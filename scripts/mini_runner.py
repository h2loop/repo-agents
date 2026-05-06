#!/usr/bin/env python3
"""
Mini-SWE-Agent runner: thin wrapper that drives the mini-swe-agent
DefaultAgent inside an *existing* Docker container, with the same
provider-pool / per-key cooldown / in-flight semaphore behavior we
previously had around hydron.

Used by rollout1.py / rollout2.py for SERA SFT data generation.

Design highlights:
  - One trajectory pins to one provider+model. The provider is picked
    round-robin from the pool when the trajectory starts and never
    changes mid-conversation (per user requirement).
  - Rate limits are handled at the message level, not the trajectory
    level: a single LLM call that hits 429 sleeps and retries with the
    same provider+model, leaving the agent loop's state untouched.
    Concurrent trajectories pinned to the same api_key share the
    cooldown so they back off together.

Environment variables:
  LLM_BASE_URL              - OpenAI-compatible URL (e.g. litellm proxy)
  LLM_API_KEY               - API key for the openai-compat provider
  LLM_MODEL                 - Model id (default qwen/qwen3-coder-...)
  GOOGLE_GENERATIVE_AI_API_KEY_<N> - Google native keys (any number of
                              suffixed entries; legacy GEMINI_API_KEY_<N>
                              also accepted).
  GOOGLE_MODEL              - Model id used with Google keys (default
                              gemini/gemini-2.5-pro).
  BEDROCK_KEY               - AWS Bedrock API key (bearer token). When
                              set, adds a Bedrock provider to the pool.
  BEDROCK_MODEL             - Bedrock model id (default
                              bedrock/converse/zai.glm-4.7).
  AWS_REGION_NAME           - AWS region for Bedrock (default us-east-1).

  PROVIDER_MAX_INFLIGHT     - Max concurrent in-flight LLM calls per
                              api_key (default 8).
  MINI_MSG_RATE_LIMIT_RETRIES - Per-LLM-call retry cap on rate limits
                              within one trajectory (default 10).
  RATE_LIMIT_BASE_BACKOFF   - Initial backoff seconds (default 10).
  RATE_LIMIT_MAX_BACKOFF    - Max single backoff seconds (default 300).

  MINI_STEP_LIMIT           - Default step_limit for AgentConfig (75).
  MINI_COST_LIMIT           - Default cost_limit for AgentConfig (0 =
                              disabled).
  MINI_EXEC_TIMEOUT         - Per-bash-command timeout passed to the
                              docker environment (default 300).
  MINI_MAX_TRAJECTORY_TOKENS - Hard cap on trajectory input tokens. The
                              trajectory is killed and marked failed if
                              the next LLM call would exceed this
                              (default 128000).
  MINI_EXEC_OUTPUT_MAX_BYTES - Hard cap on bytes of stdout/stderr stored
                              in agent.messages per tool call. Larger
                              outputs are head/tail-truncated. Prevents
                              one runaway command (e.g. `find /`) from
                              ballooning a worker's RSS into the GBs
                              (default 32768).
"""

from __future__ import annotations

import itertools
import json
import logging
import os
import random
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Any

import litellm
litellm.modify_params = True
from minisweagent.agents.default import DefaultAgent
from minisweagent.environments.docker import (
    DockerEnvironment,
    DockerEnvironmentConfig,
)
from minisweagent.exceptions import LimitsExceeded
from minisweagent.models.litellm_model import LitellmModel, LitellmModelConfig

# ---------------------------------------------------------------------------
# Provider pool
# ---------------------------------------------------------------------------
# Each Provider is one (kind, key, model) entry. Workers pick providers
# round-robin per *trajectory* and the choice is pinned for that whole
# trajectory. Cooldowns and slot semaphores are keyed by api_key so a
# 429 on one key does not pause workers using a different key.

_GOOGLE_MODEL_RAW = os.getenv("GOOGLE_MODEL") or os.getenv(
    "GEMINI_MODEL", "gemini-2.5-pro"
)
# Two ways to reach Google models with litellm:
#   1. Native: model="gemini/<name>", api_key=<key>.
#   2. OpenAI-compat: model="openai/<name>", api_base=GEMINI_BASE_URL,
#      api_key=<key>. Used when GEMINI_BASE_URL is set (e.g. Google's
#      OpenAI-compatible endpoint at generativelanguage.googleapis.com).
_GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL")
_GOOGLE_USES_OPENAI_COMPAT = bool(_GEMINI_BASE_URL)

# Strip any provider prefix the user may have left in the env value.
_bare_google_model = _GOOGLE_MODEL_RAW
for prefix in ("google/", "gemini/", "openai/"):
    if _bare_google_model.startswith(prefix):
        _bare_google_model = _bare_google_model[len(prefix) :]
        break

if _GOOGLE_USES_OPENAI_COMPAT:
    _GOOGLE_MODEL = f"openai/{_bare_google_model}"
else:
    _GOOGLE_MODEL = f"gemini/{_bare_google_model}"


@dataclass(frozen=True)
class Provider:
    kind: str  # "google_native" | "openai_compat" | "bedrock"
    api_key: str
    model: str
    label: str
    base_url: str | None = None
    aws_region: str | None = None


def _discover_providers() -> list[Provider]:
    providers: list[Provider] = []

    goog_pat = re.compile(r"^(?:GOOGLE_GENERATIVE_AI_API_KEY|GEMINI_API_KEY)_(.+)$")
    seen: set[str] = set()
    entries: list[tuple[str, str]] = []
    for env_name, value in os.environ.items():
        m = goog_pat.match(env_name)
        if not m:
            continue
        key = value.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        entries.append((m.group(1), key))
    entries.sort(key=lambda kv: kv[0])
    for suffix, key in entries:
        providers.append(
            Provider(
                kind="openai_compat" if _GOOGLE_USES_OPENAI_COMPAT else "google_native",
                api_key=key,
                model=_GOOGLE_MODEL,
                label=f"google[{suffix}]",
                base_url=_GEMINI_BASE_URL if _GOOGLE_USES_OPENAI_COMPAT else None,
            )
        )

    lite_url = os.getenv("LLM_BASE_URL")
    lite_key = os.getenv("LLM_API_KEY")
    lite_model_raw = os.getenv("LLM_MODEL", "qwen/qwen3-coder-480b-a35b-instruct-maas")
    if os.getenv("LLM_LITELLM_DISABLED", "0") == "1":
        lite_url = None  # skip the openai-compat litellm provider entirely
    # litellm needs a recognized provider prefix for openai-compat: use
    # `openai/<name>` and pass api_base explicitly.
    lite_model = (
        lite_model_raw if lite_model_raw.startswith("openai/") else f"openai/{lite_model_raw}"
    )
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

    bedrock_key = os.getenv("BEDROCK_KEY") or os.getenv("BEDROCK_TOKEN") or os.getenv("AWS_BEARER_TOKEN_BEDROCK")
    if bedrock_key:
        bedrock_key = bedrock_key.strip()
        os.environ["AWS_BEARER_TOKEN_BEDROCK"] = bedrock_key
        bedrock_model = os.getenv("BEDROCK_MODEL", "bedrock/converse/zai.glm-4.7")
        if not bedrock_model.startswith("bedrock/"):
            bedrock_model = f"bedrock/{bedrock_model}"
        providers.append(
            Provider(
                kind="bedrock",
                api_key=bedrock_key,
                model=bedrock_model,
                label="bedrock-glm",
                aws_region=os.getenv("AWS_REGION_NAME", "us-east-1"),
            )
        )

    if not providers:
        providers.append(
            Provider(
                kind="openai_compat",
                base_url="https://litellm-prod-909645453767.asia-south1.run.app",
                api_key="sk-1234",
                model="openai/qwen/qwen3-coder-480b-a35b-instruct-maas",
                label="litellm-default",
            )
        )

    print(f"[mini] Provider pool: {[p.label for p in providers]}", file=sys.stderr)
    return providers


_PROVIDERS: list[Provider] = _discover_providers()
DEFAULT_MODEL = _PROVIDERS[0].model

_rr_lock = threading.Lock()
_rr_counter = itertools.count()


def pick_provider_for_trajectory() -> Provider:
    """Round-robin across providers not currently on cooldown. Pinned for
    the whole trajectory. Falls back to round-robin over all providers if
    every key is cooling down."""
    now = time.time()
    with _cooldown_lock:
        free = [p for p in _PROVIDERS if _cooldown_until.get(p.api_key, 0.0) <= now]
    pool = free or _PROVIDERS
    with _rr_lock:
        idx = next(_rr_counter)
    return pool[idx % len(pool)]


# ---------------------------------------------------------------------------
# Per-api_key cooldowns + in-flight slots
# ---------------------------------------------------------------------------

PROVIDER_MAX_INFLIGHT = int(os.getenv("PROVIDER_MAX_INFLIGHT", "8"))
MINI_MAX_TRAJECTORY_TOKENS = int(os.getenv("MINI_MAX_TRAJECTORY_TOKENS", "128000"))
MINI_EXEC_OUTPUT_MAX_BYTES = int(os.getenv("MINI_EXEC_OUTPUT_MAX_BYTES", "32768"))


class TrajectoryTooLong(LimitsExceeded):
    """Raised when the conversation token count would exceed
    MINI_MAX_TRAJECTORY_TOKENS. Inherits from LimitsExceeded so mini-swe-agent
    treats it as a terminal limit (no retry)."""

MINI_MSG_RATE_LIMIT_RETRIES = int(os.getenv("MINI_MSG_RATE_LIMIT_RETRIES", "10"))
RATE_LIMIT_BASE_BACKOFF = float(os.getenv("RATE_LIMIT_BASE_BACKOFF", "10"))
RATE_LIMIT_MAX_BACKOFF = float(os.getenv("RATE_LIMIT_MAX_BACKOFF", "300"))

_cooldown_lock = threading.Lock()
_cooldown_until: dict[str, float] = {}

_slots_lock = threading.Lock()
_provider_slots: dict[str, threading.Semaphore] = {
    p.api_key: threading.Semaphore(PROVIDER_MAX_INFLIGHT) for p in _PROVIDERS
}


def _slot_for(api_key: str) -> threading.Semaphore:
    with _slots_lock:
        sem = _provider_slots.get(api_key)
        if sem is None:
            sem = threading.Semaphore(PROVIDER_MAX_INFLIGHT)
            _provider_slots[api_key] = sem
        return sem


def _trigger_cooldown(api_key: str, seconds: float) -> None:
    seconds = min(max(seconds, 0.0), RATE_LIMIT_MAX_BACKOFF)
    until = time.time() + seconds
    with _cooldown_lock:
        cur = _cooldown_until.get(api_key, 0.0)
        if until > cur:
            _cooldown_until[api_key] = until


def _wait_out_cooldown(api_key: str) -> None:
    while True:
        with _cooldown_lock:
            until = _cooldown_until.get(api_key, 0.0)
        remaining = until - time.time()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 5.0))


def _backoff_seconds(attempt: int) -> float:
    base = RATE_LIMIT_BASE_BACKOFF * (2 ** attempt)
    jitter = random.uniform(0, base * 0.25)
    return min(base + jitter, RATE_LIMIT_MAX_BACKOFF)


_RETRY_AFTER_PATTERNS = [
    re.compile(r"retry[\s_-]?after[\"'\s:=]+(\d+(?:\.\d+)?)\s*s?", re.IGNORECASE),
    re.compile(r"retryDelay[\"'\s:=]+(\d+(?:\.\d+)?)\s*s?", re.IGNORECASE),
    re.compile(r"in\s+(\d+(?:\.\d+)?)\s*seconds?", re.IGNORECASE),
]


def _parse_retry_after(text: str) -> float | None:
    if not text:
        return None
    for pat in _RETRY_AFTER_PATTERNS:
        m = pat.search(text)
        if m:
            try:
                v = float(m.group(1))
            except ValueError:
                continue
            if 0 < v <= RATE_LIMIT_MAX_BACKOFF * 2:
                return v
    return None


# ---------------------------------------------------------------------------
# Mini-swe-agent shims: existing-container env + rate-limited model
# ---------------------------------------------------------------------------


class _ExistingDockerEnvironment(DockerEnvironment):
    """DockerEnvironment that attaches to an *existing* container_id instead
    of starting one. The caller (rollout1's ContainerPool) manages container
    lifecycle, so cleanup() is a no-op."""

    def __init__(self, *, existing_container_id: str, **kwargs):
        # Build config without invoking the parent's _start_container.
        self.logger = logging.getLogger("minisweagent.environment")
        self.config = DockerEnvironmentConfig(**kwargs)
        self.container_id = existing_container_id

    def cleanup(self):  # noqa: D401 — caller manages lifecycle
        return

    def __del__(self):
        return

    def execute(self, action: dict, cwd: str = "", *, timeout: int | None = None):
        result = super().execute(action, cwd=cwd, timeout=timeout)
        out = result.get("output") or ""
        cap = MINI_EXEC_OUTPUT_MAX_BYTES
        if cap > 0 and len(out) > cap:
            half = cap // 2
            result["output"] = (
                out[:half]
                + f"\n... [truncated {len(out) - cap} bytes — output exceeded "
                f"MINI_EXEC_OUTPUT_MAX_BYTES={cap}] ...\n"
                + out[-half:]
            )
        return result


class _RateLimitedLitellmModel(LitellmModel):
    """LitellmModel that, on each LLM call:
        1. waits out any active cooldown on its provider's api_key,
        2. acquires the per-key in-flight slot,
        3. retries on RateLimitError with backoff (server hint preferred),
        4. retries the *same* call (no model/provider swap, no trajectory
           abort) up to MINI_MSG_RATE_LIMIT_RETRIES times.
    """

    def __init__(self, *, provider: Provider, **kwargs):
        super().__init__(**kwargs)
        self._provider = provider
        # Treat LimitsExceeded (incl. our TrajectoryTooLong) as terminal so
        # mini-swe-agent's tenacity retry loop does not back-off-and-retry it.
        self.abort_exceptions = list(self.abort_exceptions) + [LimitsExceeded, litellm.BadRequestError]

    def _query(self, messages, **kwargs):
        # Hard cap on trajectory length: count tokens once per outer call
        # (not per retry). If we would exceed the limit, kill the trajectory.
        n_tokens = sum(len(str(m.get("content") or "")) for m in messages) // 4
        if n_tokens > MINI_MAX_TRAJECTORY_TOKENS:
            raise TrajectoryTooLong(
                {
                    "role": "exit",
                    "content": (
                        f"TrajectoryTooLong: {n_tokens} tokens exceeds limit "
                        f"{MINI_MAX_TRAJECTORY_TOKENS}"
                    ),
                    "extra": {"exit_status": "TrajectoryTooLong", "submission": ""},
                }
            )
        api_key = self._provider.api_key
        slot = _slot_for(api_key)
        attempt = 0
        last_err: Exception | None = None
        while attempt <= MINI_MSG_RATE_LIMIT_RETRIES:
            _wait_out_cooldown(api_key)
            slot.acquire()
            try:
                return super()._query(messages, **kwargs)
            except litellm.exceptions.RateLimitError as e:
                last_err = e
                msg = getattr(e, "message", "") or str(e)
                server_hint = _parse_retry_after(msg)
                expo = _backoff_seconds(attempt)
                sleep_s = min(max(server_hint or 0.0, expo), RATE_LIMIT_MAX_BACKOFF)
                hint_note = (
                    f" (server hint: {server_hint:.1f}s)" if server_hint else ""
                )
                print(
                    f"    [mini] rate limit on {self._provider.label} "
                    f"(attempt {attempt + 1}/{MINI_MSG_RATE_LIMIT_RETRIES})"
                    f"{hint_note} — cooling key for {sleep_s:.1f}s",
                    file=sys.stderr,
                )
                _trigger_cooldown(api_key, sleep_s)
                attempt += 1
                continue
            finally:
                slot.release()
        # Bubble up the last RateLimitError after retries exhausted.
        print(
            f"    [mini] rate-limit retries exhausted on {self._provider.label} "
            f"({MINI_MSG_RATE_LIMIT_RETRIES}) — giving up on this message",
            file=sys.stderr,
        )
        assert last_err is not None
        raise last_err


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


@dataclass
class MiniResult:
    """Result of running one mini-swe-agent session.

    `messages` is the full agent.messages list (already in OpenAI tool-calling
    schema: system / user / assistant-with-tool_calls / tool / exit).
    """

    messages: list[dict]
    provider_label: str
    model_name: str
    exit_status: str
    submission: str
    n_calls: int
    cost: float


def _build_litellm_kwargs(provider: Provider) -> dict:
    """Build kwargs for litellm.completion based on provider kind."""
    kwargs: dict[str, Any] = {"model": provider.model}
    if provider.kind == "google_native":
        kwargs["api_key"] = provider.api_key
    elif provider.kind == "bedrock":
        # litellm reads the bearer token from AWS_BEARER_TOKEN_BEDROCK env;
        # it is set at module init when the provider is discovered.
        kwargs["aws_region_name"] = provider.aws_region or "us-east-1"
        kwargs["modify_params"] = True
    else:
        kwargs["api_key"] = provider.api_key
        kwargs["api_base"] = provider.base_url or ""
    return kwargs


# Repo-agnostic SERA system prompt. Kept identical to rollout1.SYSTEM_PROMPT
# so trajectories are consistent across runs. The instance template wraps
# the caller-supplied prompt (which already contains REPO_CONTEXT + task).
_SYSTEM_TEMPLATE = (
    "You are an autonomous coding agent. You have access to a shell and "
    "can run commands, read files, and edit code. Think step by step, "
    "investigate the problem, and make targeted fixes. Always verify your "
    "changes with `git diff` before finishing.\n\n"
    "When you are done, run exactly:\n"
    "    echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n"
    "as a standalone command (no other commands on the same line). After "
    "that the session ends.\n\n"
    "Operating context: {{system}} {{release}} {{machine}}.\n\n"
    "Use the `bash` tool for every action.\n\n"
    "Never `cat` a whole file. Use `grep -n PATTERN file`, "
    "`sed -n 'A,Bp' file`, or pipe through `head`/`tail`. "
    "Keep each command's output under ~100 lines."
)

_INSTANCE_TEMPLATE = (
    "{{task}}\n\n"
    "Workflow:\n"
    "1. Inspect the working directory and the relevant files.\n"
    "2. Make the targeted change.\n"
    "3. Verify with `git diff`.\n"
    "4. Submit by running `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` "
    "as a standalone command."
)


def run_mini_session(
    container_id: str,
    prompt: str,
    repo_path: str = "/repo",
    model: str | None = None,
    max_steps: int | None = None,
    step_limit: int | None = None,
    cost_limit: float | None = None,
    exec_timeout: int | None = None,
) -> MiniResult:
    """Run mini-swe-agent inside an existing Docker container.

    `container_id` is a long-lived container started by rollout1 / rollout2.
    The provider+model is pinned for the whole trajectory.
    """
    provider = pick_provider_for_trajectory()
    if model:
        # Caller-supplied model wins for this trajectory only. We still
        # pin the provider object's kind/api_key/base_url.
        provider = replace(provider, model=model)

    env = _ExistingDockerEnvironment(
        existing_container_id=container_id,
        image="unused",  # required field but ignored since we don't start one
        cwd=repo_path,
        timeout=exec_timeout or int(os.getenv("MINI_EXEC_TIMEOUT", "300")),
    )

    llm_kwargs = _build_litellm_kwargs(provider)
    llm = _RateLimitedLitellmModel(
        provider=provider,
        model_name=llm_kwargs["model"],
        model_kwargs={
            k: v for k, v in llm_kwargs.items() if k != "model"
        }
        | {"drop_params": True},
        cost_tracking="ignore_errors",
    )

    effective_step_limit = (
        step_limit
        if step_limit is not None
        else (max_steps if max_steps is not None else int(os.getenv("MINI_STEP_LIMIT", "75")))
    )
    effective_cost_limit = (
        cost_limit if cost_limit is not None else float(os.getenv("MINI_COST_LIMIT", "0"))
    )

    agent = DefaultAgent(
        model=llm,
        env=env,
        system_template=_SYSTEM_TEMPLATE,
        instance_template=_INSTANCE_TEMPLATE,
        step_limit=effective_step_limit,
        cost_limit=effective_cost_limit,
    )

    print(
        f"    [mini] Running session in {repo_path} via {provider.label} "
        f"({provider.model}) step_limit={effective_step_limit}",
        file=sys.stderr,
    )

    exit_extra: dict = {}
    try:
        exit_extra = agent.run(task=prompt) or {}
    except LimitsExceeded as e:
        # mini raises LimitsExceeded for step/cost limits; the InterruptAgentFlow
        # path normally catches it inside .run(), but this is a safety net.
        exit_extra = {"exit_status": "LimitsExceeded", "submission": ""}
        print(f"    [mini] limits exceeded: {e}", file=sys.stderr)
    except Exception as e:
        # Hard failures bubble out of agent.run(); record what we have.
        import traceback as _tb
        exit_extra = {"exit_status": type(e).__name__, "submission": ""}
        print(f"    [mini] session error: {type(e).__name__}: {e}", file=sys.stderr)
        _tb.print_exc(file=sys.stderr)

    return MiniResult(
        messages=list(agent.messages),
        provider_label=provider.label,
        model_name=provider.model,
        exit_status=exit_extra.get("exit_status", ""),
        submission=exit_extra.get("submission", ""),
        n_calls=agent.n_calls,
        cost=agent.cost,
    )


# ---------------------------------------------------------------------------
# Container helpers
# ---------------------------------------------------------------------------


def docker_exec(container_id: str, cmd: str, timeout: int = 600) -> tuple[str, int]:
    """Execute a shell command inside a Docker container."""
    result = subprocess.run(
        ["docker", "exec", container_id, "bash", "-c", cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if len(output) > 8000:
        output = output[:4000] + "\n... [truncated] ...\n" + output[-4000:]
    return output, result.returncode


def get_patch(container_id: str, repo_path: str = "/repo") -> str:
    """Extract `git diff` from the container's repo."""
    output, _ = docker_exec(container_id, f"cd {repo_path} && git diff", timeout=120)
    return output
