#!/usr/bin/env python3
"""
Phase 7: Convert filtered trajectories into SFT-ready JSONL format.

Reads the filtered selection from Phase 6 and converts each trajectory into
a multi-turn conversation with metadata, suitable for fine-tuning with
axolotl or similar frameworks.

Output format per line:
{
  "conversations": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."},
    {"role": "tool", "content": "..."},
    ...
  ],
  "metadata": { ... }
}

Usage:
    python scripts/format_for_training.py \
        --selection data/filtered/selected_samples.jsonl \
        --output-dir data/sft_dataset \
        --held-out-ratio 0.10 \
        --max-tokens 32768

Outputs:
    data/sft_dataset/oai5g_train.jsonl
    data/sft_dataset/oai5g_held_out.jsonl
    data/sft_dataset/dataset_stats.json
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# SWE-agent system prompt (must match training format exactly)
# ---------------------------------------------------------------------------
SWE_AGENT_SYSTEM_PROMPT = """\
SETTING: You are an autonomous coding agent working on the OpenAirInterface 5G \
codebase located at /repo. You have access to the following tools:

1. bash - Execute shell commands
   Usage: ```bash
   <command>
   ```

2. str_replace_editor - View and edit files
   Commands:
   - view <path> [line_range]: View file contents
   - str_replace <path> <old_str> <new_str>: Replace text in file
   - create <path> <content>: Create a new file
   - insert <path> <line> <text>: Insert text at line

INSTRUCTIONS:
- Navigate the repository to understand the code structure
- Make targeted changes to fix the issue described
- Test your changes when possible (e.g., gcc -fsyntax-only)
- When finished, output SUBMIT

The repository contains a 5G telecommunications stack implementation in C/C++ \
with subsystems: PHY (openair1), MAC/RLC/PDCP (openair2/LAYER2), RRC (openair2/RRC), \
NAS (openair3/NAS), and supporting infrastructure.
"""


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Rough token estimate."""
    return len(text.split())


def load_trajectory(path: Path) -> list[dict]:
    """Load a JSONL trajectory."""
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def trajectory_to_conversation(
    trajectory: list[dict],
    task_prompt: str | None = None,
    max_tokens: int = 32768,
) -> list[dict[str, str]]:
    """Convert a raw trajectory into a conversation format.

    Returns a list of {"role": ..., "content": ...} messages.
    """
    conversation: list[dict[str, str]] = []

    # System message
    conversation.append({
        "role": "system",
        "content": SWE_AGENT_SYSTEM_PROMPT,
    })

    token_count = estimate_tokens(SWE_AGENT_SYSTEM_PROMPT)

    for entry in trajectory:
        role = entry.get("role", "")
        content = entry.get("content", "")
        reasoning = entry.get("reasoning_content", "")

        if role == "system" and entry == trajectory[0]:
            # Skip the system prompt from trajectory (we added our own)
            continue

        if role == "system" and "Agent submitted" in content:
            # Final submission marker
            conversation.append({
                "role": "assistant",
                "content": "SUBMIT",
            })
            token_count += 1
            continue

        if role == "user":
            # Could be the initial task or a nudge or tool observation
            msg = {"role": "user", "content": content}
            conversation.append(msg)
            token_count += estimate_tokens(content)

        elif role == "assistant":
            # Include reasoning traces (critical per SERA Table 8)
            full_content = ""
            if reasoning:
                full_content += f"<think>\n{reasoning}\n</think>\n\n"
            full_content += content
            msg = {"role": "assistant", "content": full_content}
            conversation.append(msg)
            token_count += estimate_tokens(full_content)

        elif role == "tool":
            # Tool observations become user messages (the "environment" response)
            tool_name = entry.get("tool_name", "unknown")
            tool_args = entry.get("tool_args", {})

            # Format the observation as the agent scaffold would
            obs_content = f"[{tool_name}] {content}"
            msg = {"role": "user", "content": obs_content}
            conversation.append(msg)
            token_count += estimate_tokens(obs_content)

        # Check token budget — truncate from end if over budget
        if token_count > max_tokens:
            # Keep system + first user + as much as fits
            break

    return conversation


def compute_sample_metadata(
    sample_info: dict,
    conversation: list[dict],
) -> dict:
    """Build metadata dict for a training sample."""
    total_tokens = sum(estimate_tokens(m["content"]) for m in conversation)

    return {
        "source": "oai5g_sera",
        "run_id": sample_info.get("run_id", "unknown"),
        "rollout_type": sample_info.get("rollout_type", "unknown"),
        "token_count": total_tokens,
        "num_turns": len(conversation),
        "truncation_ratio": sample_info.get("truncation_ratio"),
        "patch_lines": sample_info.get("patch_lines"),
        "recall_score": sample_info.get("recall_score"),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SERA: Format filtered data for SFT training")
    parser.add_argument("--selection", type=Path, required=True,
                        help="Path to selected_samples.jsonl from filter step")
    parser.add_argument("--output-dir", type=Path, default=Path("data/sft_dataset"))
    parser.add_argument("--held-out-ratio", type=float, default=0.10,
                        help="Fraction of data to hold out for evaluation")
    parser.add_argument("--max-tokens", type=int, default=32768)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load selection
    samples = []
    with open(args.selection) as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    print(f"Loaded {len(samples)} selected samples", file=sys.stderr)

    # Convert each sample
    converted: list[dict] = []
    conversion_errors = 0

    for i, sample_info in enumerate(samples):
        traj_path = Path(sample_info["trajectory_path"])

        if not traj_path.exists():
            conversion_errors += 1
            if conversion_errors <= 5:
                print(f"  Missing trajectory: {traj_path}", file=sys.stderr)
            continue

        try:
            trajectory = load_trajectory(traj_path)
            conversation = trajectory_to_conversation(
                trajectory, max_tokens=args.max_tokens,
            )

            # Skip if conversation is too short (likely failed trajectory)
            if len(conversation) < 4:  # system + user + at least 1 assistant + 1 tool
                conversion_errors += 1
                continue

            metadata = compute_sample_metadata(sample_info, conversation)

            converted.append({
                "conversations": conversation,
                "metadata": metadata,
            })
        except Exception as e:
            conversion_errors += 1
            if conversion_errors <= 5:
                print(f"  Error processing {traj_path}: {e}", file=sys.stderr)

        if (i + 1) % 1000 == 0:
            print(f"  Processed {i+1}/{len(samples)}...", file=sys.stderr)

    print(f"\nConverted {len(converted)} samples ({conversion_errors} errors)", file=sys.stderr)

    # Shuffle and split
    random.shuffle(converted)
    held_out_n = int(len(converted) * args.held_out_ratio)
    held_out = converted[:held_out_n]
    train = converted[held_out_n:]

    # Write outputs
    train_path = args.output_dir / "oai5g_train.jsonl"
    held_out_path = args.output_dir / "oai5g_held_out.jsonl"

    with open(train_path, "w") as f:
        for entry in train:
            f.write(json.dumps(entry) + "\n")

    with open(held_out_path, "w") as f:
        for entry in held_out:
            f.write(json.dumps(entry) + "\n")

    # Compute and save statistics
    token_counts = [e["metadata"]["token_count"] for e in converted]
    turn_counts = [e["metadata"]["num_turns"] for e in converted]
    rollout_types = Counter(e["metadata"]["rollout_type"] for e in converted)

    stats = {
        "total_samples": len(converted),
        "train_samples": len(train),
        "held_out_samples": len(held_out),
        "conversion_errors": conversion_errors,
        "rollout_type_distribution": dict(rollout_types),
        "token_stats": {
            "min": min(token_counts) if token_counts else 0,
            "max": max(token_counts) if token_counts else 0,
            "mean": round(sum(token_counts) / len(token_counts), 1) if token_counts else 0,
            "median": sorted(token_counts)[len(token_counts) // 2] if token_counts else 0,
        },
        "turn_stats": {
            "min": min(turn_counts) if turn_counts else 0,
            "max": max(turn_counts) if turn_counts else 0,
            "mean": round(sum(turn_counts) / len(turn_counts), 1) if turn_counts else 0,
        },
        "max_tokens_config": args.max_tokens,
        "held_out_ratio": args.held_out_ratio,
    }

    stats_path = args.output_dir / "dataset_stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)

    # Summary
    print(f"\nOutputs:", file=sys.stderr)
    print(f"  Train:    {train_path} ({len(train)} samples)", file=sys.stderr)
    print(f"  Held-out: {held_out_path} ({len(held_out)} samples)", file=sys.stderr)
    print(f"  Stats:    {stats_path}", file=sys.stderr)
    print(f"\nToken distribution:", file=sys.stderr)
    print(f"  Min:    {stats['token_stats']['min']}", file=sys.stderr)
    print(f"  Max:    {stats['token_stats']['max']}", file=sys.stderr)
    print(f"  Mean:   {stats['token_stats']['mean']}", file=sys.stderr)
    print(f"  Median: {stats['token_stats']['median']}", file=sys.stderr)


if __name__ == "__main__":
    main()
