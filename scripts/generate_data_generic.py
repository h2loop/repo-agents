#!/usr/bin/env python3
"""
Generic SERA SVG data generation pipeline for any C/C++ repository.

Adapts the OAI5G-specific pipeline to work with arbitrary repos. Each repo
gets its own Docker image, function pool, and output directory.

Usage:
    # Single repo, 1000 samples
    python scripts/generate_data_generic.py \
        --repo-name zephyr \
        --repo-root repos/zephyr \
        --functions data/zephyr/functions.jsonl \
        --bug-prompts configs/bug_prompts_generic.json \
        --template configs/bug_prompt_template.txt \
        --demo-prs-dir configs/demo_prs \
        --output-dir data/zephyr/raw \
        --num-samples 1000 \
        --workers 4

Environment variables:
    LLM_BASE_URL  - LiteLLM proxy URL
    LLM_API_KEY   - API key
    LLM_MODEL     - Model ID
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration from environment
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("LLM_BASE_URL", "https://litellm-prod-909645453767.asia-south1.run.app")
API_KEY = os.getenv("LLM_API_KEY", "sk-1234")
MODEL = os.getenv("LLM_MODEL", "vertex_ai/zai-org/glm-5-maas")

MAX_STEPS = 100
TEMPERATURE = 0.7
MAX_TOKENS_PER_RESPONSE = 4096
MAX_CONSECUTIVE_NUDGES = 3

import ssl
import http.client
import urllib.request
import urllib.error
import urllib.parse
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# Parse proxy host for http.client
_parsed_url = urllib.parse.urlparse(BASE_URL)
_PROXY_HOST = _parsed_url.hostname
_PROXY_PORT = _parsed_url.port or 443

# LLM call timeout — GLM is a reasoning model and can take 2-5 min per call
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "600"))


# ---------------------------------------------------------------------------
# LLM client — streaming via http.client (handles slow reasoning models)
# ---------------------------------------------------------------------------

MAX_RETRIES = 3
RETRY_BACKOFF = 10  # seconds


def chat_completion(messages: list[dict], temperature: float = TEMPERATURE,
                    max_tokens: int = MAX_TOKENS_PER_RESPONSE) -> dict:
    """Call the LLM via the OpenAI-compatible LiteLLM proxy using streaming.

    Uses streaming to avoid socket timeouts with reasoning models (e.g. GLM)
    that spend minutes in the thinking phase before producing output.
    Retries on 5xx errors and timeouts.
    Returns a response dict matching the OpenAI non-streaming format.
    """
    last_err = None
    for attempt in range(MAX_RETRIES):
        if attempt > 0:
            wait = RETRY_BACKOFF * attempt
            print(f"    [retry {attempt}/{MAX_RETRIES}] waiting {wait}s...", file=sys.stderr)
            time.sleep(wait)
        try:
            return _chat_completion_inner(messages, temperature, max_tokens)
        except Exception as e:
            last_err = e
            err_str = str(e)
            # Retry on 5xx, timeout, connection errors
            if any(k in err_str.lower() for k in ("504", "502", "503", "timeout", "connection")):
                continue
            raise  # Non-retryable error
    raise last_err  # type: ignore[misc]


def _chat_completion_inner(messages: list[dict], temperature: float,
                           max_tokens: int) -> dict:
    payload = json.dumps({
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    })

    conn = http.client.HTTPSConnection(_PROXY_HOST, _PROXY_PORT,
                                       context=ssl_ctx, timeout=LLM_TIMEOUT)
    try:
        conn.request("POST", "/v1/chat/completions", body=payload, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        })
        resp = conn.getresponse()
        if resp.status != 200:
            body = resp.read().decode(errors="replace")
            raise RuntimeError(f"LLM API returned {resp.status}: {body[:500]}")

        # Accumulate streamed chunks into a single response
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        finish_reason = None
        model_name = MODEL
        resp_id = ""

        raw = resp.read().decode(errors="replace")
        for line in raw.split("\n"):
            line = line.strip()
            if not line or line == "data: [DONE]":
                continue
            if not line.startswith("data: "):
                continue
            try:
                chunk = json.loads(line[6:])
                resp_id = chunk.get("id", resp_id)
                model_name = chunk.get("model", model_name)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                if delta.get("content"):
                    content_parts.append(delta["content"])
                if delta.get("reasoning_content"):
                    reasoning_parts.append(delta["reasoning_content"])
                fr = chunk.get("choices", [{}])[0].get("finish_reason")
                if fr:
                    finish_reason = fr
            except (json.JSONDecodeError, IndexError, KeyError):
                continue

        # Build a response dict matching the non-streaming format
        return {
            "id": resp_id,
            "model": model_name,
            "choices": [{
                "index": 0,
                "finish_reason": finish_reason,
                "message": {
                    "role": "assistant",
                    "content": "".join(content_parts) or None,
                    "reasoning_content": "".join(reasoning_parts) or None,
                },
            }],
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Docker helpers
# ---------------------------------------------------------------------------

def docker_exec(container_id: str, cmd: str, timeout: int = 30) -> tuple[str, int]:
    result = subprocess.run(
        ["docker", "exec", container_id, "bash", "-c", cmd],
        capture_output=True, text=True, timeout=timeout,
    )
    output = result.stdout + result.stderr
    if len(output) > 8000:
        output = output[:4000] + "\n... [truncated] ...\n" + output[-4000:]
    return output, result.returncode


def start_container(image: str) -> str:
    result = subprocess.run(
        ["docker", "run", "-d", "--rm", image, "sleep", "infinity"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to start container: {result.stderr}")
    return result.stdout.strip()


def stop_container(container_id: str):
    subprocess.run(["docker", "stop", container_id], capture_output=True, timeout=30)


def get_patch(container_id: str) -> str:
    output, _ = docker_exec(container_id, "cd /repo && git diff", timeout=60)
    return output


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

def execute_tool_call(container_id: str, tool_name: str, tool_args: dict) -> str:
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
            return f"Replacement successful in {path}. {output}" if rc == 0 else f"Error: old_str not found in {path}"
        elif command == "create":
            file_text = tool_args.get("file_text", "")
            cmd = f"mkdir -p $(dirname '{path}') && cat > '{path}' << 'SERA_EOF'\n{file_text}\nSERA_EOF"
            output, rc = docker_exec(container_id, cmd, timeout=15)
            return f"File created: {path}" if rc == 0 else f"Error: {output}"
        elif command == "insert":
            insert_line = tool_args.get("insert_line", 0)
            new_str = tool_args.get("new_str", "")
            cmd = f"sed -i '{insert_line}a\\{new_str}' '{path}'"
            output, rc = docker_exec(container_id, cmd, timeout=15)
            return f"Inserted at line {insert_line}" if rc == 0 else f"Error: {output}"
    return f"Unknown tool: {tool_name}"


# ---------------------------------------------------------------------------
# Action parser
# ---------------------------------------------------------------------------

def parse_assistant_action(content: str) -> tuple[str | None, dict | None, str]:
    """Parse the model's output to extract tool calls.

    Handles multiple formats:
    - XML tags: <bash>cmd</bash>, <str_replace_editor>...</str_replace_editor>
    - Markdown fenced blocks: ```bash\ncmd\n```
    - Kimi K2 format: <|tool_call_begin|>...
    - Bare commands: grep ..., find ..., ls ...
    """
    import re

    if "SUBMIT" in content.upper():
        return "submit", {}, content

    # --- XML tag format (Qwen3-Coder style) ---
    # <bash>command</bash>
    m = re.search(r"<[Bb]ash>\s*(.*?)\s*</[Bb]ash>", content, re.DOTALL)
    if m:
        return "bash", {"command": m.group(1).strip()}, content

    # <str_replace_editor> with subcommands
    # GLM outputs many variants:
    #   <str_replace_editor> view /repo/path </str_replace_editor>
    #   <str_replace_editor> view_file path: /repo/path
    #   <str_replace_editor>path /repo/file</str_replace_editor>
    #   <str_replace_editor>/repo/path</str_replace_editor>  (standard)
    str_replace_match = re.search(
        r"<str_replace_editor[^>]*>\s*(.*?)\s*</str_replace_editor>", content, re.DOTALL)
    if str_replace_match:
        inner = str_replace_match.group(1).strip()
        # Check for str_replace with old/new
        old_m = re.search(r"<old_str>\s*(.*?)\s*</old_str>", content, re.DOTALL)
        new_m = re.search(r"<new_str>\s*(.*?)\s*</new_str>", content, re.DOTALL)

        # Extract path from inner text — handle GLM's various formats
        def _extract_path(text):
            """Extract a file path from str_replace_editor inner text."""
            # Try to find a /repo/... path anywhere in the text
            pm = re.search(r"(/repo/\S+)", text)
            if pm:
                return pm.group(1).rstrip(">,;")
            # Try any absolute path
            pm = re.search(r"(/\S+\.\w+)", text)
            if pm:
                return pm.group(1).rstrip(">,;")
            # Try relative path (e.g. "drivers/adc/file.c")
            pm = re.search(r"(\S+/\S+\.\w+)", text)
            if pm:
                p = pm.group(1).rstrip(">,;")
                return f"/repo/{p}" if not p.startswith("/") else p
            # Fallback: strip known keywords, take first token
            cleaned = re.sub(r"^(view_file|view|path:?|<path>|</path>)\s*", "", text, flags=re.IGNORECASE).strip()
            first = cleaned.split()[0] if cleaned.split() else ""
            if first and ("/" in first or "." in first):
                return f"/repo/{first}" if not first.startswith("/") else first
            return None

        if old_m and new_m:
            path = _extract_path(inner) or "/repo/unknown"
            return "str_replace_editor", {
                "command": "str_replace",
                "path": path,
                "old_str": old_m.group(1),
                "new_str": new_m.group(1),
            }, content
        # Check for view_range
        range_m = re.search(r"\[(\d+),\s*(\d+)\]", content)
        path = _extract_path(inner)
        if path:
            if range_m:
                return "str_replace_editor", {
                    "command": "view", "path": path,
                    "view_range": [int(range_m.group(1)), int(range_m.group(2))],
                }, content
            return "str_replace_editor", {"command": "view", "path": path}, content

    # Also handle str_replace_editor without closing tag (GLM sometimes doesn't close)
    str_open_match = re.search(
        r"<str_replace_editor[^>]*>\s*(.*?)$", content, re.DOTALL)
    if str_open_match and not str_replace_match:
        inner = str_open_match.group(1).strip()
        pm = re.search(r"(/repo/\S+|\S+/\S+\.\w+)", inner)
        if pm:
            path = pm.group(1).rstrip(">,;")
            if not path.startswith("/"):
                path = f"/repo/{path}"
            return "str_replace_editor", {"command": "view", "path": path}, content

    # --- Kimi K2 format ---
    m = re.search(
        r"<\|tool_call_begin\|>\s*functions\.(\w+):\d+\s*"
        r"<\|tool_call_argument_begin\|>\s*(\{.*?\})\s*"
        r"<\|tool_call_end\|>", content, re.DOTALL)
    if m:
        try:
            return m.group(1), json.loads(m.group(2)), content
        except json.JSONDecodeError:
            pass

    # --- Markdown fenced bash block ---
    m = re.search(r"```(?:bash|sh|shell)?\s*\n(.+?)```", content, re.DOTALL)
    if m:
        return "bash", {"command": m.group(1).strip()}, content

    # --- Explicit TOOL: bash ---
    m = re.search(r"(?:TOOL|tool):\s*(\w+)", content)
    if m and m.group(1).lower() == "bash":
        cm = re.search(r"(?:COMMAND|command):\s*(.+?)(?:\n|$)", content)
        if cm:
            return "bash", {"command": cm.group(1).strip()}, content

    # --- Bare commands (last resort) ---
    for line in content.strip().split("\n")[-3:]:
        line = line.strip()
        if line.startswith(("grep ", "find ", "ls ", "cat ", "cd ", "head ", "tail ",
                            "sed ", "awk ")):
            return "bash", {"command": line}, content

    return None, None, content


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def run_rollout(container_id: str, prompt: str, system_prompt: str,
                max_steps: int = MAX_STEPS) -> list[dict]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    trajectory = list(messages)
    nudges = 0

    for step in range(max_steps):
        t0 = time.time()
        try:
            response = chat_completion(messages)
        except Exception as e:
            print(f"    step {step}: LLM ERROR after {time.time()-t0:.1f}s — {e}", file=sys.stderr)
            trajectory.append({"role": "error", "content": f"LLM API error: {e}"})
            break

        elapsed = time.time() - t0
        msg = response["choices"][0]["message"]
        content = msg.get("content") or ""
        reasoning = msg.get("reasoning_content") or ""
        effective = content if content.strip() else reasoning

        traj_entry = {"role": "assistant", "content": content, "step": step}
        if reasoning:
            traj_entry["reasoning_content"] = reasoning
        trajectory.append(traj_entry)
        messages.append({"role": "assistant", "content": content or "(thinking...)"})

        tool_name, tool_args, _ = parse_assistant_action(effective)
        snippet = effective[:120].replace('\n', ' ')
        print(f"    step {step} ({elapsed:.0f}s): tool={tool_name or 'NONE'} | {snippet}", file=sys.stderr)

        if tool_name == "submit":
            trajectory.append({"role": "system", "content": "Agent submitted."})
            break

        if tool_name and tool_args:
            try:
                obs = execute_tool_call(container_id, tool_name, tool_args)
            except Exception as e:
                obs = f"Tool execution error: {e}"
            obs_preview = obs[:80].replace('\n', ' ')
            print(f"    step {step} obs: {obs_preview}", file=sys.stderr)
            trajectory.append({"role": "tool", "content": obs, "tool_name": tool_name,
                               "tool_args": tool_args, "step": step})
            messages.append({"role": "user", "content": f"Observation:\n{obs}"})
            nudges = 0
        else:
            nudges += 1
            if nudges >= MAX_CONSECUTIVE_NUDGES:
                trajectory.append({"role": "system", "content": "Agent stuck — aborting."})
                print(f"    step {step}: STUCK — aborting after {MAX_CONSECUTIVE_NUDGES} nudges", file=sys.stderr)
                break
            nudge = ("I didn't detect a tool call. Use <bash>command</bash> "
                     "to run a command, or say SUBMIT if done. "
                     "Only ONE tool call per response.")
            trajectory.append({"role": "user", "content": nudge, "step": step})
            messages.append({"role": "user", "content": nudge})

    return trajectory


# ---------------------------------------------------------------------------
# Self-evaluation
# ---------------------------------------------------------------------------

def self_evaluate(patch: str, original_prompt: str) -> bool:
    if not patch.strip():
        return False
    eval_prompt = (
        f"Task:\n{original_prompt}\n\nPatch:\n```diff\n{patch[:3000]}\n```\n\n"
        "Is this a meaningful, aligned change? Answer YES or NO."
    )
    try:
        resp = chat_completion([{"role": "user", "content": eval_prompt}], temperature=0.0, max_tokens=512)
        msg = resp["choices"][0]["message"]
        content = (msg.get("content") or msg.get("reasoning_content") or "").upper()
        return "YES" in content if content.strip() else True
    except Exception:
        return True


# ---------------------------------------------------------------------------
# PR generation
# ---------------------------------------------------------------------------

def generate_synthetic_pr(trajectory: list[dict], patch: str, demo_pr: str,
                          repo_name: str) -> str:
    parts = []
    for e in trajectory:
        role, content = e.get("role", ""), e.get("content", "")
        if role == "assistant" and content:
            parts.append(f"[Action]: {content[:300]}")
        elif role == "tool" and content:
            parts.append(f"[{e.get('tool_name', 'tool')}]: {content[:200]}")
    summary = "\n".join(parts)[:6000]

    prompt = (
        f"Given this agent trajectory working on the {repo_name} codebase:\n---\n{summary}\n---\n"
        f"Patch:\n```diff\n{patch[:3000]}\n```\n\n"
        f"Example PR:\n---\n{demo_pr}\n---\n\n"
        f"Write a concise PR description (100-300 words) with title, what/why, affected files."
    )
    resp = chat_completion([{"role": "user", "content": prompt}], temperature=0.3, max_tokens=2048)
    msg = resp["choices"][0]["message"]
    return msg.get("content") or msg.get("reasoning_content") or ""


# ---------------------------------------------------------------------------
# Soft verification
# ---------------------------------------------------------------------------

def parse_patch_lines(patch_text: str) -> set[str]:
    changed = set()
    for line in patch_text.splitlines():
        if line.startswith(("+++", "---", "@@", "diff ", "index ")):
            continue
        if line.startswith("+"):
            normalized = " ".join(line[1:].split()).strip()
            if normalized:
                changed.add(normalized)
    return changed


def soft_verify(p1_text: str, p2_text: str) -> dict:
    p1 = parse_patch_lines(p1_text)
    p2 = parse_patch_lines(p2_text)
    intersection = p1 & p2
    score = len(intersection) / len(p1) if p1 else 0.0
    if score >= 1.0:
        cls = "hard_verified"
    elif score >= 0.5:
        cls = "soft_verified"
    elif score > 0:
        cls = "weakly_verified"
    else:
        cls = "unverified"
    return {"recall_score": round(score, 4), "classification": cls,
            "p1_lines": len(p1), "p2_lines": len(p2), "intersection": len(intersection)}


# ---------------------------------------------------------------------------
# Full pipeline for one sample
# ---------------------------------------------------------------------------

def run_full_pipeline(
    sample_id: str,
    func: dict,
    bug: dict,
    template: str,
    container_image: str,
    demo_prs: list[str],
    output_dir: Path,
    repo_name: str,
    repo_description: str,
) -> dict | None:
    # Keep system prompt minimal — GLM is a reasoning model and long prompts
    # cause upstream timeouts (>300s thinking phase)
    tool_usage_guide = (
        "Tools: <bash>cmd</bash> to run shell, "
        "<str_replace_editor>path</str_replace_editor> to view file, "
        "<str_replace_editor>path</str_replace_editor>\n<old_str>old</old_str>\n<new_str>new</new_str> to edit. "
        "Say SUBMIT when done. One tool per response."
    )

    system_prompt = (
        f"Expert C/C++ engineer on {repo_name}. {tool_usage_guide} "
        f"Working dir: /repo."
    )

    r2_system_prompt = (
        f"Expert C/C++ engineer on {repo_name}. {tool_usage_guide} "
        f"Working dir: /repo. Implement the described PR changes."
    )

    prompt = template.format(
        bug_description=bug["description"],
        func_name=func["name"],
        subsystem=func["subsystem"],
        file_path=func["file"],
        start_line=func["start_line"],
    )

    print(f"[{sample_id}] func={func['name']} bug={bug['bug_id']}", file=sys.stderr)

    # --- Rollout 1 ---
    print(f"[{sample_id}] Rollout 1...", file=sys.stderr)
    container_id = start_container(container_image)
    try:
        t1 = run_rollout(container_id, prompt, system_prompt)
        p1 = get_patch(container_id)
    finally:
        stop_container(container_id)

    if not self_evaluate(p1, prompt):
        print(f"[{sample_id}] REJECTED by self-eval", file=sys.stderr)
        return None

    # Save T1/P1
    (output_dir / f"{sample_id}_t1_trajectory.jsonl").write_text(
        "\n".join(json.dumps(e) for e in t1))
    (output_dir / f"{sample_id}_p1.diff").write_text(p1)

    t1_meta = {
        "run_id": sample_id, "function": func, "bug": bug, "prompt": prompt,
        "patch_lines": len([l for l in p1.splitlines() if l.startswith("+") and not l.startswith("+++")]),
        "trajectory_steps": len([e for e in t1 if e["role"] == "assistant"]),
        "self_eval_accepted": True,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (output_dir / f"{sample_id}_t1_meta.json").write_text(json.dumps(t1_meta, indent=2))

    # --- Generate synthetic PR ---
    print(f"[{sample_id}] Generating PR...", file=sys.stderr)
    demo_pr = random.choice(demo_prs) if demo_prs else "No demo PR available."
    try:
        pr_text = generate_synthetic_pr(t1, p1, demo_pr, repo_name)
    except Exception as e:
        print(f"[{sample_id}] PR gen failed: {e}", file=sys.stderr)
        return {"run_id": sample_id, "status": "t1_only", "t1": t1_meta, "t2": None, "verification": None}

    (output_dir / f"{sample_id}_synth_pr.md").write_text(pr_text)

    # --- Rollout 2 ---
    print(f"[{sample_id}] Rollout 2...", file=sys.stderr)
    container_id = start_container(container_image)
    try:
        r2_prompt = f"Please implement the following pull request:\n\n{pr_text}"
        t2 = run_rollout(container_id, r2_prompt, r2_system_prompt)
        p2 = get_patch(container_id)
    except Exception as e:
        print(f"[{sample_id}] R2 failed: {e}", file=sys.stderr)
        stop_container(container_id)
        return {"run_id": sample_id, "status": "t1_only", "t1": t1_meta, "t2": None, "verification": None}
    finally:
        try:
            stop_container(container_id)
        except Exception:
            pass

    # Save T2/P2
    (output_dir / f"{sample_id}_t2_trajectory.jsonl").write_text(
        "\n".join(json.dumps(e) for e in t2))
    (output_dir / f"{sample_id}_p2.diff").write_text(p2)

    t2_meta = {
        "run_id": sample_id,
        "patch_lines": len([l for l in p2.splitlines() if l.startswith("+") and not l.startswith("+++")]),
        "trajectory_steps": len([e for e in t2 if e["role"] == "assistant"]),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (output_dir / f"{sample_id}_t2_meta.json").write_text(json.dumps(t2_meta, indent=2))

    # --- Soft verification ---
    verification = soft_verify(p1, p2)
    (output_dir / f"{sample_id}_verification.json").write_text(json.dumps(verification, indent=2))

    print(f"[{sample_id}] DONE: score={verification['recall_score']:.2f} ({verification['classification']})", file=sys.stderr)

    return {
        "run_id": sample_id, "status": "complete",
        "function": func["name"], "bug_type": bug["bug_id"],
        "subsystem": func["subsystem"],
        "t1": t1_meta, "t2": t2_meta, "verification": verification,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_functions(path: Path) -> list[dict]:
    funcs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                funcs.append(json.loads(line))
    return funcs


def load_bug_prompts(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def load_demo_prs(demo_dir: Path) -> list[str]:
    prs = []
    if demo_dir.is_dir():
        for f in sorted(demo_dir.iterdir()):
            if f.suffix in (".md", ".txt"):
                prs.append(f.read_text(errors="replace"))
    return prs


# ---------------------------------------------------------------------------
# Repo descriptions for system prompts
# ---------------------------------------------------------------------------

REPO_DESCRIPTIONS = {
    "zephyr": (
        "Zephyr is a scalable real-time operating system (RTOS) for connected, resource-constrained devices. "
        "It includes device drivers, HAL, networking (BLE, Wi-Fi, Thread), USB, shell, logging, "
        "and supports multiple architectures (ARM, RISC-V, x86, Xtensa). Code is primarily C."
    ),
    "nuttx": (
        "Apache NuttX is a POSIX-compliant real-time operating system for microcontrollers. "
        "It has arch-specific startup code, board support packages, character/block device drivers, "
        "filesystems, networking (TCP/IP, CAN, I2C, SPI), and scheduling. Pure C codebase."
    ),
    "mbed-os": (
        "ARM Mbed OS is an embedded operating system for ARM Cortex-M microcontrollers. "
        "It includes a hardware abstraction layer (HAL), RTOS primitives, peripheral drivers "
        "(SPI, I2C, UART, CAN, USB), connectivity (BLE, Wi-Fi, cellular), storage, and security. C/C++ codebase."
    ),
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generic SERA SVG data generation")
    parser.add_argument("--repo-name", type=str, required=True, help="Short repo name (e.g. zephyr)")
    parser.add_argument("--repo-root", type=Path, required=True, help="Path to cloned repo")
    parser.add_argument("--functions", type=Path, required=True, help="Extracted functions JSONL")
    parser.add_argument("--bug-prompts", type=Path, required=True, help="Bug prompts JSON")
    parser.add_argument("--template", type=Path, required=True, help="Bug prompt template")
    parser.add_argument("--demo-prs-dir", type=Path, default=Path("configs/demo_prs"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--docker-image", type=str, default=None,
                        help="Docker image name (default: sera-{repo-name}:latest)")
    parser.add_argument("--num-samples", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    docker_image = args.docker_image or f"sera-{args.repo_name}:latest"
    repo_desc = REPO_DESCRIPTIONS.get(args.repo_name, f"A C/C++ codebase ({args.repo_name}).")

    functions = load_functions(args.functions)
    bug_prompts = load_bug_prompts(args.bug_prompts)
    template = args.template.read_text()
    demo_prs = load_demo_prs(args.demo_prs_dir)

    print(f"Configuration:", file=sys.stderr)
    print(f"  Repo:         {args.repo_name}", file=sys.stderr)
    print(f"  Docker:       {docker_image}", file=sys.stderr)
    print(f"  Functions:    {len(functions)}", file=sys.stderr)
    print(f"  Bug types:    {len(bug_prompts)}", file=sys.stderr)
    print(f"  Demo PRs:     {len(demo_prs)}", file=sys.stderr)
    print(f"  Num samples:  {args.num_samples}", file=sys.stderr)
    print(f"  Workers:      {args.workers}", file=sys.stderr)

    # Check resume
    existing = set()
    if args.resume:
        for f in args.output_dir.glob("*_verification.json"):
            existing.add(f.stem.replace("_verification", ""))
        print(f"  Resuming: {len(existing)} already completed", file=sys.stderr)

    # Build sample plan
    plan = []
    for i in range(args.num_samples):
        sid = f"{args.repo_name}_{i:05d}_{uuid.uuid4().hex[:6]}"
        if sid in existing:
            continue
        plan.append((sid, random.choice(functions), random.choice(bug_prompts)))

    random.shuffle(plan)

    manifest = []
    completed = 0
    failed = 0

    if args.workers <= 1:
        for i, (sid, func, bug) in enumerate(plan):
            result = run_full_pipeline(
                sid, func, bug, template, docker_image, demo_prs,
                args.output_dir, args.repo_name, repo_desc,
            )
            if result:
                manifest.append(result)
                completed += 1
            else:
                failed += 1
            if (i + 1) % 10 == 0:
                print(f">>> Progress: {completed} ok, {failed} fail, {i+1}/{len(plan)}", file=sys.stderr)
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for sid, func, bug in plan:
                future = executor.submit(
                    run_full_pipeline,
                    sid, func, bug, template, docker_image, demo_prs,
                    args.output_dir, args.repo_name, repo_desc,
                )
                futures[future] = sid

            for future in as_completed(futures):
                sid = futures[future]
                try:
                    result = future.result()
                    if result:
                        manifest.append(result)
                        completed += 1
                    else:
                        failed += 1
                except Exception as e:
                    print(f"[{sid}] Worker exception: {e}", file=sys.stderr)
                    failed += 1

                if (completed + failed) % 10 == 0:
                    print(f">>> Progress: {completed} ok, {failed} fail", file=sys.stderr)

    # Save manifest
    manifest_path = args.output_dir / "generation_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump({
            "repo": args.repo_name,
            "total_planned": len(plan),
            "completed": completed,
            "failed": failed,
            "t1_only": sum(1 for r in manifest if r.get("status") == "t1_only"),
            "fully_verified": sum(
                1 for r in manifest
                if r.get("verification") and r["verification"].get("classification") in
                ("hard_verified", "soft_verified")
            ),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "samples": manifest,
        }, f, indent=2)

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"[{args.repo_name}] Generation complete!", file=sys.stderr)
    print(f"  Completed: {completed}", file=sys.stderr)
    print(f"  Failed:    {failed}", file=sys.stderr)
    print(f"  Manifest:  {manifest_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
