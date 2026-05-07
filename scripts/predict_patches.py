#!/usr/bin/env python3
"""
Predictions runner for repo-evals (mini-swe-agent backend).

Consumes a prompts JSONL (one {instance_id, repo, clone_url, base_commit,
issue_title, issue_body} per line) and emits a predictions JSONL of
{instance_id, model, patch, exit_code, run_index, duration_s, session_id}.

Per instance:
  1. Start a fresh Docker container from --container-image.
  2. Clone the repo and check out base_commit inside the container.
  3. Run mini-swe-agent against the container with the issue as prompt.
  4. Capture patch via `git diff` + untracked files (inside the container).
  5. Stop the container regardless of outcome.

Provider configuration (keys, base URL, model) is read from environment
variables by mini_runner — see scripts/mini_runner.py for the full list.
For convenience, --provider-url / --provider-key / --model on the CLI
populate LLM_BASE_URL / LLM_API_KEY / LLM_MODEL before mini_runner is
imported.

Usage:
    uv run python scripts/predict_patches.py \
        --prompts prompts.jsonl \
        --container-image python:3.12-slim \
        --model openai/qwen/qwen3-coder-480b-a35b-instruct-maas \
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
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


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
    image: str | None = None  # optional per-prompt override


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
                    image=d.get("image"),
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
# Docker helpers
# ---------------------------------------------------------------------------


_CONTAINER_LABEL = "repo_evals_predict=1"


def start_container(image: str, mem_limit: str = "4g") -> str:
    cmd = [
        "docker", "run", "-d", "--rm",
        "--label", _CONTAINER_LABEL,
        "--memory", mem_limit,
        "--memory-swap", mem_limit,
        image, "sleep", "infinity",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(
            f"docker run {image} failed (rc={r.returncode}): {r.stderr.strip()}"
        )
    return r.stdout.strip()


def stop_container(container_id: str) -> None:
    try:
        subprocess.run(
            ["docker", "stop", "-t", "1", container_id],
            capture_output=True, timeout=30,
        )
    except Exception:
        pass


def docker_exec(
    container_id: str, cmd: str, *, timeout: int = 600,
) -> tuple[str, int]:
    r = subprocess.run(
        ["docker", "exec", container_id, "bash", "-lc", cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    return (r.stdout or "") + (r.stderr or ""), r.returncode


_IMAGE_PREP_SCRIPT = r"""
set -e
need=""
command -v bash >/dev/null 2>&1 || need="$need bash"
command -v git  >/dev/null 2>&1 || need="$need git"
command -v ca-certificates >/dev/null 2>&1 || true  # package, not binary
if [ -n "$need" ] || [ ! -f /etc/ssl/certs/ca-certificates.crt ] && [ ! -f /etc/ssl/cert.pem ]; then
    if command -v apt-get >/dev/null 2>&1; then
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y --no-install-recommends bash git ca-certificates >/dev/null
        rm -rf /var/lib/apt/lists/*
    elif command -v apk >/dev/null 2>&1; then
        apk add --no-cache bash git ca-certificates >/dev/null
    elif command -v dnf >/dev/null 2>&1; then
        dnf install -y -q bash git ca-certificates >/dev/null
    elif command -v yum >/dev/null 2>&1; then
        yum install -y -q bash git ca-certificates >/dev/null
    elif command -v microdnf >/dev/null 2>&1; then
        microdnf install -y bash git ca-certificates >/dev/null
    else
        echo "no supported package manager (apt/apk/dnf/yum) and bash/git missing" >&2
        exit 127
    fi
fi
# Disable git's "dubious ownership" check — the repo dir is owned by root
# inside the container, but mini-swe-agent may run commands as a different
# uid in some images.
git config --system --add safe.directory '*' || true
"""


def prepare_image(container_id: str) -> None:
    """Install bash + git + CA bundle in the running container if missing.

    Lets users pass a barebones image like `python:3.12-slim` or
    `alpine:3.20` without pre-baking the deps mini-swe-agent needs.
    """
    # Run via /bin/sh because bash itself may not be installed yet.
    r = subprocess.run(
        ["docker", "exec", container_id, "/bin/sh", "-c", _IMAGE_PREP_SCRIPT],
        capture_output=True, text=True, timeout=600,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"image prep failed (rc={r.returncode}):\n"
            f"stdout:\n{r.stdout[-2000:]}\nstderr:\n{r.stderr[-2000:]}"
        )


def setup_repo_in_container(
    container_id: str,
    clone_url: str,
    base_commit: str,
    repo_path: str,
) -> None:
    """Clone the repo and check out base_commit inside the container.

    Tries a shallow fetch first, falls back to a full clone if that fails.
    """
    cmds = [
        f"mkdir -p {repo_path}",
        # Fast path: shallow clone, then deepen until base_commit is reachable.
        f"cd {repo_path} && git init -q && "
        f"git remote add origin {clone_url} && "
        f"(git fetch --depth 1 origin {base_commit} || "
        f" git fetch --tags origin) && "
        f"git -c advice.detachedHead=false checkout --detach {base_commit}",
    ]
    full = " && ".join(cmds)
    out, rc = docker_exec(container_id, full, timeout=900)
    if rc != 0:
        # Fallback: blow away repo_path and do a full clone.
        fallback = (
            f"rm -rf {repo_path} && mkdir -p {repo_path} && "
            f"git clone {clone_url} {repo_path} && "
            f"cd {repo_path} && "
            f"git -c advice.detachedHead=false checkout --detach {base_commit}"
        )
        out2, rc2 = docker_exec(container_id, fallback, timeout=1800)
        if rc2 != 0:
            raise RuntimeError(
                f"repo setup failed in container: shallow rc={rc} / full rc={rc2}\n"
                f"shallow output:\n{out[-2000:]}\nfull output:\n{out2[-2000:]}"
            )


def capture_patch_in_container(container_id: str, repo_path: str) -> str:
    """Unified diff of tracked + untracked changes in the container's repo."""
    # Tracked changes.
    tracked, _ = docker_exec(
        container_id,
        f"cd {repo_path} && git --no-pager diff --no-color",
        timeout=180,
    )
    # Untracked files: produce a "new file" diff for each.
    listing, _ = docker_exec(
        container_id,
        f"cd {repo_path} && git ls-files --others --exclude-standard",
        timeout=120,
    )
    chunks: list[str] = []
    if tracked.strip():
        chunks.append(tracked)
    for rel in listing.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        # --no-index exits 1 when files differ; that's the normal case.
        # We still want stdout. Quote the path defensively.
        q = rel.replace("'", "'\\''")
        d, _ = docker_exec(
            container_id,
            f"cd {repo_path} && git --no-pager diff --no-color "
            f"--no-index -- /dev/null '{q}' || true",
            timeout=120,
        )
        if d:
            chunks.append(d)
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


REPO_CONTEXT_TEMPLATE = """\
You are an autonomous coding agent working on the {repo} codebase. The \
working directory is the repository root, checked out at the base commit \
for this task.

Your task is to resolve the GitHub issue below by editing the code in this \
repository. Investigate the problem, make targeted fixes, and verify your \
changes with `git diff` before finishing. Do not commit — just leave the \
changes in the working tree.

--- ISSUE ---"""


def build_prompt(p: Prompt) -> str:
    parts = [REPO_CONTEXT_TEMPLATE.format(repo=p.repo or "this")]
    if p.issue_title:
        parts.append(p.issue_title.strip())
    if p.issue_body:
        parts.append(p.issue_body.strip())
    return "\n\n".join(parts)


def run_one(
    prompt: Prompt,
    run_index: int,
    default_image: str,
    repo_path: str,
    timeout_s: int,
    writer: PredictionWriter,
    model_label: str,
    model_override: str | None,
    eval_logs_dir: Path,
) -> dict:
    import mini_runner  # imported lazily after env vars are set in main()

    iid = prompt.instance_id
    started = time.time()
    image = prompt.image or default_image
    container_id: str | None = None
    patch = ""
    exit_code = -1
    session_id = ""

    try:
        container_id = start_container(image)
        prepare_image(container_id)
        setup_repo_in_container(
            container_id, prompt.clone_url, prompt.base_commit, repo_path,
        )
        result = mini_runner.run_mini_session(
            container_id=container_id,
            prompt=build_prompt(prompt),
            repo_path=repo_path,
            model=model_override,
            exec_timeout=timeout_s,
        )
        session_id = f"{iid}__run{run_index}__{uuid.uuid4().hex[:8]}"
        # Mini's exit_status is a string ("Submitted", "LimitsExceeded", ...).
        # Map "Submitted" / empty (no error) to 0; anything else to non-zero.
        exit_code = 0 if result.exit_status in ("Submitted", "") else 1
        try:
            patch = capture_patch_in_container(container_id, repo_path)
        except Exception as e:
            print(f"  [{iid}] patch capture failed: {e}", file=sys.stderr)
            patch = ""

        # Persist trajectory (messages) for later inspection.
        try:
            export_path = eval_logs_dir / f"{iid}__run{run_index}.json"
            export_path.write_text(
                json.dumps(
                    {
                        "instance_id": iid,
                        "run_index": run_index,
                        "provider_label": result.provider_label,
                        "model": result.model_name,
                        "exit_status": result.exit_status,
                        "submission": result.submission,
                        "n_calls": result.n_calls,
                        "cost": result.cost,
                        "messages": result.messages,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )
        except Exception as e:
            print(f"  [{iid}] trajectory export failed: {e}", file=sys.stderr)
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
        if container_id:
            stop_container(container_id)

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
    p.add_argument("--output", type=Path, default=None,
                   help="Predictions JSONL path. Defaults to "
                        "eval_output/<file-prefix>_predictions.jsonl when "
                        "--file-prefix is set, else predictions.jsonl.")
    p.add_argument("--file-prefix", default=None,
                   help="Convenience: store predictions and per-session logs "
                        "under eval_output/ using this prefix. Sets "
                        "--output to eval_output/<prefix>_predictions.jsonl "
                        "and --eval-logs-dir to eval_output/<prefix>_logs "
                        "unless those are explicitly provided.")
    p.add_argument("--model", required=True,
                   help="Model id used for the trajectory and as the "
                        "`model` field in predictions. If it has a litellm "
                        "provider prefix (e.g. openai/, gemini/) it is "
                        "passed through unchanged; otherwise mini_runner's "
                        "env-driven provider pool decides the prefix.")
    p.add_argument("--provider-url",
                   default=os.getenv("LLM_BASE_URL", ""),
                   help="OpenAI-compatible base URL. Sets LLM_BASE_URL "
                        "for mini_runner if provided.")
    p.add_argument("--provider-key",
                   default=os.getenv("LLM_API_KEY", ""),
                   help="API key. Sets LLM_API_KEY for mini_runner if "
                        "provided. Google native keys can also be passed "
                        "via GOOGLE_GENERATIVE_AI_API_KEY_<N> env vars.")
    p.add_argument("--container-image", default="python:3.12-slim",
                   help="Docker image used for each prediction. Bash, git "
                        "and ca-certificates are installed automatically "
                        "if missing (apt/apk/dnf/yum/microdnf supported). "
                        "Default: python:3.12-slim.")
    p.add_argument("--container-repo-path", default="/repo",
                   help="Path inside the container to clone the repo into.")
    p.add_argument("-k", "--num-predictions", type=int, default=1,
                   help="Runs per instance (pass@k). Default 1.")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--instance-ids", default=None,
                   help="Comma-separated filter of instance_ids.")
    p.add_argument("--timeout-s", type=int,
                   default=int(os.getenv("MINI_EXEC_TIMEOUT", "600")),
                   help="Per-bash-command timeout passed to the docker "
                        "environment. Defaults to $MINI_EXEC_TIMEOUT or 600.")
    p.add_argument("--eval-logs-dir", type=Path, default=None,
                   help="Directory to export per-session trajectory JSON "
                        "(created if missing). Defaults to "
                        "eval_output/<file-prefix>_logs when --file-prefix "
                        "is set, else eval_logs.")
    args = p.parse_args()

    eval_output_root = Path("eval_output")
    if args.file_prefix:
        if args.output is None:
            args.output = eval_output_root / f"{args.file_prefix}_predictions.jsonl"
        if args.eval_logs_dir is None:
            args.eval_logs_dir = eval_output_root / f"{args.file_prefix}_logs"
    if args.output is None:
        args.output = Path("predictions.jsonl")
    if args.eval_logs_dir is None:
        args.eval_logs_dir = Path("eval_logs")
    return args


def main() -> int:
    args = parse_args()

    # mini_runner reads provider config from env at import time, so populate
    # it from CLI flags before importing.
    if args.provider_url:
        os.environ["LLM_BASE_URL"] = args.provider_url
    if args.provider_key:
        os.environ["LLM_API_KEY"] = args.provider_key
    # Only set LLM_MODEL when --model isn't a Google id (Google models use
    # GOOGLE_MODEL / per-key env vars in mini_runner).
    model_label = args.model
    model_override: str | None = args.model
    if args.model.startswith("google/") or args.model.startswith("gemini/"):
        bare = args.model.split("/", 1)[1]
        os.environ.setdefault("GOOGLE_MODEL", bare)
        # mini_runner.run_mini_session(model=...) wants a litellm-prefixed id.
        model_override = f"gemini/{bare}"
    else:
        os.environ["LLM_MODEL"] = args.model
        model_override = None  # let mini_runner pick provider's default model

    sys.path.insert(0, str(Path(__file__).resolve().parent))

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
        f"workers={args.workers}, image={args.container_image}",
        file=sys.stderr,
    )

    writer = PredictionWriter(args.output)
    args.eval_logs_dir.mkdir(parents=True, exist_ok=True)
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

    def _submit(prm: Prompt, ri: int) -> dict:
        return run_one(
            prm, ri,
            default_image=args.container_image,
            repo_path=args.container_repo_path,
            timeout_s=args.timeout_s,
            writer=writer,
            model_label=model_label,
            model_override=model_override,
            eval_logs_dir=args.eval_logs_dir,
        )

    try:
        if args.workers <= 1:
            for prm, ri in units:
                _tally(_submit(prm, ri))
        else:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = [ex.submit(_submit, prm, ri) for prm, ri in units]
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
            "container_image": args.container_image,
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
