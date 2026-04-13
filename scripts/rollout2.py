#!/usr/bin/env python3
"""
Phase 5.3: Rollout 2 — Reproduction from synthetic PR description (Hydron-based).

Given ONLY a synthetic PR description (no original bug prompt, no function hint),
drives hydron inside a Docker container to reproduce the change.

Produces:
  - T2: full agent trajectory (JSONL)
  - P2: unified diff of the reproduced change

Usage:
    python scripts/rollout2.py \
        --pr data/raw/001_synth_pr.md \
        --container srsran-sera:latest \
        --output-dir data/raw \
        --run-id 001

Environment variables:
    HYDRON_HOST_PATH    - Path to hydron binary on host (default: ./hydron)
    HYDRON_MODEL        - Model for hydron (format: provider/model)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import hydron_runner
import trajectory_converter

from rollout1 import (
    REPO_CFG,
    start_container,
    stop_container,
)

# Repo-specific values from config
_REPO_DISPLAY_NAME = REPO_CFG.get("repo_display_name", "OpenAirInterface 5G")
_SYSTEM_PROMPT_CONTEXT = REPO_CFG.get("system_prompt_context", "")
_BUILD_CAVEAT = REPO_CFG.get("build_caveat", "")
_CONTAINER_REPO_PATH = REPO_CFG.get("container_repo_path", "/repo")
_DOCKER_IMAGE_PREFIX = REPO_CFG.get("docker_image_prefix", "sera")

# Repo-agnostic system prompt (shared with rollout1)
from rollout1 import SYSTEM_PROMPT

# Repo-specific context for the user prompt
_build_caveat_line = f"\n{_BUILD_CAVEAT}" if _BUILD_CAVEAT else ""
REPO_CONTEXT = f"""\
You are working on the {_REPO_DISPLAY_NAME} codebase.
{_SYSTEM_PROMPT_CONTEXT}

Working directory is {_CONTAINER_REPO_PATH}.{_build_caveat_line}

You will be given a pull request description. Your task is to implement the changes
described in the PR. Navigate the codebase, understand the relevant code, and make
the necessary modifications."""


def run_single_rollout2(
    pr_text: str,
    container_image: str,
    output_dir: Path,
    run_id: str,
    container_id: str | None = None,
    max_steps: int | None = None,
) -> dict | None:
    """Run a single rollout 2 for a given synthetic PR.

    If container_id is provided, uses that container (caller manages lifecycle).
    Otherwise starts and stops its own container.

    Returns metadata dict on success, None on failure.
    """
    task_prompt = f"Please implement the following pull request:\n\n{pr_text}"
    full_prompt = f"{REPO_CONTEXT}\n\n{task_prompt}"

    owns_container = container_id is None
    if owns_container:
        print(f"  Starting container {container_image}...", file=sys.stderr)
        container_id = start_container(container_image)

    try:
        # Run hydron agent inside the container
        result = hydron_runner.run_hydron_session(
            container_id,
            full_prompt,
            repo_path=_CONTAINER_REPO_PATH,
            max_steps=max_steps,
        )

        if not result.session_id:
            print("  FAILED: no session ID returned", file=sys.stderr)
            return None

        # Export session and convert to SERA trajectory format
        try:
            session_data = hydron_runner.export_session(container_id, result.session_id)
        except Exception as e:
            print(f"  FAILED: session export error: {e}", file=sys.stderr)
            return None

        trajectory = trajectory_converter.convert(
            session_data,
            system_prompt=SYSTEM_PROMPT,
        )

        # Extract patch
        patch = hydron_runner.get_patch(container_id, repo_path=_CONTAINER_REPO_PATH)

        # Save artifacts
        traj_path = output_dir / f"{run_id}_t2_trajectory.jsonl"
        patch_path = output_dir / f"{run_id}_p2.diff"
        meta_path = output_dir / f"{run_id}_t2_meta.json"

        with open(traj_path, "w") as f:
            f.write(trajectory_converter.to_jsonl(trajectory))

        with open(patch_path, "w") as f:
            f.write(patch)

        metadata = {
            "run_id": run_id,
            "pr_text": pr_text[:500],
            "trajectory_path": str(traj_path),
            "patch_path": str(patch_path),
            "patch_lines": len(
                [
                    l
                    for l in patch.splitlines()
                    if l.startswith("+") and not l.startswith("+++")
                ]
            ),
            "trajectory_steps": len(
                [e for e in trajectory if e["role"] == "assistant"]
            ),
            "hydron_session_id": result.session_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        print(
            f"  OK: {metadata['trajectory_steps']} steps, "
            f"{metadata['patch_lines']} patch lines",
            file=sys.stderr,
        )
        return metadata

    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return None

    finally:
        if owns_container:
            stop_container(container_id)


def main():
    parser = argparse.ArgumentParser(
        description="SERA SVG Rollout 2: Reproduction from PR (Hydron)"
    )
    parser.add_argument("--pr", type=Path, help="Single synthetic PR file to process")
    parser.add_argument(
        "--container",
        type=str,
        default=f"{_DOCKER_IMAGE_PREFIX}:latest",
        help="Docker image",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/raw"), help="Output directory"
    )
    parser.add_argument("--run-id", type=str, default=None, help="Run ID")
    parser.add_argument(
        "--batch-dir", type=Path, help="Directory with *_synth_pr.md files"
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.pr:
        run_id = args.run_id or args.pr.stem.replace("_synth_pr", "")
        pr_text = args.pr.read_text()
        result = run_single_rollout2(pr_text, args.container, args.output_dir, run_id)
        if result:
            print(json.dumps(result, indent=2))
        else:
            sys.exit(1)

    elif args.batch_dir:
        pr_files = sorted(args.batch_dir.glob("*_synth_pr.md"))
        print(f"Found {len(pr_files)} synthetic PRs to process", file=sys.stderr)

        results = []
        for i, pr_path in enumerate(pr_files):
            run_id = pr_path.stem.replace("_synth_pr", "")

            t2_path = args.output_dir / f"{run_id}_t2_trajectory.jsonl"
            if t2_path.exists():
                print(
                    f"  [{i + 1}/{len(pr_files)}] Skip (exists): {run_id}",
                    file=sys.stderr,
                )
                continue

            print(
                f"  [{i + 1}/{len(pr_files)}] Processing {run_id}...", file=sys.stderr
            )
            pr_text = pr_path.read_text()
            result = run_single_rollout2(
                pr_text, args.container, args.output_dir, run_id
            )
            if result:
                results.append(result)

        print(
            f"\nCompleted: {len(results)}/{len(pr_files)} rollout 2s", file=sys.stderr
        )

    else:
        parser.error("Provide either --pr or --batch-dir")


if __name__ == "__main__":
    main()
