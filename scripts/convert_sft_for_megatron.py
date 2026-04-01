#!/usr/bin/env python3
"""Convert SERA SFT dataset to Megatron-Bridge native tool-call format.

Nemotron's chat template natively handles:
  - role="assistant" with tool_calls=[{function: {name, arguments(dict)}}]
  - role="tool" with content=...

The template renders tool calls as:
  <tool_call>
  <function=bash>
  <parameter=command>find /repo -name foo.c</parameter>
  </function>
  </tool_call>

And tool responses as:
  <|im_start|>user
  <tool_response>...</tool_response>
  <|im_end|>

This script preserves the native structure so apply_chat_template
handles rendering correctly.
"""

import argparse
import json
from pathlib import Path


# Tool schemas for the 3 tools in the dataset
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a bash command in the repository environment",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute",
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
            "description": "View, create, or edit files. Commands: view, str_replace, create, insert, undo_edit",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The editor command: view, str_replace, create, insert, undo_edit",
                    },
                    "path": {
                        "type": "string",
                        "description": "Absolute path to the file or directory",
                    },
                    "old_str": {
                        "type": "string",
                        "description": "String to replace (for str_replace command)",
                    },
                    "new_str": {
                        "type": "string",
                        "description": "Replacement string (for str_replace command)",
                    },
                    "file_text": {
                        "type": "string",
                        "description": "File content (for create command)",
                    },
                    "insert_line": {
                        "type": "integer",
                        "description": "Line number to insert at (for insert command)",
                    },
                    "view_range": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Line range [start, end] (for view command)",
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
            "description": "Submit the current changes as the final patch",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]


def convert_turn(turn: dict) -> dict:
    """Convert a turn to native Nemotron tool-call format."""
    role = turn["role"]
    content = turn.get("content") or ""
    tool_calls = turn.get("tool_calls")

    if role == "assistant" and tool_calls:
        native_calls = []
        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "unknown")
            args_raw = func.get("arguments", "{}")

            # Parse arguments string → dict (template needs dict for |items)
            if isinstance(args_raw, str):
                try:
                    args = json.loads(args_raw)
                except (json.JSONDecodeError, ValueError):
                    args = {"raw": args_raw}
            else:
                args = args_raw

            if not isinstance(args, dict):
                args = {"raw": str(args)}

            native_calls.append({
                "type": "function",
                "function": {"name": name, "arguments": args},
            })

        return {"role": "assistant", "content": content, "tool_calls": native_calls}

    if role == "tool":
        return {"role": "tool", "content": content}

    return {"role": role, "content": content}


def convert_sample(sample: dict) -> dict:
    """Convert a full sample to native format with tool schemas."""
    messages = [convert_turn(t) for t in sample["conversations"]]

    # Merge consecutive same-role turns (only happens with back-to-back tool responses)
    merged = []
    for msg in messages:
        if merged and merged[-1]["role"] == msg["role"] and msg["role"] == "tool":
            merged[-1]["content"] += "\n\n" + msg["content"]
        else:
            merged.append(msg)

    return {"messages": merged, "tools": TOOL_SCHEMAS}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True)
    parser.add_argument("--held-out", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for input_path, output_name in [
        (args.train, "training.jsonl"),
        (args.held_out, "validation.jsonl"),
    ]:
        count = 0
        with open(input_path) as fin, open(out_dir / output_name, "w") as fout:
            for line in fin:
                sample = json.loads(line)
                converted = convert_sample(sample)
                fout.write(json.dumps(converted) + "\n")
                count += 1
        print(f"  {output_name}: {count} samples")

    # Also save tool schemas separately for reference
    with open(out_dir / "tool_schemas.json", "w") as f:
        json.dump(TOOL_SCHEMAS, f, indent=2)
    print(f"  tool_schemas.json: {len(TOOL_SCHEMAS)} tools")

    print(f"\nSaved to {out_dir}/")


if __name__ == "__main__":
    main()
