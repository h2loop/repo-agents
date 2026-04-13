#!/usr/bin/env python3
"""
Hydron runner: subprocess wrapper for running hydron inside Docker containers.

Handles session lifecycle:
  - Run hydron agent sessions inside containers
  - Export session trajectories as JSON
  - Extract git patches from container repos

Environment variables:
  HYDRON_HOST_PATH          - Path to hydron binary on host (default: ./hydron)
  HYDRON_CONTAINER_PATH     - Path inside container (default: /hydron)
  LLM_BASE_URL              - OpenAI-compatible provider URL
  LLM_API_KEY               - API key for the provider
  LLM_MODEL                 - Model ID (default: qwen/qwen3-coder-480b-a35b-instruct-maas)
"""

from __future__ import annotations

import json
import os
import re
import random
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

# Path where hydron binary is mounted inside containers
HYDRON_BIN = os.getenv("HYDRON_CONTAINER_PATH", "/hydron")

# Path to hydron binary on the host (for mounting into containers)
HYDRON_HOST_PATH = os.getenv(
    "HYDRON_HOST_PATH",
    str(Path(__file__).resolve().parent.parent / "hydron"),
)

# LLM provider config — OpenAI-compatible endpoint
LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL", "https://litellm-prod-909645453767.asia-south1.run.app"
)
LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-1234")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "qwen/qwen3-coder-480b-a35b-instruct-maas")

# ---------------------------------------------------------------------------
# Rate-limit handling
# ---------------------------------------------------------------------------
# Hydron is invoked as a subprocess so we cannot intercept HTTP responses.
# Instead we scan the combined stdout/stderr for signals that the upstream
# LLM provider returned a rate-limit error and back off if so.

RATE_LIMIT_PATTERNS = [
    re.compile(r"\b429\b"),
    re.compile(r"too\s+many\s+requests", re.IGNORECASE),
    re.compile(r"rate[\s_-]?limit", re.IGNORECASE),
    re.compile(r"resource[\s_]?exhausted", re.IGNORECASE),
    re.compile(r"quota\s+(?:exceeded|exhausted)", re.IGNORECASE),
    re.compile(r"RateLimitError", re.IGNORECASE),
]

RATE_LIMIT_MAX_RETRIES = int(os.getenv("RATE_LIMIT_MAX_RETRIES", "5"))
RATE_LIMIT_BASE_BACKOFF = float(os.getenv("RATE_LIMIT_BASE_BACKOFF", "10"))  # seconds
RATE_LIMIT_MAX_BACKOFF = float(os.getenv("RATE_LIMIT_MAX_BACKOFF", "300"))   # 5 min cap

# Process-wide cooldown gate so a 429 in one worker pauses all workers.
# Normal state: _cooldown_until = 0 (no cooldown). When set, callers wait
# until time.time() >= _cooldown_until before issuing the next request.
_cooldown_lock = threading.Lock()
_cooldown_until: float = 0.0


def _is_rate_limited(text: str) -> bool:
    """Return True if `text` contains a rate-limit signal."""
    if not text:
        return False
    for pat in RATE_LIMIT_PATTERNS:
        if pat.search(text):
            return True
    return False


def _trigger_cooldown(seconds: float) -> None:
    """Set a global cooldown so all workers pause until it expires."""
    global _cooldown_until
    with _cooldown_lock:
        new_until = time.time() + seconds
        if new_until > _cooldown_until:
            _cooldown_until = new_until


def _wait_for_cooldown() -> None:
    """Block until any active cooldown expires."""
    while True:
        with _cooldown_lock:
            remaining = _cooldown_until - time.time()
        if remaining <= 0:
            return
        print(
            f"    [hydron] rate-limit cooldown active — sleeping {remaining:.1f}s",
            file=sys.stderr,
        )
        time.sleep(min(remaining, 30))


def _backoff_seconds(attempt: int) -> float:
    """Exponential backoff with jitter, capped at RATE_LIMIT_MAX_BACKOFF."""
    base = RATE_LIMIT_BASE_BACKOFF * (2 ** attempt)
    base = min(base, RATE_LIMIT_MAX_BACKOFF)
    return base + random.uniform(0, base * 0.25)


@dataclass
class HydronResult:
    """Result of a hydron session run."""

    session_id: str
    events: list[dict] = field(default_factory=list)
    exit_code: int = 0


def docker_exec(container_id: str, cmd: str, timeout: int = 600) -> tuple[str, int]:
    """Execute a command inside a Docker container."""
    result = subprocess.run(
        ["docker", "exec", container_id, "bash", "-c", cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = result.stdout + result.stderr
    if len(output) > 16000:
        output = output[:8000] + "\n... [truncated] ...\n" + output[-8000:]
    return output, result.returncode


def _docker_exec_with_env(
    container_id: str,
    cmd: list[str],
    env_vars: dict[str, str] | None = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess:
    """Execute a command inside a Docker container with env vars."""
    docker_cmd = ["docker", "exec"]
    for k, v in (env_vars or {}).items():
        docker_cmd.extend(["-e", f"{k}={v}"])
    docker_cmd.append(container_id)
    docker_cmd.extend(cmd)

    return subprocess.run(
        docker_cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_hydron_session(
    container_id: str,
    prompt: str,
    model: str | None = None,
    repo_path: str = "/repo",
    max_steps: int | None = None,
) -> HydronResult:
    """Run a hydron agent session inside a Docker container.

    Args:
        container_id: Docker container ID.
        prompt: The task prompt to send to hydron.
        model: Optional model override (format: provider/model).
        repo_path: Working directory inside the container.
        max_steps: Optional max agent steps (passed to --max-steps).

    Returns:
        HydronResult with session_id, events, and exit_code.
    """
    model = model or DEFAULT_MODEL

    hydron_cmd = [
        HYDRON_BIN,
        "run",
        "--auto",
        "--skip-auth",
        "--format",
        "json",
        "--dir",
        repo_path,
        "--provider-url",
        LLM_BASE_URL,
        "--provider-key",
        LLM_API_KEY,
        "--provider-model",
        model,
    ]

    if max_steps is not None:
        hydron_cmd.extend(["--max-steps", str(max_steps)])

    hydron_cmd.append(prompt)

    print(
        f"    [hydron] Running session in {repo_path} with {model}...",
        file=sys.stderr,
    )

    # Retry loop with rate-limit detection + exponential backoff.
    result = None
    for attempt in range(RATE_LIMIT_MAX_RETRIES + 1):
        _wait_for_cooldown()  # respect global cooldown set by other workers

        result = _docker_exec_with_env(
            container_id,
            hydron_cmd,
            timeout=600,  # 10 min max per session
        )

        combined = (result.stdout or "") + "\n" + (result.stderr or "")
        if not _is_rate_limited(combined):
            break  # success or non-rate-limit failure — leave to downstream

        if attempt >= RATE_LIMIT_MAX_RETRIES:
            print(
                f"    [hydron] rate-limit retries exhausted "
                f"({RATE_LIMIT_MAX_RETRIES}) — giving up on this session",
                file=sys.stderr,
            )
            break

        sleep_s = _backoff_seconds(attempt)
        print(
            f"    [hydron] rate limit detected (attempt {attempt + 1}/"
            f"{RATE_LIMIT_MAX_RETRIES}) — backing off {sleep_s:.1f}s",
            file=sys.stderr,
        )
        _trigger_cooldown(sleep_s)
        time.sleep(sleep_s)

    # Parse JSON events from stdout (one JSON object per line)
    events: list[dict] = []
    session_id = ""
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            events.append(event)
            if "sessionID" in event and not session_id:
                session_id = event["sessionID"]
        except json.JSONDecodeError:
            continue

    if not session_id:
        session_id = _get_latest_session_id(container_id)

    if not session_id:
        print("    [hydron] WARNING: could not determine session ID", file=sys.stderr)
        # Include stderr for debugging
        if result.stderr:
            print(f"    [hydron] stderr: {result.stderr[:500]}", file=sys.stderr)

    print(
        f"    [hydron] Session {session_id[:20] if session_id else '???'}... completed "
        f"({len(events)} events, exit={result.returncode})",
        file=sys.stderr,
    )

    return HydronResult(
        session_id=session_id,
        events=events,
        exit_code=result.returncode,
    )


def _get_latest_session_id(container_id: str) -> str:
    """Get the most recent session ID from hydron session list."""
    output, rc = docker_exec(
        container_id,
        f"{HYDRON_BIN} session list",
        timeout=30,
    )
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("ses_"):
            return line.split()[0]
    return ""


def export_session(container_id: str, session_id: str) -> dict:
    """Export a hydron session as JSON from inside a container.

    Uses docker cp to avoid truncation and control-char issues with piped output.

    Returns:
        Parsed JSON dict with session data including conversations.
    """
    container_path = f"/tmp/{session_id}.json"

    output, rc = docker_exec(
        container_id,
        f"cd /tmp && {HYDRON_BIN} session export {session_id}",
        timeout=30,
    )

    if rc != 0:
        raise RuntimeError(f"hydron session export failed (rc={rc}): {output}")

    # Copy file out of container to avoid truncation/encoding issues
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        local_path = tmp.name

    try:
        result = subprocess.run(
            ["docker", "cp", f"{container_id}:{container_path}", local_path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(f"docker cp failed: {result.stderr}")

        with open(local_path) as f:
            return json.load(f)
    finally:
        os.remove(local_path)
        docker_exec(container_id, f"rm -f {container_path}", timeout=5)


def get_patch(container_id: str, repo_path: str = "/repo") -> str:
    """Extract git diff from the container's repo."""
    output, _ = docker_exec(
        container_id,
        f"cd {repo_path} && git diff",
        timeout=15,
    )
    return output
