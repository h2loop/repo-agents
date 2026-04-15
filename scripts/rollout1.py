#!/usr/bin/env python3
"""
Phase 5.1: Rollout 1 — Change generation (Hydron-based).

Drives hydron inside a Docker container to make a change in the target
codebase starting from a randomly selected function and bug prompt.

Produces:
  - T1: full agent trajectory (JSONL of messages)
  - P1: unified diff of the change (git diff)

Usage:
    python scripts/rollout1.py \
        --functions data/srsran_functions.jsonl \
        --bug-prompts configs/bug_prompts_srsran.json \
        --template configs/bug_prompt_template.txt \
        --container srsran-sera:latest \
        --output-dir data/raw \
        --num-samples 1

Environment variables:
    HYDRON_HOST_PATH    - Path to hydron binary on host (default: ./hydron)
    HYDRON_CONTAINER_PATH - Path to hydron inside container (default: /hydron)
    HYDRON_MODEL        - Model for hydron (format: provider/model)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
import uuid
from pathlib import Path

import hydron_runner
import trajectory_converter

# ---------------------------------------------------------------------------
# Repo configuration
# ---------------------------------------------------------------------------
REPO_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "configs" / "repo_config.json"
)


def load_repo_config(config_path: Path = REPO_CONFIG_PATH) -> dict:
    """Load repo_config.json if it exists."""
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


REPO_CFG = load_repo_config()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_RETRIES = 2

# Repo-specific values from config
_REPO_DISPLAY_NAME = REPO_CFG.get("repo_display_name", "OpenAirInterface 5G")
_REPO_DESCRIPTION = REPO_CFG.get(
    "repo_description", "a 5G telecommunications implementation"
)
_SYSTEM_PROMPT_CONTEXT = REPO_CFG.get("system_prompt_context", "")
_BUILD_CAVEAT = REPO_CFG.get("build_caveat", "")
_CONTAINER_REPO_PATH = REPO_CFG.get("container_repo_path", "/repo")
_DOCKER_IMAGE_PREFIX = REPO_CFG.get("docker_image_prefix", "sera")

# ---------------------------------------------------------------------------
# Repo-agnostic system prompt for training trajectories.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are an autonomous coding agent. You have access to a shell and can run \
commands, read files, and edit code. Think step by step, investigate the \
problem, and make targeted fixes. Always verify your changes with `git diff` \
before finishing."""

# Repo-specific context — embedded in the user prompt for hydron.
# ---------------------------------------------------------------------------
_build_caveat_line = f"\n{_BUILD_CAVEAT}" if _BUILD_CAVEAT else ""
REPO_CONTEXT = f"""\
You are working on the {_REPO_DISPLAY_NAME} codebase.
{_SYSTEM_PROMPT_CONTEXT}

Working directory is {_CONTAINER_REPO_PATH}.{_build_caveat_line}"""

# ---------------------------------------------------------------------------
# Docker helpers (container lifecycle — kept from original)
# ---------------------------------------------------------------------------


def start_container(image: str) -> str:
    """Start a Docker container with hydron mounted, return container ID.

    Containers are labeled `sera_pipeline=1` so the driver's pre-run
    cleanup can identify and kill only its own orphans (not unrelated
    user containers that happen to share an image suffix).
    """
    hydron_host = hydron_runner.HYDRON_HOST_PATH
    hydron_container = hydron_runner.HYDRON_BIN

    # Per-container memory cap. Hydron (Bun-based) reserves ~74GB virtual
    # per process but only uses ~300MB RSS. Without a cap, the kernel OOM
    # killer fires on overcommit heuristics even though physical usage is
    # fine. The cap prevents any single container from genuinely running
    # away, while still allowing the large virtual reservation.
    # Per-container RSS cap. With vm.overcommit_memory=1 on the host the
    # 74GB Bun virtual reservation is harmless; only real pages count.
    # Hydron typically uses 300-800MB RSS but can spike to 3-4GB on large
    # repos during git/grep. 4g gives comfortable headroom for 16 workers
    # on a 64GB host (peaks are not simultaneous in practice).
    mem_limit = os.getenv("CONTAINER_MEMORY_LIMIT", "4g")

    # Retry with backoff — when the pool warms many containers concurrently
    # on a loaded daemon (especially right after pre_run_cleanup), a single
    # `docker run` can exceed 60s. Fail only after several attempts.
    cmd = [
        "docker", "run", "-d", "--rm",
        "--label", "sera_pipeline=1",
        "--memory", mem_limit,
        "--memory-swap", mem_limit,
        "-v", f"{hydron_host}:{hydron_container}:ro",
        image, "sleep", "infinity",
    ]
    attempts = 4
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=60
            )
        except subprocess.TimeoutExpired as exc:
            last_err = exc
            wait = min(30, 5 * (2 ** i))
            print(
                f"    [start_container] docker run timed out "
                f"(attempt {i + 1}/{attempts}) — retrying in {wait}s",
                file=sys.stderr,
            )
            time.sleep(wait)
            continue
        if result.returncode != 0:
            raise RuntimeError(f"Failed to start container: {result.stderr}")
        return result.stdout.strip()

    raise RuntimeError(
        f"docker run timed out after {attempts} attempts for image {image} "
        f"— daemon overloaded"
    ) from last_err


def stop_container(container_id: str):
    """Stop and remove a Docker container."""
    subprocess.run(
        ["docker", "stop", container_id],
        capture_output=True,
        timeout=30,
    )


def reset_container(container_id: str) -> bool:
    """Reset a container's repo to clean state. Returns True on success."""
    # Remove any stale index lock from a previously-killed git process,
    # then do a single-pass hard reset (faster than checkout+clean on large repos).
    cmd = (
        f"cd {_CONTAINER_REPO_PATH} && "
        f"rm -f .git/index.lock && "
        f"git reset --hard HEAD && git clean -fdx"
    )
    _, rc = hydron_runner.docker_exec(container_id, cmd, timeout=120)
    return rc == 0


class ContainerPool:
    """Pool of reusable Docker containers to avoid start/stop overhead."""

    def __init__(
        self,
        image: str,
        size: int = 1,
        max_extras: int | None = None,
    ):
        self.image = image
        self.size = size
        # Cap on "extra" containers spawned past pool size when acquire
        # times out. Without a cap, a slow daemon causes every blocked
        # worker to spawn a fresh container, piling load onto the already-
        # stressed daemon and producing the cascade we're trying to avoid.
        # Default to half the pool size (min 1).
        self.max_extras = (
            max_extras if max_extras is not None else max(1, size // 2)
        )
        self._containers: list[str] = []
        # Containers spawned outside the pool's capacity (e.g. on acquire
        # timeout). On release these are stopped rather than recycled, so
        # the semaphore/list invariant `len(_containers) <= size` holds.
        self._extras: set[str] = set()
        self._lock = __import__("threading").Lock()
        self._sem = __import__("threading").Semaphore(0)
        for i in range(size):
            cid = start_container(image)
            self._containers.append(cid)
            self._sem.release()
            print(
                f"    [pool] {image}: warmed {i + 1}/{size} containers",
                file=sys.stderr,
            )

    def acquire(self, timeout: float = 300) -> str:
        """Get a clean container from the pool. Blocks if none available.

        If the wait times out, spin up a fresh container rather than failing —
        a stuck/leaked container should not cascade failures across workers.
        Such "extra" containers are tracked and stopped on release instead of
        being added back to the pool, to avoid unbounded pool-size drift.

        Extras are capped at ``self.max_extras`` so a slow daemon can't be
        further loaded with new container starts. When at the cap, this
        retries the semaphore wait up to ``max_wait_rounds`` times before
        giving up.
        """
        max_wait_rounds = 3
        for round_idx in range(max_wait_rounds):
            if self._sem.acquire(timeout=timeout):
                break
            with self._lock:
                extras_count = len(self._extras)
            if extras_count < self.max_extras:
                print(
                    f"  [pool] acquire timed out after {timeout}s "
                    f"(extras={extras_count}/{self.max_extras}) — "
                    f"starting fresh container",
                    file=sys.stderr,
                )
                cid = start_container(self.image)
                with self._lock:
                    self._extras.add(cid)
                return cid
            print(
                f"  [pool] acquire timed out after {timeout}s, extras at "
                f"cap ({self.max_extras}) — waiting again "
                f"(round {round_idx + 1}/{max_wait_rounds})",
                file=sys.stderr,
            )
        else:
            raise RuntimeError(
                f"pool acquire for {self.image} failed after "
                f"{max_wait_rounds} rounds of {timeout}s with extras at cap "
                f"({self.max_extras}) — daemon likely stuck"
            )
        with self._lock:
            cid = self._containers.pop(0)
        if not reset_container(cid):
            try:
                stop_container(cid)
            except Exception:
                pass
            cid = start_container(self.image)
            if not reset_container(cid):
                # Replacement is also broken — fail loudly so the worker's
                # exception path can react, rather than handing back a
                # poisoned container.
                try:
                    stop_container(cid)
                except Exception:
                    pass
                # Restore semaphore so other waiters aren't starved.
                self._sem.release()
                raise RuntimeError(
                    f"reset_container failed twice for image {self.image}"
                )
        return cid

    def release(self, container_id: str):
        """Return a container to the pool, or stop it if it's an extra."""
        with self._lock:
            if container_id in self._extras:
                self._extras.discard(container_id)
                is_extra = True
            else:
                self._containers.append(container_id)
                is_extra = False
        if is_extra:
            try:
                stop_container(container_id)
            except Exception:
                pass
        else:
            self._sem.release()

    def shutdown(self):
        """Stop all containers in the pool (including outstanding extras)."""
        with self._lock:
            cids = list(self._containers) + list(self._extras)
            self._containers.clear()
            self._extras.clear()
        for cid in cids:
            try:
                stop_container(cid)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_functions(path: Path) -> list[dict]:
    """Load functions from JSONL."""
    functions = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                functions.append(json.loads(line))
    return functions


def load_bug_prompts(path: Path) -> list[dict]:
    """Load bug prompts from JSON."""
    with open(path) as f:
        return json.load(f)


def format_prompt(template: str, func: dict, bug: dict) -> str:
    """Format the rollout 1 prompt from template, function, and bug."""
    return template.format(
        bug_description=bug["description"],
        func_name=func["name"],
        subsystem=func["subsystem"],
        file_path=func["file"],
        start_line=func["start_line"],
    )


# ---------------------------------------------------------------------------
# Rollout via Hydron
# ---------------------------------------------------------------------------


def run_single(
    func: dict,
    bug: dict,
    template: str,
    container_image: str,
    output_dir: Path,
    run_id: str,
    container_id: str | None = None,
    max_steps: int | None = None,
) -> dict | None:
    """Run a single rollout 1 for one function + bug combination.

    If container_id is provided, uses that container (caller manages lifecycle).
    Otherwise starts and stops its own container.

    Returns metadata dict on success, None on failure.
    """
    task_prompt = format_prompt(template, func, bug)
    full_prompt = f"{REPO_CONTEXT}\n\n{task_prompt}"

    owns_container = container_id is None
    if owns_container:
        print(f"  Starting container {container_image}...", file=sys.stderr)
        container_id = start_container(container_image)

    try:
        # Run hydron agent inside the container
        print(
            f"  Running hydron for {func['name']} / {bug['bug_id']}...", file=sys.stderr
        )
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
            session_data, system_prompt=SYSTEM_PROMPT
        )

        # Extract patch
        patch = hydron_runner.get_patch(container_id, repo_path=_CONTAINER_REPO_PATH)

        # Patch quality check
        agent_steps = len([e for e in trajectory if e["role"] == "assistant"])
        if not patch.strip():
            print(
                f"  REJECTED: empty patch ({agent_steps} agent steps)", file=sys.stderr
            )
            return None

        # Reject patches that are only comments or whitespace changes
        code_lines = [
            l[1:].strip()
            for l in patch.splitlines()
            if l.startswith("+") and not l.startswith("+++")
        ]
        substantive = [
            l
            for l in code_lines
            if l
            and not l.startswith("//")
            and not l.startswith("/*")
            and not l.startswith("*")
            and not l.startswith("#")
        ]
        if not substantive:
            print(
                f"  REJECTED: comment/whitespace-only patch "
                f"({agent_steps} steps, {len(code_lines)} added lines)",
                file=sys.stderr,
            )
            return None

        # Save artifacts
        traj_path = output_dir / f"{run_id}_t1_trajectory.jsonl"
        patch_path = output_dir / f"{run_id}_p1.diff"
        meta_path = output_dir / f"{run_id}_t1_meta.json"

        with open(traj_path, "w") as f:
            f.write(trajectory_converter.to_jsonl(trajectory))

        with open(patch_path, "w") as f:
            f.write(patch)

        metadata = {
            "run_id": run_id,
            "function": func,
            "bug": bug,
            "prompt": task_prompt,
            "trajectory_path": str(traj_path),
            "patch_path": str(patch_path),
            "patch_lines": len(
                [
                    l
                    for l in patch.splitlines()
                    if l.startswith("+") and not l.startswith("+++")
                ]
            ),
            "trajectory_steps": agent_steps,
            "hydron_session_id": result.session_id,
            "self_eval_accepted": True,  # kept for schema compat
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        print(
            f"  OK: {len(trajectory)} entries, {metadata['patch_lines']} patch lines",
            file=sys.stderr,
        )
        return metadata

    finally:
        if owns_container:
            stop_container(container_id)


def main():
    parser = argparse.ArgumentParser(
        description="SERA SVG Rollout 1: Change generation (Hydron)"
    )
    parser.add_argument(
        "--functions", type=Path, required=True, help="Path to functions JSONL"
    )
    parser.add_argument(
        "--bug-prompts", type=Path, required=True, help="Path to bug_prompts.json"
    )
    parser.add_argument(
        "--template", type=Path, required=True, help="Path to bug_prompt_template.txt"
    )
    parser.add_argument(
        "--container",
        type=str,
        default=f"{_DOCKER_IMAGE_PREFIX}:latest",
        help="Docker image name",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/raw"), help="Output directory"
    )
    parser.add_argument(
        "--run-id", type=str, default=None, help="Run ID (default: auto-generated)"
    )
    parser.add_argument(
        "--num-samples", type=int, default=1, help="Number of rollouts to generate"
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Max agent steps per hydron session",
    )
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    functions = load_functions(args.functions)
    bug_prompts = load_bug_prompts(args.bug_prompts)
    template = args.template.read_text()

    print(
        f"Loaded {len(functions)} functions, {len(bug_prompts)} bug types",
        file=sys.stderr,
    )

    results = []
    for i in range(args.num_samples):
        run_id = args.run_id or f"r1_{uuid.uuid4().hex[:8]}"
        if args.num_samples > 1:
            run_id = f"r1_{i:05d}_{uuid.uuid4().hex[:6]}"

        func = random.choice(functions)
        bug = random.choice(bug_prompts)

        for attempt in range(MAX_RETRIES):
            result = run_single(
                func, bug, template, args.container, args.output_dir, run_id,
                max_steps=args.max_steps,
            )
            if result is not None:
                results.append(result)
                break
            bug = random.choice(bug_prompts)
            print(
                f"  Retry {attempt + 1}/{MAX_RETRIES} with bug {bug['bug_id']}",
                file=sys.stderr,
            )

    print(
        f"\nCompleted: {len(results)}/{args.num_samples} successful rollouts",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
