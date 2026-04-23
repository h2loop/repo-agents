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

  Rate-limit handling (per-provider, multi-worker safe):

  PROVIDER_MAX_INFLIGHT     - Max concurrent hydron sessions per api_key
                              (default 8). Caps load on any single key so
                              20 workers against 1 key don't all 429 at
                              once. Tune up if your provider's limit is
                              high, down if you still see 429s.
  RATE_LIMIT_MAX_RETRIES    - Per-session retry cap on rate limits (5).
  RATE_LIMIT_BASE_BACKOFF   - Initial cooldown on 429, seconds (10).
  RATE_LIMIT_MAX_BACKOFF    - Upper bound on any single cooldown (300).

  On 429 we parse the server's suggested Retry-After / retryDelay from
  hydron's output when available and use max(server_hint, exponential).
  Cooldowns are per-api_key so one key's 429 doesn't pause workers using
  a different key. With only one configured provider, workers wait the
  cooldown and retry instead of bypassing it.

  Provider pool (a Provider is selected round-robin per session, and
  swapped on rate-limit retries as a soft preference; single-provider
  setups fall back to reusing the same key after its cooldown expires):

  LLM_BASE_URL              - OpenAI-compatible URL for the litellm provider
  LLM_API_KEY               - API key for the litellm provider
  LLM_MODEL                 - Model ID for the litellm provider
                              (default: qwen/qwen3-coder-480b-a35b-instruct-maas)

  GOOGLE_GENERATIVE_AI_API_KEY_<N>
                              - Any number of Google keys (suffix is free-form,
                              e.g. GOOGLE_GENERATIVE_AI_API_KEY_1, ...).
                              Each becomes its own Google-native pool entry.
                              Legacy GEMINI_API_KEY_<N> is accepted as an alias.
  GOOGLE_MODEL              - Model ID used with all Google keys, passed to
                              hydron via --model (default: google/gemini-2.5-pro).
                              A bare name without the "google/" prefix is
                              auto-prefixed.
"""

from __future__ import annotations

import itertools
import json
import os
import re
import random
import shutil
import subprocess
import sys
import tempfile
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
# Each Provider is one (kind, key, model) entry. Workers pick providers
# round-robin per session and swap on rate-limit retry. Cooldowns are
# tracked per-provider keyed by api_key so a 429 on one Google key does
# not pause workers using a different key (or the litellm provider).
#
# Two kinds are supported:
#   - google_native:  hydron resolves the provider via --model google/<name>
#                     and reads GOOGLE_GENERATIVE_AI_API_KEY from its env.
#                     base_url is unused.
#   - openai_compat:  hydron is told the URL/key/model explicitly via
#                     --provider-url / --provider-key / --provider-model.

_GOOGLE_MODEL_RAW = os.getenv("GOOGLE_MODEL") or os.getenv(
    "GEMINI_MODEL", "google/gemini-2.5-pro"
)
_GOOGLE_MODEL = (
    _GOOGLE_MODEL_RAW
    if _GOOGLE_MODEL_RAW.startswith("google/")
    else f"google/{_GOOGLE_MODEL_RAW}"
)


@dataclass(frozen=True)
class Provider:
    kind: str  # "google_native" | "openai_compat"
    api_key: str
    model: str
    label: str  # human-readable, for logs (api_key never logged)
    base_url: str | None = None  # only set for openai_compat


def _discover_providers() -> list[Provider]:
    """Build the provider pool from environment variables.

    Includes:
      - Every GOOGLE_GENERATIVE_AI_API_KEY_<suffix> (or legacy
        GEMINI_API_KEY_<suffix>) as its own google-native provider entry.
      - The litellm provider (LLM_BASE_URL / LLM_API_KEY / LLM_MODEL) if
        an API key is set.
    """
    providers: list[Provider] = []

    # Google keys: GOOGLE_GENERATIVE_AI_API_KEY_1, GEMINI_API_KEY_FOO, etc.
    # Dedup by key value so the same secret exported under both names only
    # counts once.
    goog_pat = re.compile(r"^(?:GOOGLE_GENERATIVE_AI_API_KEY|GEMINI_API_KEY)_(.+)$")
    goog_entries: list[tuple[str, str]] = []
    seen_keys: set[str] = set()
    for env_name, value in os.environ.items():
        m = goog_pat.match(env_name)
        if not m:
            continue
        key = value.strip()
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        goog_entries.append((m.group(1), key))
    # Stable order: lexicographic by suffix, so labels are deterministic.
    goog_entries.sort(key=lambda kv: kv[0])
    for suffix, key in goog_entries:
        providers.append(
            Provider(
                kind="google_native",
                api_key=key,
                model=_GOOGLE_MODEL,
                label=f"google[{suffix}]",
            )
        )

    # Litellm provider, if configured.
    lite_url = os.getenv("LLM_BASE_URL")
    lite_key = os.getenv("LLM_API_KEY")
    lite_model = os.getenv("LLM_MODEL", "qwen/qwen3-coder-480b-a35b-instruct-maas")
    if lite_url and lite_key:
        providers.append(
            Provider(
                kind="openai_compat",
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
                kind="openai_compat",
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

HYDRON_SESSION_TIMEOUT = int(os.getenv("HYDRON_SESSION_TIMEOUT", "1200"))  # seconds per hydron session
HYDRON_VARIANT = os.getenv("HYDRON_VARIANT", "low")  # reasoning effort: none, minimal, low, medium, high, xhigh

RATE_LIMIT_MAX_RETRIES = int(os.getenv("RATE_LIMIT_MAX_RETRIES", "5"))
RATE_LIMIT_BASE_BACKOFF = float(os.getenv("RATE_LIMIT_BASE_BACKOFF", "10"))  # seconds
RATE_LIMIT_MAX_BACKOFF = float(os.getenv("RATE_LIMIT_MAX_BACKOFF", "300"))   # 5 min cap

# Max concurrent in-flight hydron sessions per provider (per api_key). Caps
# how many workers can hit the same key simultaneously, which is the single
# most effective lever against 429 cascades when running many workers
# against one or few keys. Default 8 is conservative; bump up if your
# provider's rate limit is high, or down if you still see 429s.
PROVIDER_MAX_INFLIGHT = int(os.getenv("PROVIDER_MAX_INFLIGHT", "8"))

# Per-provider cooldown: api_key -> unix-time-when-cooldown-expires.
_cooldown_lock = threading.Lock()
_cooldown_until: dict[str, float] = {}

# Per-provider in-flight slot semaphores, keyed by api_key. Pre-seeded
# from _PROVIDERS; callers that construct a Provider outside the pool
# (e.g. the predictions runner) get a semaphore created lazily via
# _slot_for.
_slots_lock = threading.Lock()
_provider_slots: dict[str, threading.Semaphore] = {
    p.api_key: threading.Semaphore(PROVIDER_MAX_INFLIGHT) for p in _PROVIDERS
}


def _slot_for(api_key: str) -> threading.Semaphore:
    sem = _provider_slots.get(api_key)
    if sem is not None:
        return sem
    with _slots_lock:
        sem = _provider_slots.get(api_key)
        if sem is None:
            sem = threading.Semaphore(PROVIDER_MAX_INFLIGHT)
            _provider_slots[api_key] = sem
        return sem

# Server-suggested retry-after hints, parsed from hydron's subprocess
# output. Formats vary by provider:
#   - HTTP header style:     "retry-after: 60"
#   - Google gRPC detail:    '"retryDelay": "19s"'
#   - Free-text fallback:    "retry in 30 seconds"
RETRY_AFTER_PATTERNS = [
    re.compile(r'retry[-_ ]after["\':=\s]+(\d+(?:\.\d+)?)', re.IGNORECASE),
    re.compile(r'retrydelay["\':=\s]+"?(\d+(?:\.\d+)?)\s*s?', re.IGNORECASE),
    re.compile(r'retry\s+in\s+(\d+(?:\.\d+)?)\s*s', re.IGNORECASE),
]


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


def _parse_retry_after(text: str) -> float | None:
    """Parse a server-suggested retry-after delay (seconds) from text.

    Returns the parsed value if it's within a sane range, else None. Values
    <=0 or absurdly large (>2x our max backoff) are discarded — we'd rather
    fall back to our own exponential than stall on a malformed suggestion.
    """
    if not text:
        return None
    for pat in RETRY_AFTER_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        try:
            val = float(m.group(1))
        except (ValueError, IndexError):
            continue
        if 0 < val <= RATE_LIMIT_MAX_BACKOFF * 2:
            return val
    return None


def _soonest_cooldown_expiry() -> float | None:
    """Earliest still-active cooldown expiry across all providers, or None."""
    now = time.time()
    with _cooldown_lock:
        active = [t for t in _cooldown_until.values() if t > now]
    return min(active) if active else None


def _pick_provider_with_slot(avoid: set[str] | None = None) -> Provider:
    """Pick a provider with an available in-flight slot and acquire it.

    ``avoid`` is a soft preference — api_keys that rate-limited earlier in
    this session's retry cycle. Pass 1 skips cooling providers and those
    in ``avoid``; Pass 2 relaxes ``avoid`` (but still skips cooling), so
    single-provider callers and "everything tried" cases still make
    progress once cooldowns expire, instead of barrelling through the
    cooldown like the old code did.

    Caller MUST release via ``_release_provider_slot`` when done.

    Blocks indefinitely until a slot is acquired. Waits between passes
    are jittered so many workers waking on the same cooldown expiry don't
    stampede back onto the freshly-uncooled key(s) simultaneously.
    """
    avoid = avoid or set()
    n = len(_PROVIDERS)

    while True:
        cooling = _cooled_down_keys()
        with _rr_lock:
            start = next(_rr_counter)

        # Pass 1: preferred — not cooling, not in avoid.
        for offset in range(n):
            p = _PROVIDERS[(start + offset) % n]
            if p.api_key in cooling or p.api_key in avoid:
                continue
            if _provider_slots[p.api_key].acquire(blocking=False):
                return p

        # Pass 2: relax avoid (still skip cooling). Lets single-provider
        # sessions and multi-provider "all tried" cases proceed once
        # cooldowns have elapsed.
        for offset in range(n):
            p = _PROVIDERS[(start + offset) % n]
            if p.api_key in cooling:
                continue
            if _provider_slots[p.api_key].acquire(blocking=False):
                return p

        # No slot available on any non-cooling provider. Wait before
        # retrying. Cap wait by soonest cooldown expiry so we don't
        # oversleep a recovery; jitter prevents wake-stampede across
        # many workers blocked on the same cooldown.
        soonest = _soonest_cooldown_expiry()
        now = time.time()
        cool_wait = (soonest - now) if soonest is not None else float("inf")
        poll_wait = random.uniform(1.0, 4.0)
        sleep_s = max(0.0, min(cool_wait, poll_wait))
        if sleep_s > 0:
            time.sleep(sleep_s)


def _release_provider_slot(provider: Provider) -> None:
    """Release an in-flight slot previously acquired via _pick_provider_with_slot."""
    sem = _provider_slots.get(provider.api_key)
    if sem is not None:
        sem.release()


def _wait_out_cooldown(provider: Provider) -> None:
    """Block until this provider's cooldown window has elapsed. Jittered so
    many workers waking on the same expiry don't stampede."""
    while True:
        remaining = _cooldown_remaining(provider)
        if remaining <= 0:
            return
        sleep_s = remaining + random.uniform(0, min(2.0, remaining * 0.1 + 0.1))
        print(
            f"    [hydron-host] {provider.label} cooling down; sleeping "
            f"{sleep_s:.1f}s",
            file=sys.stderr,
        )
        time.sleep(sleep_s)


def run_hydron_session_host(
    repo_path: str,
    prompt: str,
    provider: Provider,
    timeout: int = HYDRON_SESSION_TIMEOUT,
    max_steps: int | None = None,
    export_path: Path | None = None,
) -> HydronResult:
    """Run a hydron agent session directly on the host (no Docker).

    Used by the eval predictions runner: `repo_path` is a git worktree at
    the instance's `base_commit`. Provider is explicit (CLI-supplied).

    Rate-limit handling (multi-worker safe):
      - Caps in-flight sessions per api_key via PROVIDER_MAX_INFLIGHT.
      - Honors per-key cooldowns set by sibling workers before starting.
      - On 429 in hydron output, triggers a per-key cooldown (using the
        server's Retry-After hint when parseable) and retries up to
        RATE_LIMIT_MAX_RETRIES times.
    """
    active_model = provider.model
    hydron_cmd_base = [
        HYDRON_HOST_PATH,
        "run",
        "--auto",
        "--skip-auth",
        "--format",
        "json",
        "--dir",
        repo_path,
    ]
    env = os.environ.copy()
    # Per-session fake HOME so each hydron process gets its own
    # ~/.local/share/hydron-cli/kilo.db. Multiple concurrent processes
    # on the shared db produce EBADF / lock contention (hydron resolves
    # the data dir from $HOME, not $XDG_DATA_HOME). Symlink the real
    # ~/.config/hydron-cli so config still loads. Cleaned up below.
    session_home_root = os.getenv("HYDRON_SESSION_HOME_ROOT") or None
    if session_home_root:
        Path(session_home_root).mkdir(parents=True, exist_ok=True)
    session_home = tempfile.mkdtemp(prefix="hydron-home-", dir=session_home_root)
    real_home = os.environ.get("HOME", str(Path.home()))
    real_cfg = Path(real_home) / ".config" / "hydron-cli"
    fake_cfg_parent = Path(session_home) / ".config"
    fake_cfg_parent.mkdir(parents=True, exist_ok=True)
    if real_cfg.exists():
        try:
            os.symlink(real_cfg, fake_cfg_parent / "hydron-cli")
        except FileExistsError:
            pass
    env["HOME"] = session_home
    env.pop("XDG_DATA_HOME", None)
    env.pop("XDG_CONFIG_HOME", None)
    if provider.kind == "google_native":
        hydron_cmd_base.extend(["--model", active_model])
        env["GOOGLE_GENERATIVE_AI_API_KEY"] = provider.api_key
    else:
        hydron_cmd_base.extend(
            [
                "--provider-url",
                provider.base_url or "",
                "--provider-key",
                provider.api_key,
                "--provider-model",
                active_model,
            ]
        )
    if max_steps is not None:
        hydron_cmd_base.extend(["--max-steps", str(max_steps)])
    if HYDRON_VARIANT:
        hydron_cmd_base.extend(["--variant", HYDRON_VARIANT])
    hydron_cmd = hydron_cmd_base + [prompt]

    slot = _slot_for(provider.api_key)
    result = None
    timed_out = False

    try:
        for attempt in range(RATE_LIMIT_MAX_RETRIES + 1):
            _wait_out_cooldown(provider)
            slot.acquire()
            try:
                print(
                    f"    [hydron-host] Running session in {repo_path} via "
                    f"{provider.label} ({active_model}) attempt {attempt + 1}...",
                    file=sys.stderr,
                )
                try:
                    result = subprocess.run(
                        hydron_cmd,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        env=env,
                        stdin=subprocess.DEVNULL,
                    )
                except subprocess.TimeoutExpired:
                    print(
                        f"    [hydron-host] timed out after {timeout}s in {repo_path}",
                        file=sys.stderr,
                    )
                    timed_out = True
                    break
            finally:
                slot.release()

            combined = (result.stdout or "") + "\n" + (result.stderr or "")
            if not _is_rate_limited(combined):
                break

            if attempt >= RATE_LIMIT_MAX_RETRIES:
                print(
                    f"    [hydron-host] rate-limit retries exhausted "
                    f"({RATE_LIMIT_MAX_RETRIES}) on {provider.label} — giving up",
                    file=sys.stderr,
                )
                break

            server_hint = _parse_retry_after(combined)
            expo = _backoff_seconds(attempt)
            sleep_s = min(max(server_hint or 0.0, expo), RATE_LIMIT_MAX_BACKOFF)
            hint_note = f" (server hint: {server_hint:.1f}s)" if server_hint else ""
            print(
                f"    [hydron-host] rate limit on {provider.label} (attempt "
                f"{attempt + 1}/{RATE_LIMIT_MAX_RETRIES}){hint_note} — cooling "
                f"key for {sleep_s:.1f}s",
                file=sys.stderr,
            )
            _trigger_cooldown(provider, sleep_s)

        # Export session JSON before tearing down the fake HOME (kilo.db lives
        # there). Best-effort: a failed export must not fail the run.
        if export_path is not None and not timed_out and result is not None:
            sid = ""
            for line in (result.stdout or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "sessionID" in ev:
                    sid = ev["sessionID"]
                    break
            if sid:
                try:
                    export_path.parent.mkdir(parents=True, exist_ok=True)
                    exp_env = env.copy()
                    with tempfile.TemporaryDirectory() as td:
                        subprocess.run(
                            [HYDRON_HOST_PATH, "session", "export", sid],
                            cwd=td,
                            env=exp_env,
                            capture_output=True,
                            timeout=120,
                            check=True,
                        )
                        produced = Path(td) / f"{sid}.json"
                        if produced.exists():
                            shutil.copyfile(produced, export_path)
                            print(
                                f"    [hydron-host] exported session {sid[:20]}... "
                                f"-> {export_path}",
                                file=sys.stderr,
                            )
                except Exception as e:
                    print(
                        f"    [hydron-host] session export failed: {e}",
                        file=sys.stderr,
                    )
    finally:
        shutil.rmtree(session_home, ignore_errors=True)

    if timed_out:
        return HydronResult(session_id="", events=[], exit_code=-1)

    events: list[dict] = []
    session_id = ""
    for line in (result.stdout or "").splitlines():
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

    print(
        f"    [hydron-host] Session {session_id[:20] if session_id else '???'}"
        f"... completed ({len(events)} events, exit={result.returncode})",
        file=sys.stderr,
    )
    if result.returncode != 0:
        tail_out = (result.stdout or "")[-1500:]
        tail_err = (result.stderr or "")[-1500:]
        if tail_err:
            print(f"    [hydron-host] stderr: {tail_err}", file=sys.stderr)
        if tail_out and not events:
            print(f"    [hydron-host] stdout: {tail_out}", file=sys.stderr)

    return HydronResult(
        session_id=session_id,
        events=events,
        exit_code=result.returncode,
    )


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
        chosen = _pick_provider_with_slot(avoid=tried)
        try:
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
            ]
            env_vars: dict[str, str] | None = None
            if chosen.kind == "google_native":
                # Hydron resolves google via GOOGLE_GENERATIVE_AI_API_KEY;
                # model is passed as `google/<name>` via --model.
                hydron_cmd.extend(["--model", active_model])
                env_vars = {"GOOGLE_GENERATIVE_AI_API_KEY": chosen.api_key}
            else:
                # OpenAI-compatible endpoint (e.g. litellm) — explicit URL/key/model.
                hydron_cmd.extend(
                    [
                        "--provider-url",
                        chosen.base_url or "",
                        "--provider-key",
                        chosen.api_key,
                        "--provider-model",
                        active_model,
                    ]
                )
            if max_steps is not None:
                hydron_cmd.extend(["--max-steps", str(max_steps)])
            if HYDRON_VARIANT:
                hydron_cmd.extend(["--variant", HYDRON_VARIANT])
            hydron_cmd.append(prompt)

            print(
                f"    [hydron] Running session in {repo_path} via {chosen.label} "
                f"({active_model}) attempt {attempt + 1}...",
                file=sys.stderr,
            )

            result = _docker_exec_with_env(
                container_id,
                hydron_cmd,
                env_vars=env_vars,
                timeout=HYDRON_SESSION_TIMEOUT,
            )
        finally:
            _release_provider_slot(chosen)

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

        # Prefer the server's suggested wait if we can parse one out of the
        # output (Google, litellm, and others typically echo retryDelay or
        # Retry-After). Fall back to our exponential. Take the max of the
        # two so we don't under-wait, and clamp to the global max.
        server_hint = _parse_retry_after(combined)
        expo = _backoff_seconds(attempt)
        sleep_s = min(max(server_hint or 0.0, expo), RATE_LIMIT_MAX_BACKOFF)
        hint_note = f" (server hint: {server_hint:.1f}s)" if server_hint else ""
        print(
            f"    [hydron] rate limit on {chosen.label} (attempt {attempt + 1}/"
            f"{RATE_LIMIT_MAX_RETRIES}){hint_note} — cooling that key "
            f"for {sleep_s:.1f}s",
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

    if not session_id and result.returncode != 137:
        # Skip session-list fallback on SIGKILL (exit 137 = OOM / memory cap).
        # The container is stressed post-kill and docker exec will hang.
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
