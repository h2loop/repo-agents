#!/usr/bin/env python3
"""
Post-process SWE-agent outputs into SFT training data.

Reads stage 1 + stage 2 SWE-agent trajectories, applies SERA-style filtering,
and formats into conversation-style SFT dataset (JSONL).

Combines both T1 (unverified rollout 1) and T2 (verified rollout 2) trajectories.
"""

import json
import os
import sys
import yaml
from collections import Counter
from pathlib import Path
from argparse import ArgumentParser


def load_sweagent_trajectory(traj_dir: Path, instance_id: str) -> list[dict] | None:
    """Load a SWE-agent trajectory from its output directory.

    Uses 'history' (role/content conversation format) rather than
    'trajectory' (action/observation step format).
    """
    traj_file = traj_dir / instance_id / f"{instance_id}.traj"
    if not traj_file.exists():
        return None
    try:
        with open(traj_file) as f:
            traj_data = json.load(f)
        return traj_data.get("history", [])
    except Exception:
        return None


def load_sweagent_patch(traj_dir: Path, instance_id: str) -> str | None:
    """Load the model patch from SWE-agent output."""
    pred_file = traj_dir / instance_id / f"{instance_id}.pred"
    if not pred_file.exists():
        return None
    try:
        with open(pred_file) as f:
            return json.load(f).get("model_patch", "")
    except Exception:
        return None


def estimate_tokens(text: str) -> int:
    return len(text.split())


def _extract_text(content) -> str:
    """Extract text from content which may be a string or list of dicts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content) if content else ""


def trajectory_to_conversation(history: list[dict]) -> list[dict]:
    """Convert a SWE-agent history into a conversation format for SFT."""
    messages = []

    for step in history:
        role = step.get("role", "")
        content = _extract_text(step.get("content", ""))
        if not content:
            continue

        if role == "system":
            messages.append({"role": "system", "content": content})
        elif role == "user":
            messages.append({"role": "user", "content": content})
        elif role == "assistant":
            msg = {"role": "assistant", "content": content}
            if step.get("tool_calls"):
                msg["tool_calls"] = step["tool_calls"]
            messages.append(msg)
        elif role == "tool":
            messages.append({"role": "tool", "content": content})

    return messages


def main():
    parser = ArgumentParser()
    parser.add_argument("--stage-one-output", type=Path, required=True)
    parser.add_argument("--stage-two-output", type=Path, required=True)
    parser.add_argument("--verification-dir", type=Path, required=True)
    parser.add_argument("--stage-one-instances", type=Path, required=True)
    parser.add_argument("--stage-two-instances", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-patch-lines", type=int, default=40)
    parser.add_argument("--max-tokens", type=int, default=32768)
    parser.add_argument("--min-recall", type=float, default=0.5)
    parser.add_argument("--train-ratio", type=float, default=0.9)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load verification results
    verif_results = {}
    verif_file = args.verification_dir / "verification_results.jsonl"
    if verif_file.exists():
        with open(verif_file) as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    verif_results[r["instance_id"]] = r

    # Load instances
    with open(args.stage_one_instances) as f:
        s1_instances = yaml.safe_load(f) or []

    s2_instances = []
    if args.stage_two_instances.exists():
        with open(args.stage_two_instances) as f:
            s2_instances = yaml.safe_load(f) or []

    stats = Counter()
    all_samples = []

    # Process stage 1 (T1) trajectories
    print("Processing stage 1 trajectories...")
    for inst in s1_instances:
        inst_id = inst["id"]
        stats["s1_total"] += 1

        patch = load_sweagent_patch(args.stage_one_output, inst_id)
        if not patch:
            stats["s1_no_patch"] += 1
            continue

        patch_lines = len([l for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")])
        if patch_lines == 0:
            stats["s1_empty_patch"] += 1
            continue
        if patch_lines > args.max_patch_lines:
            stats["s1_patch_too_large"] += 1
            continue

        # Check self-eval from .synth file
        synth_file = args.stage_one_output / inst_id / f"{inst_id}.synth"
        if synth_file.exists():
            try:
                with open(synth_file) as f:
                    synth = json.load(f)
                if not synth.get("is_good_patch"):
                    stats["s1_self_eval_rejected"] += 1
                    continue
            except Exception:
                pass

        traj = load_sweagent_trajectory(args.stage_one_output, inst_id)
        if not traj:
            stats["s1_no_traj"] += 1
            continue

        # Token filter
        total_tokens = sum(estimate_tokens(_extract_text(s.get("content", ""))) for s in traj)
        if total_tokens > args.max_tokens:
            stats["s1_too_long"] += 1
            continue

        conversation = trajectory_to_conversation(traj)
        all_samples.append({
            "id": inst_id,
            "rollout_type": "T1",
            "conversations": conversation,
            "patch": patch,
            "patch_lines": patch_lines,
            "tokens": total_tokens,
        })
        stats["s1_passed"] += 1

    # Process stage 2 (T2) trajectories
    print("Processing stage 2 trajectories...")
    for inst in s2_instances:
        inst_id = inst["id"]
        stats["s2_total"] += 1

        # Check verification
        verif = verif_results.get(inst_id)
        if not verif or verif.get("recall_score", 0) < args.min_recall:
            stats["s2_low_recall"] += 1
            continue

        patch = load_sweagent_patch(args.stage_two_output, inst_id)
        if not patch:
            stats["s2_no_patch"] += 1
            continue

        patch_lines = len([l for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")])
        if patch_lines == 0:
            stats["s2_empty_patch"] += 1
            continue
        if patch_lines > args.max_patch_lines:
            stats["s2_patch_too_large"] += 1
            continue

        traj = load_sweagent_trajectory(args.stage_two_output, inst_id)
        if not traj:
            stats["s2_no_traj"] += 1
            continue

        total_tokens = sum(estimate_tokens(_extract_text(s.get("content", ""))) for s in traj)
        if total_tokens > args.max_tokens:
            stats["s2_too_long"] += 1
            continue

        conversation = trajectory_to_conversation(traj)
        all_samples.append({
            "id": inst_id,
            "rollout_type": "T2",
            "conversations": conversation,
            "patch": patch,
            "patch_lines": patch_lines,
            "tokens": total_tokens,
            "recall_score": verif["recall_score"],
        })
        stats["s2_passed"] += 1

    # Split train/held-out
    import random
    random.seed(42)
    random.shuffle(all_samples)

    split_idx = int(len(all_samples) * args.train_ratio)
    train_samples = all_samples[:split_idx]
    held_out_samples = all_samples[split_idx:]

    # Save
    train_file = args.output_dir / "oai5g_train.jsonl"
    held_out_file = args.output_dir / "oai5g_held_out.jsonl"

    for filepath, samples in [(train_file, train_samples), (held_out_file, held_out_samples)]:
        with open(filepath, "w") as f:
            for s in samples:
                f.write(json.dumps(s) + "\n")

    print(f"\nStatistics:")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    print(f"\nTotal samples: {len(all_samples)}")
    print(f"  T1: {sum(1 for s in all_samples if s['rollout_type'] == 'T1')}")
    print(f"  T2: {sum(1 for s in all_samples if s['rollout_type'] == 'T2')}")
    print(f"  Train: {len(train_samples)}")
    print(f"  Held-out: {len(held_out_samples)}")
    print(f"\nSaved to:")
    print(f"  {train_file}")
    print(f"  {held_out_file}")


if __name__ == "__main__":
    main()
