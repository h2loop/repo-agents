#!/usr/bin/env python3
"""
Trajectory converter: maps hydron session export JSON to the SERA JSONL format.

Hydron export format (confirmed from real session):
{
  "id": "ses_...",
  "title": "...",
  "conversations": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "", "tool_calls": [
        {"index": 0, "function": {"name": "bash", "arguments": "{\"command\": \"ls\"}"}, "id": "tooluse_...", "type": "function"}
    ]},
    {"role": "tool", "content": "file1\nfile2\n"},
    {"role": "assistant", "content": "Here are the files..."}
  ],
  "tokens": N
}

SERA trajectory JSONL format (one JSON object per line):
{"role": "system", "content": "..."}
{"role": "user", "content": "..."}
{"role": "assistant", "content": "...", "step": 0, "tool_calls": [...]}
{"role": "tool", "content": "...", "tool_name": "bash", "tool_args": {"command": "ls"}, "step": 0}
"""

from __future__ import annotations

import json
import re
from typing import Any


def convert(session_data: dict, system_prompt: str | None = None) -> list[dict]:
    """Convert a hydron session export into SERA trajectory format.

    Args:
        session_data: Parsed JSON from hydron session export.
        system_prompt: Optional system prompt to prepend (for format compatibility).

    Returns:
        List of trajectory entries in SERA JSONL format.
    """
    conversations = session_data.get("conversations", [])
    trajectory: list[dict] = []

    if system_prompt:
        trajectory.append({"role": "system", "content": system_prompt})

    step = 0
    # Track the last assistant's tool_calls so we can annotate tool result messages
    pending_tool_calls: dict[str, dict] = {}  # tool_call_id -> {name, args}

    for msg in conversations:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "system":
            trajectory.append({"role": "system", "content": content})

        elif role == "user":
            trajectory.append({"role": "user", "content": content})

        elif role == "assistant":
            entry: dict[str, Any] = {
                "role": "assistant",
                "content": content,
                "step": step,
            }

            # Extract reasoning/thinking if present
            reasoning = msg.get("reasoning_content") or msg.get("thinking") or ""
            if not reasoning:
                reasoning, content = _extract_thinking(content)
                if reasoning:
                    entry["content"] = content
            if reasoning:
                entry["reasoning_content"] = reasoning

            # Parse tool_calls and build lookup for subsequent tool results
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                entry["tool_calls"] = tool_calls
                pending_tool_calls.clear()
                for tc in tool_calls:
                    tc_id = tc.get("id", "")
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    if tc_id:
                        pending_tool_calls[tc_id] = {"name": name, "args": args}

            trajectory.append(entry)
            step += 1

        elif role == "tool":
            tool_entry: dict[str, Any] = {
                "role": "tool",
                "content": content,
                "step": max(0, step - 1),
            }

            # Look up tool info from the preceding assistant's tool_calls
            tc_id = msg.get("tool_call_id", "")
            if tc_id and tc_id in pending_tool_calls:
                info = pending_tool_calls[tc_id]
                tool_entry["tool_name"] = info["name"]
                tool_entry["tool_args"] = info["args"]
            elif pending_tool_calls:
                # No explicit tool_call_id — use the first (and usually only) pending call
                # then pop it so subsequent tool results get the next one
                first_id = next(iter(pending_tool_calls))
                info = pending_tool_calls.pop(first_id)
                tool_entry["tool_name"] = info["name"]
                tool_entry["tool_args"] = info["args"]

            trajectory.append(tool_entry)

    # Add submission marker if trajectory looks complete
    if any(e.get("role") == "assistant" for e in trajectory):
        trajectory.append({"role": "system", "content": "Agent submitted."})

    return trajectory


def _extract_thinking(content: str) -> tuple[str, str]:
    """Extract <think>...</think> blocks from content.

    Returns (reasoning, cleaned_content).
    """
    pattern = re.compile(r"<think>\s*(.*?)\s*</think>", re.DOTALL)
    matches = pattern.findall(content)
    if matches:
        reasoning = "\n".join(matches)
        cleaned = pattern.sub("", content).strip()
        return reasoning, cleaned
    return "", content


def to_jsonl(trajectory: list[dict]) -> str:
    """Serialize a trajectory to JSONL string."""
    return "\n".join(json.dumps(entry) for entry in trajectory) + "\n"
