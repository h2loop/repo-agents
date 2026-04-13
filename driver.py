#!/usr/bin/env python3
"""
Multi-repo data generation driver.

Reads a .txt file listing repository HTTPS URLs (one per line, optional branch),
then drives the full pipeline for each: clone -> config -> extract -> docker build
-> generate -> filter -> cleanup.

Usage:
    uv run python driver.py \
        --repos repos.txt \
        --output-dir data/ \
        --domain telecom_5g \
        --workers 4

repos.txt format (one per line, # comments and blank lines ignored):
    https://github.com/srsran/srsRAN_Project.git main
    https://github.com/zephyrproject-rtos/zephyr.git
    https://github.com/apache/nuttx.git master
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent
REPO_CONFIG_PATH = PROJECT_ROOT / "configs" / "repo_config.json"
COMMITS_CONFIG_PATH = PROJECT_ROOT / "configs" / "commits.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def repo_name_from_url(url: str) -> str:
    """Extract repository name from a git HTTPS URL."""
    path = urlparse(url).path.rstrip("/")
    name = path.rsplit("/", 1)[-1]
    if name.endswith(".git"):
        name = name[:-4]
    return name


def parse_repos_file(path: Path) -> list[dict]:
    """Parse repos.txt into a list of {url, branch} dicts."""
    repos = []
    for lineno, raw_line in enumerate(path.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        url = parts[0]
        branch = parts[1] if len(parts) > 1 else None
        repos.append({"url": url, "branch": branch, "line": lineno})
    return repos


def run(cmd: list[str], *, label: str, cwd: str | Path | None = None) -> None:
    """Run a subprocess, streaming output. Raises on failure."""
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  [{label}] {' '.join(cmd)}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"[{label}] exited with code {result.returncode}")


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


def step_clone(url: str, branch: str | None, clone_dir: Path) -> Path:
    """Clone the repo. Returns the path to the cloned directory."""
    name = repo_name_from_url(url)
    dest = clone_dir / name
    if dest.exists():
        print(f"  [clone] {dest} already exists — skipping clone", file=sys.stderr)
        return dest
    clone_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--depth", "1"]
    if branch:
        cmd += ["--branch", branch]
    cmd += [url, str(dest)]
    run(cmd, label="clone")
    return dest


def step_populate_config(repo_path: Path, domain: str) -> dict:
    """Generate repo config at the canonical configs/repo_config.json path.

    Returns the parsed config dict.
    """
    REPO_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            "scripts/populate_repo_config.py",
            "--repo-path", str(repo_path),
            "--output", str(REPO_CONFIG_PATH),
            "--domain", domain,
            "--force",
        ],
        label="config",
    )
    return json.loads(REPO_CONFIG_PATH.read_text())


def step_write_commits_json() -> None:
    """Write a minimal commits.json with a single 'latest' entry.

    generate_data.py requires --commits; when there are no valid commit SHAs
    it falls back to the 'latest' Docker image tag automatically.
    """
    commits = {
        "description": "Single HEAD snapshot (shallow clone)",
        "commits": [
            {"sha": "PLACEHOLDER_latest", "label": "head", "date": ""}
        ],
    }
    COMMITS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    COMMITS_CONFIG_PATH.write_text(json.dumps(commits, indent=2) + "\n")


def step_extract_functions(repo_path: Path, output: Path) -> None:
    """Extract functions from the repo."""
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            "scripts/extract_functions_generic.py",
            "--repo-root", str(repo_path),
            "--output", str(output),
        ],
        label="extract",
    )


def step_build_docker(url: str, branch: str | None, image_prefix: str) -> str:
    """Build Docker image using Dockerfile.generic. Returns image tag.

    The tag must match `docker_image_prefix` from repo_config.json, since
    generate_data.py constructs container image names as `{prefix}:latest`.
    """
    tag = f"{image_prefix}:latest"
    cmd = [
        "docker", "build",
        "-f", "docker/Dockerfile.generic",
        "--build-arg", f"REPO_URL={url}",
    ]
    if branch:
        cmd += ["--build-arg", f"REPO_BRANCH={branch}"]
    cmd += ["-t", tag, "."]
    run(cmd, label="docker-build")
    return tag


def step_generate(
    functions_file: Path,
    bug_prompts_file: Path,
    output_dir: Path,
    bugs_per_func: int,
    max_samples: int | None,
    workers: int,
    seed: int,
    resume: bool,
    max_steps: int | None,
) -> None:
    """Run the SERA data generation pipeline (generate_data.py)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "scripts/generate_data.py",
        "--functions", str(functions_file),
        "--bug-prompts", str(bug_prompts_file),
        "--template", "configs/bug_prompt_template.txt",
        "--commits", str(COMMITS_CONFIG_PATH),
        "--demo-prs-dir", "configs/demo_prs",
        "--output-dir", str(output_dir),
        "--bugs-per-func", str(bugs_per_func),
        "--workers", str(workers),
        "--seed", str(seed),
    ]
    if max_samples is not None:
        cmd += ["--max-samples", str(max_samples)]
    if max_steps is not None:
        cmd += ["--max-steps", str(max_steps)]
    if resume:
        cmd.append("--resume")
    run(cmd, label="generate")


def step_filter(input_dir: Path, output_dir: Path) -> None:
    """Filter raw trajectories for quality."""
    output_dir.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            "scripts/filter_data.py",
            "--input-dir", str(input_dir),
            "--output-dir", str(output_dir),
        ],
        label="filter",
    )


def pre_run_cleanup() -> None:
    """Clean up artifacts from a prior (possibly crashed) driver run.

    - Stops any orphaned containers built from `*-sera:*` images (the driver
      tags its build images this way; containers run with `--rm` so they
      should auto-remove on stop).
    - Prunes dangling images and stopped container records.
    """
    print(f"\n{'='*60}", file=sys.stderr)
    print("  [pre-cleanup] Checking for orphaned state from prior runs", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    # Find running containers whose image matches the driver's tagging scheme.
    try:
        ps = subprocess.run(
            ["docker", "ps", "--format", "{{.ID}} {{.Image}}"],
            capture_output=True, text=True, timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(f"  [pre-cleanup] docker ps failed: {exc} — skipping", file=sys.stderr)
        return

    orphans = []
    for line in ps.stdout.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        cid, image = parts
        # Match images tagged by step_build_docker (`<prefix>-sera:latest`).
        if "-sera:" in image or image.endswith("-sera"):
            orphans.append((cid, image))

    if orphans:
        print(f"  [pre-cleanup] Found {len(orphans)} orphaned container(s):", file=sys.stderr)
        for cid, image in orphans:
            print(f"    - {cid[:12]} ({image})", file=sys.stderr)
        for cid, _ in orphans:
            subprocess.run(
                ["docker", "kill", cid],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
            )
    else:
        print("  [pre-cleanup] No orphaned sera containers", file=sys.stderr)

    # Prune dangling images and any non-running container records left behind.
    subprocess.run(
        ["docker", "container", "prune", "-f"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
    )
    subprocess.run(
        ["docker", "image", "prune", "-f"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
    )
    print("  [pre-cleanup] Pruned stopped containers and dangling images", file=sys.stderr)


def step_cleanup(repo_path: Path, docker_image: str) -> None:
    """Remove cloned repo and Docker image."""
    if repo_path.exists():
        print(f"  [cleanup] Removing {repo_path}", file=sys.stderr)
        shutil.rmtree(repo_path)
    print(f"  [cleanup] Removing Docker image {docker_image}", file=sys.stderr)
    subprocess.run(
        ["docker", "rmi", "-f", docker_image],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Drive data generation across multiple repositories"
    )
    parser.add_argument(
        "--repos", type=Path, required=True, help="Path to .txt file with repo URLs"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data"),
        help="Base output directory (default: data/)",
    )
    parser.add_argument(
        "--domain", type=str, default="telecom_5g",
        help="Domain for bug prompts (default: telecom_5g). Use '' for generic.",
    )
    parser.add_argument(
        "--bugs-per-func", type=int, default=3,
        help="Max bug attempts per function (default: 3)",
    )
    parser.add_argument(
        "--max-samples", type=int, default=None,
        help="Cap total functions per repo (default: all)",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--max-steps", type=int, default=None,
        help="Max agent steps per hydron session",
    )
    parser.add_argument(
        "--clone-dir", type=Path, default=Path("repos"),
        help="Directory to clone repos into (default: repos/)",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume generation (skip completed samples)",
    )
    parser.add_argument(
        "--skip-filter", action="store_true",
        help="Skip the filter_data.py step",
    )
    args = parser.parse_args()

    if not args.repos.exists():
        sys.exit(f"Error: repos file not found: {args.repos}")

    repos = parse_repos_file(args.repos)
    if not repos:
        sys.exit("Error: no repos found in file")

    print(f"Found {len(repos)} repo(s) to process", file=sys.stderr)

    pre_run_cleanup()

    results: list[dict] = []

    for i, repo_info in enumerate(repos, 1):
        url = repo_info["url"]
        branch = repo_info["branch"]
        name = repo_name_from_url(url)
        t0 = time.time()

        print(f"\n{'#'*60}", file=sys.stderr)
        print(f"  [{i}/{len(repos)}] {name} ({url})", file=sys.stderr)
        print(f"{'#'*60}", file=sys.stderr)

        entry = {"repo": name, "url": url, "status": "pending", "failed_step": None}
        docker_image = None
        repo_path = None

        try:
            # Step 1: Clone
            repo_path = step_clone(url, branch, args.clone_dir)

            # Step 2: Generate repo config (writes to configs/repo_config.json)
            config = step_populate_config(repo_path, args.domain)
            short_name = config.get("repo_short_name", name.lower()[:10])
            image_prefix = config.get("docker_image_prefix", f"{short_name}-sera")
            bug_prompts_file = Path(
                config.get("bug_prompts_file", f"configs/bug_prompts_{short_name}.json")
            )
            functions_file = Path(
                config.get("functions_file", f"data/{short_name}_functions.jsonl")
            )

            # Step 3: Extract functions
            step_extract_functions(repo_path, functions_file)

            # Step 4: Write commits.json (single "latest" entry for shallow clone)
            step_write_commits_json()

            # Step 5: Build Docker image (tag must match docker_image_prefix from config)
            docker_image = step_build_docker(url, branch, image_prefix)

            # Step 6: Generate data
            raw_dir = args.output_dir / short_name / "raw"
            step_generate(
                functions_file=functions_file,
                bug_prompts_file=bug_prompts_file,
                output_dir=raw_dir,
                bugs_per_func=args.bugs_per_func,
                max_samples=args.max_samples,
                workers=args.workers,
                seed=args.seed,
                resume=args.resume,
                max_steps=args.max_steps,
            )

            # Step 7: Filter
            if not args.skip_filter:
                filtered_dir = args.output_dir / short_name / "filtered"
                step_filter(raw_dir, filtered_dir)

            entry["status"] = "success"

        except Exception as exc:
            entry["status"] = "failed"
            entry["failed_step"] = str(exc)
            print(f"\n  ERROR: {exc}", file=sys.stderr)
            print(f"  Skipping to next repo...\n", file=sys.stderr)

        finally:
            # Step 8: Cleanup
            try:
                step_cleanup(
                    repo_path or args.clone_dir / name,
                    docker_image or f"{name.lower()}-sera:latest",
                )
            except Exception as exc:
                print(f"  [cleanup] Warning: {exc}", file=sys.stderr)

        entry["elapsed_s"] = round(time.time() - t0, 1)
        results.append(entry)

    # Summary
    print(f"\n{'='*60}", file=sys.stderr)
    print("  SUMMARY", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    succeeded = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] == "failed"]
    print(f"  Total: {len(results)}  |  OK: {len(succeeded)}  |  Failed: {len(failed)}", file=sys.stderr)
    for r in results:
        icon = "OK" if r["status"] == "success" else "FAIL"
        line = f"  [{icon}] {r['repo']} ({r['elapsed_s']}s)"
        if r["failed_step"]:
            line += f" — {r['failed_step']}"
        print(line, file=sys.stderr)


if __name__ == "__main__":
    main()
