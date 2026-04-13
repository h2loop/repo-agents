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

  Provider pool (a Provider is selected round-robin per session, and
  swapped on rate-limit retries; cooldowns are tracked per-provider so
  a 429 on one key does not pause workers using a different key):

  LLM_BASE_URL              - OpenAI-compatible URL for the litellm provider
  LLM_API_KEY               - API key for the litellm provider
  LLM_MODEL                 - Model ID for the litellm provider
                              (default: qwen/qwen3-coder-480b-a35b-instruct-maas)

  GEMINI_API_KEY_<N>        - Any number of Gemini keys (suffix is free-form,
                              e.g. GEMINI_API_KEY_1, GEMINI_API_KEY_2, ...).
                              Each becomes its own pool entry.
  GEMINI_BASE_URL           - Override for Gemini OpenAI-compatible URL
                              (default: https://generativelanguage.googleapis.com/v1beta/openai/)
  GEMINI_MODEL              - Model ID used with all Gemini keys
                              (default: gemini-3-flash-preview)
"""

from __future__ import annotations

import itertools
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

# ---------------------------------------------------------------------------
# Provider pool
# ---------------------------------------------------------------------------
# Each Provider is one (URL, key, model) triple. Workers pick providers
# round-robin per session and swap on rate-limit retry. Cooldowns are
# tracked per-provider keyed by api_key so a 429 on one Gemini key does
# not pause workers using a different key (or the litellm provider).

_GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
)
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")


@dataclass(frozen=True)
class Provider:
    base_url: str
    api_key: str
    model: str
    label: str  # human-readable, for logs (api_key never logged)


def _discover_providers() -> list[Provider]:
    """Build the provider pool from environment variables.

    Includes:
      - Every GEMINI_API_KEY_<suffix> as its own Gemini provider entry.
      - The litellm provider (LLM_BASE_URL / LLM_API_KEY / LLM_MODEL) if
        an API key is set.
    """
    providers: list[Provider] = []

    # Gemini keys: GEMINI_API_KEY_1, GEMINI_API_KEY_FOO, etc.
    gem_pat = re.compile(r"^GEMINI_API_KEY_(.+)$")
    gem_entries = []
    for env_name, value in os.environ.items():
        m = gem_pat.match(env_name)
        if m and value.strip():
            gem_entries.append((m.group(1), value.strip()))
    # Stable order: lexicographic by suffix, so labels are deterministic.
    gem_entries.sort(key=lambda kv: kv[0])
    for suffix, key in gem_entries:
        providers.append(
            Provider(
                base_url=_GEMINI_BASE_URL,
                api_key=key,
                model=_GEMINI_MODEL,
                label=f"gemini[{suffix}]",
            )
        )

    # Litellm provider, if configured.
    lite_url = os.getenv("LLM_BASE_URL")
    lite_key = os.getenv("LLM_API_KEY")
    lite_model = os.getenv("LLM_MODEL", "qwen/qwen3-coder-480b-a35b-instruct-maas")
    if lite_url and lite_key:
        providers.append(
            Provider(
                base_url=lite_url,
                api_key=lite_key,
                model=lite_model,
                label="litellm",
            )
        )

    if not providers:
        # Fall back to historical defaults so the script still runs in dev.
        providers.append(
            Provider(
                base_url="https://litellm-prod-909645453767.asia-south1.run.app",
                api_key="sk-1234",
                model="qwen/qwen3-coder-480b-a35b-instruct-maas",
                label="litellm-default",
            )
        )

    print(
        f"[hydron] Provider pool: {[p.label for p in providers]}",
        file=sys.stderr,
    )
    return providers


_PROVIDERS: list[Provider] = _discover_providers()
# DEFAULT_MODEL kept for back-compat; first provider's model is used when
# callers don't pass an explicit model override.
DEFAULT_MODEL = _PROVIDERS[0].model

# Round-robin index into _PROVIDERS, advanced atomically.
_rr_lock = threading.Lock()
_rr_counter = itertools.count()


def _next_provider(exclude: set[str] | None = None) -> Provider | None:
    """Return the next provider in round-robin order whose api_key is not
    in `exclude`. Returns None if every provider is excluded."""
    exclude = exclude or set()
    n = len(_PROVIDERS)
    with _rr_lock:
        start = next(_rr_counter)
    for offset in range(n):
        p = _PROVIDERS[(start + offset) % n]
        if p.api_key not in exclude:
            return p
    return None


# ---------------------------------------------------------------------------
# Rate-limit handling (per-provider)
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

# Per-provider cooldown: api_key -> unix-time-when-cooldown-expires.
_cooldown_lock = threading.Lock()
_cooldown_until: dict[str, float] = {}


def _is_rate_limited(text: str) -> bool:
    """Return True if `text` contains a rate-limit signal."""
    if not text:
        return False
    for pat in RATE_LIMIT_PATTERNS:
        if pat.search(text):
            return True
    return False


def _trigger_cooldown(provider: Provider, seconds: float) -> None:
    """Mark a provider as cooling down for at least `seconds`."""
    with _cooldown_lock:
        existing = _cooldown_until.get(provider.api_key, 0.0)
        new_until = time.time() + seconds
        if new_until > existing:
            _cooldown_until[provider.api_key] = new_until


def _cooldown_remaining(provider: Provider) -> float:
    with _cooldown_lock:
        return max(0.0, _cooldown_until.get(provider.api_key, 0.0) - time.time())


def _cooled_down_keys() -> set[str]:
    """Return the set of api_keys currently in cooldown."""
    now = time.time()
    with _cooldown_lock:
        return {k for k, t in _cooldown_until.items() if t > now}


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


def _pick_provider_blocking(exclude: set[str]) -> Provider:
    """Pick the next non-cooling-down provider, waiting if all are cooling.

    `exclude` is the set of api_keys this session has already tried in the
    current retry cycle (so we don't immediately re-pick the one that just
    rate-limited us, even if its cooldown is short).
    """
    # First try to find one not in cooldown and not in exclude.
    cooling = _cooled_down_keys()
    p = _next_provider(exclude=exclude | cooling)
    if p is not None:
        return p

    # Everything we haven't excluded is cooling. Wait for the soonest
    # eligible cooldown to expire.
    while True:
        with _cooldown_lock:
            eligible = [
                (k, t) for k, t in _cooldown_until.items() if k not in exclude
            ]
        if not eligible:
            # All providers excluded — caller has exhausted retries; fall
            # back to plain round-robin (will likely also rate-limit, but
            # this preserves the original "exhausted" path).
            return _next_provider() or _PROVIDERS[0]
        soonest = min(t for _, t in eligible)
        wait = max(0.0, soonest - time.time())
        if wait <= 0:
            break
        print(
            f"    [hydron] all providers cooling down — sleeping {wait:.1f}s",
            file=sys.stderr,
        )
        time.sleep(min(wait, 30))
    cooling = _cooled_down_keys()
    return _next_provider(exclude=exclude | cooling) or _PROVIDERS[0]


def run_hydron_session(
    container_id: str,
    prompt: str,
    model: str | None = None,
    repo_path: str = "/repo",
    max_steps: int | None = None,
) -> HydronResult:
    """Run a hydron agent session inside a Docker container.

    Picks a provider round-robin from the pool. On rate-limit response,
    marks that provider as cooling down and retries with the next provider
    (skipping any others currently in cooldown).

    Args:
        container_id: Docker container ID.
        prompt: The task prompt to send to hydron.
        model: Optional model override. If set, overrides the model from
            whichever provider is chosen.
        repo_path: Working directory inside the container.
        max_steps: Optional max agent steps (passed to --max-steps).

    Returns:
        HydronResult with session_id, events, and exit_code.
    """
    tried: set[str] = set()
    result = None
    chosen: Provider | None = None

    for attempt in range(RATE_LIMIT_MAX_RETRIES + 1):
        chosen = _pick_provider_blocking(exclude=tried)
        active_model = model or chosen.model

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
            chosen.base_url,
            "--provider-key",
            chosen.api_key,
            "--provider-model",
            active_model,
        ]
        if max_steps is not None:
            hydron_cmd.extend(["--max-steps", str(max_steps)])
        hydron_cmd.append(prompt)

        print(
            f"    [hydron] Running session in {repo_path} via {chosen.label} "
            f"({active_model}) attempt {attempt + 1}...",
            file=sys.stderr,
        )

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
            f"    [hydron] rate limit on {chosen.label} (attempt {attempt + 1}/"
            f"{RATE_LIMIT_MAX_RETRIES}) — cooling that key for {sleep_s:.1f}s, "
            f"swapping provider",
            file=sys.stderr,
        )
        _trigger_cooldown(chosen, sleep_s)
        tried.add(chosen.api_key)

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
        timeout=60,
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
            timeout=60,
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
        timeout=60,
    )
    return output
