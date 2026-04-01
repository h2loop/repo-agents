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
# Configuration from environment
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("LLM_BASE_URL", "https://litellm-prod-909645453767.asia-south1.run.app")
API_KEY = os.getenv("LLM_API_KEY", "sk-1234")
MODEL = os.getenv("LLM_MODEL", "qwen/qwen3-coder-480b-a35b-instruct-maas")

MAX_STEPS = 70
MAX_RETRIES = 2
TEMPERATURE = 0.7
MAX_TOKENS_PER_RESPONSE = 4096
MAX_CONSECUTIVE_NUDGES = 3  # Early exit if model is stuck

# ---------------------------------------------------------------------------
# SWE-agent style system prompt for C/C++ code navigation
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are an expert C/C++ software engineer working on the OpenAirInterface 5G codebase.
You have access to the following tools to navigate and modify the codebase:

1. **bash** - Execute shell commands. Use for: grep, find, ls, gcc -fsyntax-only, etc.
2. **str_replace_editor** - View and edit files. Commands:
   - view: View file contents (with optional line range)
   - str_replace: Replace a specific string in a file
   - create: Create a new file
   - insert: Insert text at a specific line

The codebase is a 5G telecommunications implementation with PHY, MAC, RLC, PDCP, RRC layers.
Working directory is /repo.

When you are done making your changes, output SUBMIT to indicate you are finished.

Think step by step. First understand the code around the indicated function, then investigate
the potential issue, and finally make a targeted fix.
"""


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

def chat_completion(
    messages: list[dict],
    temperature: float = TEMPERATURE,
    max_tokens: int = MAX_TOKENS_PER_RESPONSE,
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


def get_patch(container_id: str) -> str:
    """Extract the git diff (patch) from the container."""
    output, _ = docker_exec(container_id, "cd /repo && git diff", timeout=15)
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

    # Check for SUBMIT
    if "SUBMIT" in content.upper():
        return "submit", {}, reasoning

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
    bash_match = re.search(r"```(?:bash|sh|shell)?\s*\n(.+?)```", content, re.DOTALL)
    if bash_match:
        cmd = bash_match.group(1).strip()
        return "bash", {"command": cmd}, reasoning

    # --- Explicit TOOL: / COMMAND: patterns ---
    tool_match = re.search(r"(?:TOOL|tool):\s*(\w+)", content)
    if tool_match:
        tool = tool_match.group(1).lower()
        if tool == "bash":
            cmd_match = re.search(r"(?:COMMAND|command):\s*(.+?)(?:\n|$)", content)
            if cmd_match:
                return "bash", {"command": cmd_match.group(1).strip()}, reasoning

    # --- File viewing patterns ---
    view_match = re.search(r"(?:view|VIEW|View)\s+(?:file\s+)?['\"]?(/[^\s'\"]+)", content)
    if view_match:
        return "str_replace_editor", {"command": "view", "path": view_match.group(1)}, reasoning

    # --- Bare command detection (last resort) ---
    lines = content.strip().split("\n")
    last_lines = [l.strip() for l in lines[-3:] if l.strip()]
    for line in last_lines:
        if line.startswith(("grep ", "find ", "ls ", "cat ", "cd ", "head ", "tail ")):
            return "bash", {"command": line}, reasoning

    # No tool detected — return None to let the model try again
    return None, None, reasoning


def run_rollout(
    container_id: str,
    prompt: str,
    max_steps: int = MAX_STEPS,
) -> list[dict]:
    """Run a single SWE-agent rollout. Returns the trajectory as a list of messages."""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    trajectory: list[dict] = list(messages)
    consecutive_nudges = 0

    for step in range(max_steps):
        # Get model response
        try:
            response = chat_completion(messages)
        except Exception as e:
            trajectory.append({"role": "error", "content": f"LLM API error: {e}"})
            break

        assistant_msg = response["choices"][0]["message"]
        content = assistant_msg.get("content") or ""
        reasoning = assistant_msg.get("reasoning_content") or ""

        # If content is empty but reasoning exists, use reasoning for action parsing
        # Kimi K2 thinking model may put actions in content after reasoning
        effective_content = content if content.strip() else reasoning

        # Store full response including reasoning
        traj_entry = {
            "role": "assistant",
            "content": content,
            "step": step,
        }
        if reasoning:
            traj_entry["reasoning_content"] = reasoning
        trajectory.append(traj_entry)
        messages.append({"role": "assistant", "content": content or "(thinking...)"})

        # Parse action from content (preferred) or reasoning (fallback)
        tool_name, tool_args, _ = parse_assistant_action(effective_content)

        if tool_name == "submit":
            trajectory.append({"role": "system", "content": "Agent submitted."})
            break

        if tool_name and tool_args:
            # Execute tool
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
            consecutive_nudges = 0
        else:
            # No tool parsed — nudge the model
            consecutive_nudges += 1
            if consecutive_nudges >= MAX_CONSECUTIVE_NUDGES:
                trajectory.append({"role": "system", "content": "Agent stuck — aborting."})
                break
            nudge = (
                "I didn't detect a tool call in your response. "
                "Please use a bash command block (```bash\\n<command>\\n```) "
                "or say SUBMIT if you are done."
            )
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
You were given this task:
{original_prompt}

The agent produced this patch:
```diff
{patch[:3000]}
```

Does this patch represent a meaningful and aligned change related to the task description?
Answer YES if the change is relevant (even if imperfect), or NO if it is completely unrelated
or trivially empty.

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
            return "YES" in content.strip().upper()
        # If only reasoning available, look for conclusion patterns
        upper_reasoning = reasoning.upper()
        # Count YES vs NO occurrences — last occurrence wins
        last_yes = upper_reasoning.rfind("YES")
        last_no = upper_reasoning.rfind("NO")
        if last_yes > last_no:
            return True
        if last_no > last_yes:
            return False
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
) -> dict | None:
    """Run a single rollout 1 for one function + bug combination.

    Returns metadata dict on success, None on failure.
    """
    prompt = format_prompt(template, func, bug)

    # Start container
    print(f"  Starting container {container_image}...", file=sys.stderr)
    container_id = start_container(container_image)

    try:
        # Run the agent
        print(f"  Running rollout for {func['name']} / {bug['bug_id']}...", file=sys.stderr)
        trajectory = run_rollout(container_id, prompt)

        # Extract patch
        patch = get_patch(container_id)

        # Self-evaluation
        accepted = self_evaluate(trajectory, patch, prompt)
        if not accepted:
            print(f"  REJECTED by self-evaluation", file=sys.stderr)
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
            "self_eval_accepted": True,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"  OK: {len(trajectory)} steps, {metadata['patch_lines']} patch lines", file=sys.stderr)
        return metadata

    finally:
        stop_container(container_id)


def main():
    parser = argparse.ArgumentParser(description="SERA SVG Rollout 1: Change generation")
    parser.add_argument("--functions", type=Path, required=True, help="Path to oai5g_functions.jsonl")
    parser.add_argument("--bug-prompts", type=Path, required=True, help="Path to bug_prompts.json")
    parser.add_argument("--template", type=Path, required=True, help="Path to bug_prompt_template.txt")
    parser.add_argument("--container", type=str, default="oai5g-sera:latest", help="Docker image name")
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
