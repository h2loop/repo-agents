#!/usr/bin/env python3
"""
Phase 5.1: Rollout 1 — Change generation.

Drives the teacher model (Qwen3-Coder-480B via LiteLLM) through SWE-agent
to make a change in the OAI5G codebase starting from a randomly selected
function and bug prompt.

Produces:
  - T1: full agent trajectory (JSONL of messages)
  - P1: unified diff of the change (git diff)

Usage:
    python scripts/rollout1.py \
        --functions data/oai5g_functions.jsonl \
        --bug-prompts configs/bug_prompts.json \
        --template configs/bug_prompt_template.txt \
        --container oai5g-sera:latest \
        --output-dir data/raw \
        --run-id 001

Environment variables:
    LLM_BASE_URL  - LiteLLM proxy URL (default: https://litellm-prod-909645453767.asia-south1.run.app)
    LLM_API_KEY   - API key (default: sk-1234)
    LLM_MODEL     - Model ID (default: zai-org/glm-5-maas)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Repo configuration
# ---------------------------------------------------------------------------
REPO_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "repo_config.json"


def load_repo_config(config_path: Path = REPO_CONFIG_PATH) -> dict:
    """Load repo_config.json if it exists."""
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}


REPO_CFG = load_repo_config()

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("LLM_BASE_URL", "https://litellm-prod-909645453767.asia-south1.run.app")
API_KEY = os.getenv("LLM_API_KEY", "sk-1234")
MODEL = os.getenv("LLM_MODEL", "qwen/qwen3-coder-480b-a35b-instruct-maas")

MAX_STEPS = 50
MAX_RETRIES = 2
TEMPERATURE = 0.7
MAX_TOKENS_PER_RESPONSE = 4096
MAX_CONSECUTIVE_NUDGES = 3  # Early exit if model is stuck

# Repo-specific values from config
_REPO_DISPLAY_NAME = REPO_CFG.get("repo_display_name", "OpenAirInterface 5G")
_REPO_DESCRIPTION = REPO_CFG.get("repo_description", "a 5G telecommunications implementation with PHY, MAC, RLC, PDCP, RRC layers")
_SYSTEM_PROMPT_CONTEXT = REPO_CFG.get("system_prompt_context", "")
_BUILD_CAVEAT = REPO_CFG.get("build_caveat", "")
_CONTAINER_REPO_PATH = REPO_CFG.get("container_repo_path", "/repo")
_DOCKER_IMAGE_PREFIX = REPO_CFG.get("docker_image_prefix", "sera")

# ---------------------------------------------------------------------------
# SWE-agent style system prompt for C/C++ code navigation
# ---------------------------------------------------------------------------
_build_caveat_line = f"\n{_BUILD_CAVEAT}" if _BUILD_CAVEAT else ""
SYSTEM_PROMPT = f"""\
You are an expert C/C++ software engineer working on the {_REPO_DISPLAY_NAME} codebase.
{_SYSTEM_PROMPT_CONTEXT}

Working directory is {_CONTAINER_REPO_PATH}.{_build_caveat_line}

You have tools available: bash (run shell commands) and str_replace_editor (view/edit files).
Before you finish, always run `git diff` to verify your changes were actually applied.
If `git diff` shows no changes, your edits did not take effect — retry.

When you are done, call the submit tool.

Think step by step. First understand the code around the indicated function, then investigate
the potential issue, and finally make a targeted fix.
"""

# Tool schemas for the OpenAI-compatible function calling API
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a shell command in the repository. Use for: grep, find, ls, cat, sed, git diff, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute",
                    }
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "str_replace_editor",
            "description": "View and edit files. Use 'command' to specify the operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["view", "str_replace", "create", "insert"],
                        "description": "The operation: view, str_replace, create, or insert",
                    },
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file",
                    },
                    "view_range": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "[start_line, end_line] for view command (optional)",
                    },
                    "old_str": {
                        "type": "string",
                        "description": "String to replace (for str_replace)",
                    },
                    "new_str": {
                        "type": "string",
                        "description": "Replacement string (for str_replace/insert)",
                    },
                    "insert_line": {
                        "type": "integer",
                        "description": "Line number to insert at (for insert)",
                    },
                    "file_text": {
                        "type": "string",
                        "description": "File contents (for create)",
                    },
                },
                "required": ["command", "path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit",
            "description": "Call this when you are done making changes. Always run `git diff` first to verify your changes were applied.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

def chat_completion(
    messages: list[dict],
    temperature: float = TEMPERATURE,
    max_tokens: int = MAX_TOKENS_PER_RESPONSE,
    tools: list[dict] | None = None,
) -> dict:
    """Call the LLM via the OpenAI-compatible LiteLLM proxy."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        payload["tools"] = tools
    resp = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Docker helpers
# ---------------------------------------------------------------------------

def docker_exec(container_id: str, cmd: str, timeout: int = 30) -> tuple[str, int]:
    """Execute a command inside the running Docker container."""
    result = subprocess.run(
        ["docker", "exec", container_id, "bash", "-c", cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output = result.stdout + result.stderr
    # Truncate very long output
    if len(output) > 8000:
        output = output[:4000] + "\n... [truncated] ...\n" + output[-4000:]
    return output, result.returncode


def start_container(image: str) -> str:
    """Start a Docker container from the given image, return container ID."""
    result = subprocess.run(
        ["docker", "run", "-d", "--rm", image, "sleep", "infinity"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to start container: {result.stderr}")
    return result.stdout.strip()


def stop_container(container_id: str):
    """Stop and remove a Docker container."""
    subprocess.run(
        ["docker", "stop", container_id],
        capture_output=True,
        timeout=30,
    )


def reset_container(container_id: str) -> bool:
    """Reset a container's repo to clean state. Returns True on success."""
    cmd = f"cd {_CONTAINER_REPO_PATH} && git checkout . && git clean -fd"
    _, rc = docker_exec(container_id, cmd, timeout=15)
    return rc == 0


class ContainerPool:
    """Pool of reusable Docker containers to avoid start/stop overhead."""

    def __init__(self, image: str, size: int = 1):
        self.image = image
        self._containers: list[str] = []
        self._lock = __import__("threading").Lock()
        self._sem = __import__("threading").Semaphore(0)
        # Pre-start containers
        for _ in range(size):
            cid = start_container(image)
            self._containers.append(cid)
            self._sem.release()

    def acquire(self, timeout: float = 300) -> str:
        """Get a clean container from the pool. Blocks if none available."""
        if not self._sem.acquire(timeout=timeout):
            raise TimeoutError("No container available in pool")
        with self._lock:
            cid = self._containers.pop(0)
        # Reset to clean state
        if not reset_container(cid):
            # Container is broken — replace it
            try:
                stop_container(cid)
            except Exception:
                pass
            cid = start_container(self.image)
            reset_container(cid)
        return cid

    def release(self, container_id: str):
        """Return a container to the pool."""
        with self._lock:
            self._containers.append(container_id)
        self._sem.release()

    def shutdown(self):
        """Stop all containers in the pool."""
        with self._lock:
            for cid in self._containers:
                try:
                    stop_container(cid)
                except Exception:
                    pass
            self._containers.clear()


def get_patch(container_id: str) -> str:
    """Extract the git diff (patch) from the container."""
    output, _ = docker_exec(container_id, f"cd {_CONTAINER_REPO_PATH} && git diff", timeout=15)
    return output


# ---------------------------------------------------------------------------
# Tool execution (SWE-agent style)
# ---------------------------------------------------------------------------

def execute_tool_call(container_id: str, tool_name: str, tool_args: dict) -> str:
    """Execute a tool call inside the container and return the observation."""
    if tool_name == "bash":
        cmd = tool_args.get("command", "")
        output, rc = docker_exec(container_id, cmd, timeout=60)
        return f"Exit code: {rc}\n{output}"

    elif tool_name == "str_replace_editor":
        command = tool_args.get("command", "view")
        path = tool_args.get("path", "")

        if command == "view":
            view_range = tool_args.get("view_range")
            if view_range:
                start, end = view_range
                cmd = f"sed -n '{start},{end}p' '{path}'"
            else:
                cmd = f"cat -n '{path}' | head -200"
            output, rc = docker_exec(container_id, cmd, timeout=15)
            return output if rc == 0 else f"Error viewing {path}: {output}"

        elif command == "str_replace":
            old_str = tool_args.get("old_str", "")
            new_str = tool_args.get("new_str", "")
            # Use base64 encoding to safely pass strings containing quotes/special chars
            import base64
            old_b64 = base64.b64encode(old_str.encode()).decode()
            new_b64 = base64.b64encode(new_str.encode()).decode()
            py_cmd = (
                f"python3 -c \""
                f"import sys, base64; "
                f"p='{path}'; "
                f"t=open(p).read(); "
                f"old=base64.b64decode('{old_b64}').decode(); "
                f"new=base64.b64decode('{new_b64}').decode(); "
                f"c=t.count(old); "
                f"print(f'Found {{c}} occurrences'); "
                f"open(p,'w').write(t.replace(old,new,1)) if c>0 else sys.exit(1)"
                f"\""
            )
            output, rc = docker_exec(container_id, py_cmd, timeout=15)
            if rc != 0:
                return f"Error: old_str not found in {path}"
            return f"Replacement successful in {path}. {output}"

        elif command == "create":
            file_text = tool_args.get("file_text", "")
            cmd = f"mkdir -p $(dirname '{path}') && cat > '{path}' << 'SERA_EOF'\n{file_text}\nSERA_EOF"
            output, rc = docker_exec(container_id, cmd, timeout=15)
            return f"File created: {path}" if rc == 0 else f"Error creating {path}: {output}"

        elif command == "insert":
            insert_line = tool_args.get("insert_line", 0)
            new_str = tool_args.get("new_str", "")
            cmd = f"sed -i '{insert_line}a\\{new_str}' '{path}'"
            output, rc = docker_exec(container_id, cmd, timeout=15)
            return f"Inserted at line {insert_line} in {path}" if rc == 0 else f"Error: {output}"

    return f"Unknown tool: {tool_name}"


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def parse_assistant_action(content: str) -> tuple[str | None, dict | None, str]:
    """Parse the assistant's response to extract tool calls.

    Returns (tool_name, tool_args, reasoning_text).
    Supports multiple formats:
      - Kimi K2: <|tool_call_begin|> functions.bash:N <|tool_call_argument_begin|> {...} <|tool_call_end|>
      - Markdown: ```bash\n<command>\n```
      - Explicit: TOOL: bash / COMMAND: <cmd>
      - SUBMIT: done signal
    """
    import re

    reasoning = content

    # --- Kimi K2 / Moonshot native tool call format ---
    tool_call_match = re.search(
        r"<\|tool_call_begin\|>\s*functions\.(\w+):\d+\s*"
        r"<\|tool_call_argument_begin\|>\s*(\{.*?\})\s*"
        r"<\|tool_call_end\|>",
        content,
        re.DOTALL,
    )
    if tool_call_match:
        tool_name = tool_call_match.group(1)
        try:
            tool_args = json.loads(tool_call_match.group(2))
        except json.JSONDecodeError:
            tool_args = {}
        if tool_name == "bash":
            return "bash", tool_args, reasoning
        elif tool_name == "str_replace_editor":
            return "str_replace_editor", tool_args, reasoning
        else:
            return tool_name, tool_args, reasoning

    # --- Markdown bash code blocks ---
    # Collect ALL bash blocks and execute sequentially (model often emits multiple)
    bash_matches = re.findall(r"```(?:bash|sh|shell)?\s*\n(.+?)```", content, re.DOTALL)
    if bash_matches:
        cmd = " ; ".join(m.strip() for m in bash_matches)
        # Model sometimes wraps SUBMIT in a bash block — intercept it
        if cmd.strip().upper() == "SUBMIT":
            return "submit", {}, reasoning
        # Model sometimes wraps str_replace_editor calls in a bash block
        if cmd.strip().startswith("str_replace_editor"):
            ste = re.match(
                r"str_replace_editor\s+(str_replace|view|create|insert)\s+(\S+)(.*)",
                cmd.strip(), re.DOTALL,
            )
            if ste:
                subcmd, path = ste.group(1), ste.group(2)
                rest = ste.group(3).strip()
                args: dict = {"command": subcmd, "path": path}
                if subcmd == "str_replace":
                    parts = re.findall(r"'((?:[^'\\]|\\.)*)'", rest)
                    if len(parts) >= 2:
                        args["old_str"] = parts[0]
                        args["new_str"] = parts[1]
                    elif len(parts) == 1:
                        args["old_str"] = parts[0]
                        args["new_str"] = ""
                return "str_replace_editor", args, reasoning
        return "bash", {"command": cmd}, reasoning

    # --- Explicit TOOL: / COMMAND: patterns ---
    tool_match = re.search(r"(?:TOOL|tool):\s*(\w+)", content)
    if tool_match:
        tool = tool_match.group(1).lower()
        if tool == "bash":
            cmd_match = re.search(r"(?:COMMAND|command):\s*(.+?)(?:\n|$)", content)
            if cmd_match:
                return "bash", {"command": cmd_match.group(1).strip()}, reasoning

    # --- Undelimited "bash\n<command>" pattern ---
    # Some models output "bash\n<command>" without triple-backtick fencing.
    undelimited = re.search(r"(?:^|\n)bash\n(.+?)(?:\n\n|\n```|$)", content, re.DOTALL)
    if undelimited:
        cmd = undelimited.group(1).strip()
        # Filter out str_replace_editor invocations mistakenly prefixed with "bash"
        if cmd.startswith("str_replace_editor"):
            # Parse: str_replace_editor str_replace <path> '<old>' '<new>'
            ste = re.match(
                r"str_replace_editor\s+(str_replace|view|create|insert)\s+(\S+)(.*)",
                cmd, re.DOTALL,
            )
            if ste:
                subcmd, path = ste.group(1), ste.group(2)
                rest = ste.group(3).strip()
                args: dict = {"command": subcmd, "path": path}
                if subcmd == "str_replace":
                    # Try to extract old_str / new_str from quoted arguments
                    parts = re.findall(r"'((?:[^'\\]|\\.)*)'", rest)
                    if len(parts) >= 2:
                        args["old_str"] = parts[0]
                        args["new_str"] = parts[1]
                    elif len(parts) == 1:
                        args["old_str"] = parts[0]
                        args["new_str"] = ""
                return "str_replace_editor", args, reasoning
        if cmd:
            return "bash", {"command": cmd}, reasoning

    # --- File viewing patterns ---
    view_match = re.search(r"(?:view|VIEW|View)\s+(?:file\s+)?['\"]?(/[^\s'\"]+)", content)
    if view_match:
        return "str_replace_editor", {"command": "view", "path": view_match.group(1)}, reasoning

    # --- Bare command detection (last resort) ---
    _BARE_PREFIXES = (
        "grep ", "find ", "ls ", "cat ", "cd ", "head ", "tail ",
        "sed ", "awk ", "echo ", "diff ", "patch ", "python3 ", "chmod ",
        "mkdir ", "cp ", "mv ", "rm ", "wc ", "sort ", "uniq ", "xargs ",
    )
    lines = content.strip().split("\n")
    last_lines = [l.strip() for l in lines[-3:] if l.strip()]
    for line in last_lines:
        if line.startswith(_BARE_PREFIXES):
            return "bash", {"command": line}, reasoning

    # Check for SUBMIT only AFTER all tool call formats — the model often mentions
    # SUBMIT in planning text alongside a tool call (e.g. "I'll fix this and SUBMIT"),
    # which was previously short-circuiting execution.
    if "SUBMIT" in content.upper():
        return "submit", {}, reasoning

    # No tool detected — return None to let the model try again
    return None, None, reasoning


def run_rollout(
    container_id: str,
    prompt: str,
    max_steps: int = MAX_STEPS,
) -> list[dict]:
    """Run a single SWE-agent rollout using structured tool calls.

    Returns the trajectory as a list of messages.
    """

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    trajectory: list[dict] = list(messages)

    for step in range(max_steps):
        # Step budget warnings
        if step == max_steps - 10:
            budget_warn = (
                f"You have used {step} of {max_steps} steps. "
                "If you haven't made your code change yet, please make it now."
            )
            trajectory.append({"role": "user", "content": budget_warn, "step": step})
            messages.append({"role": "user", "content": budget_warn})
        elif step == max_steps - 5:
            budget_warn = (
                "5 steps remaining. Please finalize your edit and run `git diff` to verify."
            )
            trajectory.append({"role": "user", "content": budget_warn, "step": step})
            messages.append({"role": "user", "content": budget_warn})

        # Get model response with tool schemas
        try:
            response = chat_completion(messages, tools=TOOL_SCHEMAS)
        except Exception as e:
            trajectory.append({"role": "error", "content": f"LLM API error: {e}"})
            break

        assistant_msg = response["choices"][0]["message"]
        finish_reason = response["choices"][0].get("finish_reason", "")
        content = assistant_msg.get("content") or ""
        reasoning = assistant_msg.get("reasoning_content") or ""
        tool_calls = assistant_msg.get("tool_calls") or []

        # Store full response
        traj_entry = {
            "role": "assistant",
            "content": content,
            "step": step,
        }
        if reasoning:
            traj_entry["reasoning_content"] = reasoning
        if tool_calls:
            traj_entry["tool_calls"] = tool_calls
        trajectory.append(traj_entry)

        # Build the assistant message for the conversation history
        api_assistant_msg: dict = {"role": "assistant"}
        if content:
            api_assistant_msg["content"] = content
        if tool_calls:
            api_assistant_msg["tool_calls"] = tool_calls
        if not content and not tool_calls:
            api_assistant_msg["content"] = "(thinking...)"
        messages.append(api_assistant_msg)

        # --- Handle structured tool calls ---
        if tool_calls:
            for tc in tool_calls:
                func_name = tc["function"]["name"]
                call_id = tc.get("id", f"call_{step}")
                try:
                    func_args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, TypeError):
                    func_args = {}

                if func_name == "submit":
                    # Check for empty patch — give agent a chance to retry
                    patch_check = get_patch(container_id)
                    if not patch_check.strip() and step < max_steps - 1:
                        empty_retries = sum(
                            1 for e in trajectory
                            if e.get("role") == "tool" and "git diff shows no changes" in e.get("content", "")
                        )
                        if empty_retries < 2:
                            retry_msg = (
                                "git diff shows no changes were applied. Your str_replace may have "
                                "failed (old_str not found). Please use `view` to check the current "
                                "file content, then retry your edit. Do NOT submit until git diff "
                                "shows your changes."
                            )
                            print(f"    [step {step}] empty-patch retry ({empty_retries + 1}/2)", file=sys.stderr)
                            # Send tool result back then continue
                            messages.append({"role": "tool", "tool_call_id": call_id, "content": retry_msg})
                            trajectory.append({"role": "tool", "content": retry_msg, "tool_name": "submit", "step": step})
                            continue
                    trajectory.append({"role": "system", "content": "Agent submitted."})
                    return trajectory

                # Execute bash or str_replace_editor
                try:
                    observation = execute_tool_call(container_id, func_name, func_args)
                except Exception as e:
                    observation = f"Tool execution error: {e}"

                obs_entry = {
                    "role": "tool",
                    "content": observation,
                    "tool_name": func_name,
                    "tool_args": func_args,
                    "step": step,
                }
                trajectory.append(obs_entry)
                messages.append({"role": "tool", "tool_call_id": call_id, "content": observation})

        elif content or reasoning:
            # Model produced text without tool calls — fall back to text parsing
            effective_content = content if content.strip() else reasoning
            tool_name, tool_args, _ = parse_assistant_action(effective_content)

            if tool_name == "submit":
                patch_check = get_patch(container_id)
                if not patch_check.strip() and step < max_steps - 1:
                    empty_retries = sum(
                        1 for e in trajectory
                        if e.get("role") == "user" and "git diff shows no changes" in e.get("content", "")
                    )
                    if empty_retries < 2:
                        retry_msg = (
                            "git diff shows no changes were applied. Your str_replace may have "
                            "failed (old_str not found). Please use `view` to check the current "
                            "file content, then retry your edit. Do NOT submit until git diff "
                            "shows your changes."
                        )
                        print(f"    [step {step}] empty-patch retry ({empty_retries + 1}/2)", file=sys.stderr)
                        trajectory.append({"role": "user", "content": retry_msg, "step": step})
                        messages.append({"role": "user", "content": retry_msg})
                        continue
                trajectory.append({"role": "system", "content": "Agent submitted."})
                break

            if tool_name and tool_args:
                try:
                    observation = execute_tool_call(container_id, tool_name, tool_args)
                except Exception as e:
                    observation = f"Tool execution error: {e}"

                obs_entry = {
                    "role": "tool",
                    "content": observation,
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "step": step,
                }
                trajectory.append(obs_entry)
                messages.append({"role": "user", "content": f"Observation:\n{observation}"})
            else:
                # No tool call at all — nudge
                print(f"    [step {step}] no tool call in response", file=sys.stderr)
                nudge = "Please use one of your tools (bash, str_replace_editor, or submit)."
                trajectory.append({"role": "user", "content": nudge, "step": step})
                messages.append({"role": "user", "content": nudge})

    return trajectory


# ---------------------------------------------------------------------------
# Self-evaluation
# ---------------------------------------------------------------------------

def self_evaluate(trajectory: list[dict], patch: str, original_prompt: str) -> bool:
    """Ask the teacher model if the change is aligned with the original prompt.

    Returns True if the change is accepted, False if rejected.
    """
    if not patch.strip():
        return False  # No change made

    eval_prompt = f"""\
An agent was asked to modify C/C++ code near a specific function. Here is the task it was given:
{original_prompt}

The agent produced this patch:
```diff
{patch[:3000]}
```

Does this patch make a substantive, non-trivial code change (not just comments, whitespace, or
formatting)? The change does not need to perfectly match the task — any meaningful code
modification in the target area is acceptable.

Answer with a single word: YES or NO.
"""

    messages = [{"role": "user", "content": eval_prompt}]
    try:
        response = chat_completion(messages, temperature=0.0, max_tokens=1024)
        msg = response["choices"][0]["message"]
        # Prefer content, but fall back to reasoning for thinking models
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""
        # Check content first (definitive answer)
        if content.strip():
            result = "YES" in content.strip().upper()
            print(f"  Self-eval (content): {'YES' if result else 'NO'} — {content.strip()[:120]!r}", file=sys.stderr)
            return result
        # If only reasoning available, look for conclusion patterns
        upper_reasoning = reasoning.upper()
        # Count YES vs NO occurrences — last occurrence wins
        last_yes = upper_reasoning.rfind("YES")
        last_no = upper_reasoning.rfind("NO")
        if last_yes > last_no:
            print(f"  Self-eval (reasoning): YES (last_yes={last_yes} > last_no={last_no})", file=sys.stderr)
            return True
        if last_no > last_yes:
            print(f"  Self-eval (reasoning): NO (last_no={last_no} > last_yes={last_yes})", file=sys.stderr)
            return False
        print(f"  Self-eval: default YES (no YES/NO found in reasoning)", file=sys.stderr)
        return True  # Default: accept
    except Exception:
        return True  # On error, accept by default (conservative)


# ---------------------------------------------------------------------------
# Main
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


def run_single(
    func: dict,
    bug: dict,
    template: str,
    container_image: str,
    output_dir: Path,
    run_id: str,
    container_id: str | None = None,
) -> dict | None:
    """Run a single rollout 1 for one function + bug combination.

    If container_id is provided, uses that container (caller manages lifecycle).
    Otherwise starts and stops its own container.

    Returns metadata dict on success, None on failure.
    """
    prompt = format_prompt(template, func, bug)

    owns_container = container_id is None
    if owns_container:
        print(f"  Starting container {container_image}...", file=sys.stderr)
        container_id = start_container(container_image)

    try:
        # Run the agent
        print(f"  Running rollout for {func['name']} / {bug['bug_id']}...", file=sys.stderr)
        trajectory = run_rollout(container_id, prompt)

        # Extract patch
        patch = get_patch(container_id)

        # Programmatic patch quality check (replaces LLM self-evaluation)
        agent_steps = len([e for e in trajectory if e["role"] == "assistant"])
        patch_len = len(patch.strip())
        if not patch.strip():
            print(f"  REJECTED: empty patch ({agent_steps} agent steps)", file=sys.stderr)
            return None

        # Reject patches that are only comments or whitespace changes
        code_lines = [
            l[1:].strip() for l in patch.splitlines()
            if l.startswith("+") and not l.startswith("+++")
        ]
        substantive = [
            l for l in code_lines
            if l and not l.startswith("//") and not l.startswith("/*")
            and not l.startswith("*") and not l.startswith("#")
        ]
        if not substantive:
            print(f"  REJECTED: comment/whitespace-only patch ({agent_steps} steps, {len(code_lines)} added lines)", file=sys.stderr)
            return None

        # Save artifacts
        traj_path = output_dir / f"{run_id}_t1_trajectory.jsonl"
        patch_path = output_dir / f"{run_id}_p1.diff"
        meta_path = output_dir / f"{run_id}_t1_meta.json"

        with open(traj_path, "w") as f:
            for entry in trajectory:
                f.write(json.dumps(entry) + "\n")

        with open(patch_path, "w") as f:
            f.write(patch)

        metadata = {
            "run_id": run_id,
            "function": func,
            "bug": bug,
            "prompt": prompt,
            "trajectory_path": str(traj_path),
            "patch_path": str(patch_path),
            "patch_lines": len([l for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")]),
            "trajectory_steps": len([e for e in trajectory if e["role"] == "assistant"]),
            "self_eval_accepted": True,  # self-eval gate removed; kept for schema compat
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"  OK: {len(trajectory)} steps, {metadata['patch_lines']} patch lines", file=sys.stderr)
        return metadata

    finally:
        if owns_container:
            stop_container(container_id)


def main():
    parser = argparse.ArgumentParser(description="SERA SVG Rollout 1: Change generation")
    parser.add_argument("--functions", type=Path, required=True, help="Path to oai5g_functions.jsonl")
    parser.add_argument("--bug-prompts", type=Path, required=True, help="Path to bug_prompts.json")
    parser.add_argument("--template", type=Path, required=True, help="Path to bug_prompt_template.txt")
    parser.add_argument("--container", type=str, default=f"{_DOCKER_IMAGE_PREFIX}:latest", help="Docker image name")
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw"), help="Output directory")
    parser.add_argument("--run-id", type=str, default=None, help="Run ID (default: auto-generated UUID)")
    parser.add_argument("--num-samples", type=int, default=1, help="Number of rollouts to generate")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    functions = load_functions(args.functions)
    bug_prompts = load_bug_prompts(args.bug_prompts)
    template = args.template.read_text()

    print(f"Loaded {len(functions)} functions, {len(bug_prompts)} bug types", file=sys.stderr)

    results = []
    for i in range(args.num_samples):
        run_id = args.run_id or f"r1_{uuid.uuid4().hex[:8]}"
        if args.num_samples > 1:
            run_id = f"r1_{i:05d}_{uuid.uuid4().hex[:6]}"

        func = random.choice(functions)
        bug = random.choice(bug_prompts)

        # Retry with different bugs on rejection
        for attempt in range(MAX_RETRIES):
            result = run_single(func, bug, template, args.container, args.output_dir, run_id)
            if result is not None:
                results.append(result)
                break
            bug = random.choice(bug_prompts)  # try different bug
            print(f"  Retry {attempt + 1}/{MAX_RETRIES} with bug {bug['bug_id']}", file=sys.stderr)

    print(f"\nCompleted: {len(results)}/{args.num_samples} successful rollouts", file=sys.stderr)


if __name__ == "__main__":
    main()
