#!/usr/bin/env python3
"""
Predictions runner for repo-evals.

Consumes a prompts JSONL (one {instance_id, repo, clone_url, base_commit,
issue_title, issue_body} per line) and emits a predictions JSONL of
{instance_id, model, patch, exit_code, run_index, duration_s, session_id}.

Per instance:
  1. Ensure the repo is cloned into <cache-dir>/<owner>__<repo>.
  2. `git worktree add` an isolated checkout at base_commit.
  3. Run hydron on the host against the worktree with the issue as prompt.
  4. Capture patch via `git diff` + untracked files, append JSONL.
  5. `git worktree remove --force` regardless of outcome.

Usage:
    uv run python scripts/predict_patches.py \
        --prompts prompts.jsonl \
        --model google/gemini-2.5-pro \
        --provider-url https://... \
        --provider-key $KEY \
        --workers 4 --num-predictions 1 \
        --output predictions.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hydron_runner  # noqa: E402
from hydron_runner import Provider, run_hydron_session_host, warmup_host  # noqa: E402


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Prompt:
    instance_id: str
    repo: str
    clone_url: str
    base_commit: str
    issue_title: str
    issue_body: str


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------


def load_prompts(path: Path) -> list[Prompt]:
    out: list[Prompt] = []
    with path.open() as f:
        for lineno, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                d = json.loads(raw)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{lineno} invalid JSON: {e}") from e
            out.append(
                Prompt(
                    instance_id=d["instance_id"],
                    repo=d["repo"],
                    clone_url=d["clone_url"],
                    base_commit=d["base_commit"],
                    issue_title=d.get("issue_title", ""),
                    issue_body=d.get("issue_body", ""),
                )
            )
    return out


def load_completed(path: Path) -> set[tuple[str, int]]:
    """Read existing predictions JSONL, return set of (instance_id, run_index)
    pairs that are considered done (non-empty patch OR exit_code == 0)."""
    if not path.exists():
        return set()
    done: set[tuple[str, int]] = set()
    with path.open() as f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue
            iid = d.get("instance_id")
            ri = d.get("run_index", 0)
            patch = d.get("patch") or ""
            rc = d.get("exit_code", -1)
            if iid and (patch or rc == 0):
                done.add((iid, int(ri)))
    return done


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Repo cache + worktree
# ---------------------------------------------------------------------------


def _slug_from_repo(repo: str, clone_url: str) -> str:
    if "/" in repo:
        return repo.replace("/", "__")
    path = urlparse(clone_url).path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return path.replace("/", "__") or "repo"


class RepoCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()

    def _lock_for(self, slug: str) -> threading.Lock:
        with self._locks_lock:
            lk = self._locks.get(slug)
            if lk is None:
                lk = threading.Lock()
                self._locks[slug] = lk
            return lk

    def ensure(self, prompt: Prompt) -> Path:
        """Ensure the repo is cloned and `base_commit` is fetched. Returns
        the path to the cached clone (used as worktree parent)."""
        slug = _slug_from_repo(prompt.repo, prompt.clone_url)
        dest = self.cache_dir / slug
        lock = self._lock_for(slug)
        with lock:
            if not dest.exists():
                print(
                    f"  [{prompt.instance_id}] cloning {prompt.clone_url} "
                    f"-> {dest}",
                    file=sys.stderr,
                )
                subprocess.run(
                    ["git", "clone", "--no-checkout", prompt.clone_url, str(dest)],
                    check=True,
                )
            # Make sure the base_commit is reachable. Fetch if not.
            if not _commit_exists(dest, prompt.base_commit):
                print(
                    f"  [{prompt.instance_id}] fetching {prompt.base_commit[:12]} "
                    f"in {dest.name}",
                    file=sys.stderr,
                )
                # Try a targeted fetch first; fall back to full fetch.
                r = subprocess.run(
                    [
                        "git", "-C", str(dest), "fetch", "--depth", "1",
                        "origin", prompt.base_commit,
                    ],
                    capture_output=True, text=True,
                )
                if r.returncode != 0 or not _commit_exists(dest, prompt.base_commit):
                    subprocess.run(
                        ["git", "-C", str(dest), "fetch", "--all", "--tags"],
                        check=True,
                    )
        return dest


def _commit_exists(repo_dir: Path, sha: str) -> bool:
    r = subprocess.run(
        ["git", "-C", str(repo_dir), "cat-file", "-e", f"{sha}^{{commit}}"],
        capture_output=True,
    )
    return r.returncode == 0


def add_worktree(repo_dir: Path, worktree_path: Path, base_commit: str) -> None:
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "git", "-C", str(repo_dir), "worktree", "add",
            "--detach", "--force", str(worktree_path), base_commit,
        ],
        check=True,
        capture_output=True,
    )


def remove_worktree(repo_dir: Path, worktree_path: Path) -> None:
    try:
        subprocess.run(
            ["git", "-C", str(repo_dir), "worktree", "remove", "--force",
             str(worktree_path)],
            capture_output=True,
            timeout=60,
        )
    except Exception:
        pass
    if worktree_path.exists():
        shutil.rmtree(worktree_path, ignore_errors=True)
    # Prune stale worktree metadata regardless.
    subprocess.run(
        ["git", "-C", str(repo_dir), "worktree", "prune"],
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Patch capture
# ---------------------------------------------------------------------------


def capture_patch(worktree: Path) -> str:
    """Unified diff of tracked + untracked changes in the worktree."""
    # Tracked changes.
    tracked = subprocess.run(
        ["git", "-C", str(worktree), "diff", "--no-color"],
        capture_output=True, text=True, timeout=120,
    ).stdout

    # Untracked files.
    listing = subprocess.run(
        ["git", "-C", str(worktree), "ls-files", "--others", "--exclude-standard"],
        capture_output=True, text=True, timeout=60,
    ).stdout
    chunks: list[str] = []
    if tracked:
        chunks.append(tracked)
    for rel in listing.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        # Let git produce a proper "new file" diff against /dev/null.
        d = subprocess.run(
            ["git", "-C", str(worktree), "diff", "--no-color",
             "--no-index", "--", "/dev/null", rel],
            capture_output=True, text=True, timeout=60,
        )
        # --no-index exits 1 when files differ; that's the normal case.
        if d.stdout:
            chunks.append(d.stdout)
    return "".join(chunks)


# ---------------------------------------------------------------------------
# Prediction writer (thread-safe JSONL append)
# ---------------------------------------------------------------------------


class PredictionWriter:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            with self.path.open("a") as f:
                f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())


# ---------------------------------------------------------------------------
# Per-instance work
# ---------------------------------------------------------------------------


def build_prompt(p: Prompt) -> str:
    parts = []
    if p.issue_title:
        parts.append(p.issue_title.strip())
    if p.issue_body:
        parts.append(p.issue_body.strip())
    return "\n\n".join(parts)


def run_one(
    prompt: Prompt,
    run_index: int,
    provider: Provider,
    cache: RepoCache,
    worktree_root: Path,
    timeout_s: int,
    writer: PredictionWriter,
    model_label: str,
) -> dict:
    iid = prompt.instance_id
    started = time.time()
    wt = Path(os.path.abspath(
        worktree_root / f"{iid}__run{run_index}__{os.getpid()}_{threading.get_ident()}"
    ))
    repo_dir = cache.ensure(prompt)
    patch = ""
    exit_code = -1
    session_id = ""
    try:
        add_worktree(repo_dir, wt, prompt.base_commit)
        result = run_hydron_session_host(
            repo_path=str(wt),
            prompt=build_prompt(prompt),
            provider=provider,
            timeout=timeout_s,
        )
        session_id = result.session_id
        exit_code = result.exit_code
        try:
            patch = capture_patch(wt)
        except Exception as e:
            print(f"  [{iid}] patch capture failed: {e}", file=sys.stderr)
            patch = ""
    except subprocess.CalledProcessError as e:
        print(
            f"  [{iid}] setup failed: {e.cmd} rc={e.returncode} "
            f"{(e.stderr or b'').decode('utf-8', 'replace')[:300]}",
            file=sys.stderr,
        )
        exit_code = e.returncode or -1
    except Exception as e:
        print(f"  [{iid}] unexpected error: {e}", file=sys.stderr)
        exit_code = -1
    finally:
        remove_worktree(repo_dir, wt)

    duration = round(time.time() - started, 2)
    record = {
        "instance_id": iid,
        "model": model_label,
        "patch": patch,
        "exit_code": exit_code,
        "run_index": run_index,
        "duration_s": duration,
        "session_id": session_id,
    }
    writer.append(record)
    print(
        f"  [{iid}] run {run_index} done: exit={exit_code} "
        f"patch_len={len(patch)} dur={duration}s",
        file=sys.stderr,
    )
    return record


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--prompts", required=True, type=Path)
    p.add_argument("--output", type=Path, default=Path("predictions.jsonl"))
    p.add_argument("--model", required=True)
    p.add_argument("--provider-url", default=os.getenv("LLM_BASE_URL", ""))
    p.add_argument("--provider-key", default=os.getenv("LLM_API_KEY", ""))
    p.add_argument("-k", "--num-predictions", type=int, default=1,
                   help="Runs per instance (pass@k). Default 1.")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--instance-ids", default=None,
                   help="Comma-separated filter of instance_ids.")
    p.add_argument("--timeout-s", type=int, default=600)
    p.add_argument("--cache-dir", type=Path,
                   default=Path("data/predict_cache/repos"))
    p.add_argument("--worktree-dir", type=Path,
                   default=Path("data/predict_cache/worktrees"))
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if not args.provider_key:
        print(
            "error: --provider-key is required (or set LLM_API_KEY env)",
            file=sys.stderr,
        )
        return 2

    # Build provider. Google models use google-native kind so hydron resolves
    # the provider through its built-in Google path.
    if args.model.startswith("google/"):
        provider = Provider(
            kind="google_native",
            api_key=args.provider_key,
            model=args.model,
            label=f"google:{args.model}",
        )
    else:
        if not args.provider_url:
            print(
                "error: --provider-url required for non-google models",
                file=sys.stderr,
            )
            return 2
        provider = Provider(
            kind="openai_compat",
            api_key=args.provider_key,
            model=args.model,
            label=f"openai_compat:{args.model}",
            base_url=args.provider_url,
        )

    prompts = load_prompts(args.prompts)

    if args.instance_ids:
        wanted = {s.strip() for s in args.instance_ids.split(",") if s.strip()}
        prompts = [p for p in prompts if p.instance_id in wanted]

    if args.limit is not None:
        prompts = prompts[: args.limit]

    completed = load_completed(args.output)

    # Unit of work: (prompt, run_index)
    units: list[tuple[Prompt, int]] = []
    for prm in prompts:
        for ri in range(args.num_predictions):
            if (prm.instance_id, ri) in completed:
                continue
            units.append((prm, ri))

    print(
        f"[predict] {len(prompts)} prompts, k={args.num_predictions}, "
        f"{len(units)} units to run ({len(completed)} already done), "
        f"workers={args.workers}",
        file=sys.stderr,
    )

    warmup_host()

    cache = RepoCache(args.cache_dir)
    writer = PredictionWriter(args.output)
    started_at = datetime.now(timezone.utc).isoformat()

    counts = {"total": len(units), "succeeded": 0, "failed": 0, "timeout": 0}
    counts_lock = threading.Lock()

    def _tally(rec: dict) -> None:
        with counts_lock:
            if rec["exit_code"] == 0 and rec["patch"]:
                counts["succeeded"] += 1
            elif rec["exit_code"] == -1:
                counts["timeout"] += 1
            else:
                counts["failed"] += 1

    try:
        if args.workers <= 1:
            for prm, ri in units:
                rec = run_one(
                    prm, ri, provider, cache, args.worktree_dir,
                    args.timeout_s, writer, args.model,
                )
                _tally(rec)
        else:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = [
                    ex.submit(
                        run_one, prm, ri, provider, cache,
                        args.worktree_dir, args.timeout_s, writer, args.model,
                    )
                    for prm, ri in units
                ]
                for fut in as_completed(futs):
                    try:
                        _tally(fut.result())
                    except Exception as e:
                        print(f"[predict] worker raised: {e}", file=sys.stderr)
                        with counts_lock:
                            counts["failed"] += 1
    finally:
        finished_at = datetime.now(timezone.utc).isoformat()
        meta = {
            "model": args.model,
            "provider_url": args.provider_url or None,
            "prompts_path": str(args.prompts),
            "prompts_sha256": sha256_file(args.prompts) if args.prompts.exists() else None,
            "num_predictions": args.num_predictions,
            "workers": args.workers,
            "started_at": started_at,
            "finished_at": finished_at,
            "counts": counts,
            "output": str(args.output),
        }
        meta_path = args.output.with_suffix(args.output.suffix + ".metadata.json") \
            if args.output.suffix else args.output.parent / f"{args.output.name}.metadata.json"
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
        print(
            f"[predict] done — succeeded={counts['succeeded']} "
            f"failed={counts['failed']} timeout={counts['timeout']} "
            f"(metadata: {meta_path})",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
