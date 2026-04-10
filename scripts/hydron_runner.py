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
import subprocess
import sys
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

    result = _docker_exec_with_env(
        container_id,
        hydron_cmd,
        timeout=600,  # 10 min max per session
    )

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
