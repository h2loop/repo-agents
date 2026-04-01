#!/usr/bin/env python3
"""
Phase 6: Data filtering and quality control.

Filters raw SVG trajectories into a clean dataset based on SERA paper criteria:
  1. Self-evaluation filter (reject if teacher flagged it)
  2. Patch size filter (<= 40 lines)
  3. Tool output length filter (avg <= 600 tokens)
  4. Duplicate patch filter
  5. Truncation ratio filter (>= 0.88)
  6. Token length filter (prioritize <= 32768 tokens)

Usage:
    python scripts/filter_data.py \
        --input-dir data/raw \
        --output-dir data/filtered \
        --max-patch-lines 40 \
        --max-avg-tool-tokens 600 \
        --min-truncation-ratio 0.88 \
        --max-tokens 32768 \
        --target-t1 5000 \
        --target-t2 3000
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Rough token estimate (whitespace split)."""
    return len(text.split())


def compute_trajectory_tokens(trajectory: list[dict]) -> int:
    """Estimate total token count for a trajectory."""
    total = 0
    for entry in trajectory:
        content = entry.get("content", "")
        reasoning = entry.get("reasoning_content", "")
        total += estimate_tokens(content)
        total += estimate_tokens(reasoning)
    return total


def compute_truncation_ratio(trajectory_tokens: int, context_window: int) -> float:
    """Compute what fraction of the trajectory fits in the context window."""
    if trajectory_tokens == 0:
        return 1.0
    return min(context_window / trajectory_tokens, 1.0)


def compute_avg_tool_output_tokens(trajectory: list[dict]) -> float:
    """Compute average token count of tool outputs in a trajectory."""
    tool_tokens = []
    for entry in trajectory:
        if entry.get("role") == "tool":
            tool_tokens.append(estimate_tokens(entry.get("content", "")))
    return sum(tool_tokens) / len(tool_tokens) if tool_tokens else 0.0


def compute_patch_hash(patch_text: str) -> str:
    """Compute a hash of normalized patch content for deduplication."""
    # Normalize: strip whitespace, sort lines
    lines = sorted(line.strip() for line in patch_text.splitlines() if line.strip())
    normalized = "\n".join(lines)
    return hashlib.sha256(normalized.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

def load_trajectory(path: Path) -> list[dict]:
    """Load a JSONL trajectory file."""
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def load_metadata(path: Path) -> dict:
    """Load a JSON metadata file."""
    with open(path) as f:
        return json.load(f)


def discover_samples(input_dir: Path) -> list[dict]:
    """Discover all completed samples in the raw output directory.

    Returns a list of sample info dicts with paths to all artifacts.
    """
    samples = []

    # Find all T1 trajectories
    for t1_path in sorted(input_dir.glob("*_t1_trajectory.jsonl")):
        run_id = t1_path.stem.replace("_t1_trajectory", "")

        sample = {
            "run_id": run_id,
            "t1_trajectory": t1_path,
            "t1_meta": input_dir / f"{run_id}_t1_meta.json",
            "p1": input_dir / f"{run_id}_p1.diff",
            "synth_pr": input_dir / f"{run_id}_synth_pr.md",
            "t2_trajectory": input_dir / f"{run_id}_t2_trajectory.jsonl",
            "t2_meta": input_dir / f"{run_id}_t2_meta.json",
            "p2": input_dir / f"{run_id}_p2.diff",
            "verification": input_dir / f"{run_id}_verification.json",
        }

        # Check what's available
        sample["has_t1"] = t1_path.exists() and sample["p1"].exists()
        sample["has_t2"] = sample["t2_trajectory"].exists() and sample["p2"].exists()
        sample["has_verification"] = sample["verification"].exists()

        if sample["has_t1"]:
            samples.append(sample)

    return samples


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_samples(
    samples: list[dict],
    max_patch_lines: int = 40,
    max_avg_tool_tokens: float = 600.0,
    min_truncation_ratio: float = 0.88,
    max_tokens: int = 32768,
) -> tuple[list[dict], list[dict], dict]:
    """Apply all filters to samples.

    Returns (filtered_t1, filtered_t2, statistics).
    """
    stats = Counter()
    seen_patches: set[str] = set()
    filtered_t1: list[dict] = []
    filtered_t2: list[dict] = []

    for sample in samples:
        run_id = sample["run_id"]

        # --- Filter T1 trajectories ---
        if sample["has_t1"]:
            stats["total_t1"] += 1

            # Load T1 data
            try:
                t1_traj = load_trajectory(sample["t1_trajectory"])
                p1_text = sample["p1"].read_text(errors="replace")
                t1_meta = load_metadata(sample["t1_meta"]) if sample["t1_meta"].exists() else {}
            except Exception as e:
                stats["t1_load_error"] += 1
                continue

            # Self-evaluation filter
            if not t1_meta.get("self_eval_accepted", True):
                stats["t1_self_eval_rejected"] += 1
                continue

            # Patch size filter
            patch_lines = len([
                l for l in p1_text.splitlines()
                if l.startswith("+") and not l.startswith("+++")
            ])
            if patch_lines > max_patch_lines:
                stats["t1_patch_too_large"] += 1
                continue
            if patch_lines == 0:
                stats["t1_empty_patch"] += 1
                continue

            # Duplicate patch filter
            patch_hash = compute_patch_hash(p1_text)
            if patch_hash in seen_patches:
                stats["t1_duplicate_patch"] += 1
                continue
            seen_patches.add(patch_hash)

            # Token length + truncation ratio
            traj_tokens = compute_trajectory_tokens(t1_traj)
            trunc_ratio = compute_truncation_ratio(traj_tokens, max_tokens)

            if trunc_ratio < min_truncation_ratio:
                stats["t1_truncation_too_low"] += 1
                continue

            # Average tool output filter
            avg_tool = compute_avg_tool_output_tokens(t1_traj)
            if avg_tool > max_avg_tool_tokens:
                stats["t1_tool_output_too_long"] += 1
                continue

            # Passed all filters — use a copy to avoid mutation
            t1_entry = dict(sample)
            t1_entry["t1_tokens"] = traj_tokens
            t1_entry["t1_truncation_ratio"] = trunc_ratio
            t1_entry["t1_patch_lines"] = patch_lines
            t1_entry["t1_avg_tool_tokens"] = avg_tool
            t1_entry["rollout_type"] = "T1"
            filtered_t1.append(t1_entry)
            stats["t1_passed"] += 1

        # --- Filter T2 trajectories ---
        if sample["has_t2"] and sample["has_verification"]:
            stats["total_t2"] += 1

            try:
                t2_traj = load_trajectory(sample["t2_trajectory"])
                p2_text = sample["p2"].read_text(errors="replace")
                verif = load_metadata(sample["verification"])
            except Exception as e:
                stats["t2_load_error"] += 1
                continue

            # Verification score filter (soft verified: r >= 0.5)
            recall = verif.get("recall_score", 0.0)
            if recall < 0.5:
                stats["t2_verification_too_low"] += 1
                continue

            # Patch size filter
            patch_lines = len([
                l for l in p2_text.splitlines()
                if l.startswith("+") and not l.startswith("+++")
            ])
            if patch_lines > max_patch_lines:
                stats["t2_patch_too_large"] += 1
                continue
            if patch_lines == 0:
                stats["t2_empty_patch"] += 1
                continue

            # Duplicate check
            patch_hash = compute_patch_hash(p2_text)
            if patch_hash in seen_patches:
                stats["t2_duplicate_patch"] += 1
                continue
            seen_patches.add(patch_hash)

            # Token + truncation
            traj_tokens = compute_trajectory_tokens(t2_traj)
            trunc_ratio = compute_truncation_ratio(traj_tokens, max_tokens)

            if trunc_ratio < min_truncation_ratio:
                stats["t2_truncation_too_low"] += 1
                continue

            # Tool output filter
            avg_tool = compute_avg_tool_output_tokens(t2_traj)
            if avg_tool > max_avg_tool_tokens:
                stats["t2_tool_output_too_long"] += 1
                continue

            t2_entry = dict(sample)
            t2_entry["t2_tokens"] = traj_tokens
            t2_entry["t2_truncation_ratio"] = trunc_ratio
            t2_entry["t2_patch_lines"] = patch_lines
            t2_entry["t2_avg_tool_tokens"] = avg_tool
            t2_entry["t2_recall_score"] = recall
            t2_entry["rollout_type"] = "T2"
            filtered_t2.append(t2_entry)
            stats["t2_passed"] += 1

    return filtered_t1, filtered_t2, dict(stats)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def select_dataset(
    filtered_t1: list[dict],
    filtered_t2: list[dict],
    target_t1: int,
    target_t2: int,
) -> list[dict]:
    """Select the final dataset from filtered T1 and T2 trajectories.

    Prioritizes by truncation ratio (higher is better), per SERA Section 5.2.
    """
    # Sort T1 by truncation ratio (descending) — best quality first
    t1_sorted = sorted(filtered_t1, key=lambda x: x.get("t1_truncation_ratio", 0), reverse=True)
    selected_t1 = t1_sorted[:target_t1]

    # Sort T2 by verification score (descending), then truncation ratio
    t2_sorted = sorted(
        filtered_t2,
        key=lambda x: (x.get("t2_recall_score", 0), x.get("t2_truncation_ratio", 0)),
        reverse=True,
    )
    selected_t2 = t2_sorted[:target_t2]

    return selected_t1 + selected_t2


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SERA SVG: Data filtering and quality control")
    parser.add_argument("--input-dir", type=Path, required=True, help="Raw data directory")
    parser.add_argument("--output-dir", type=Path, required=True, help="Filtered output directory")
    parser.add_argument("--max-patch-lines", type=int, default=40)
    parser.add_argument("--max-avg-tool-tokens", type=float, default=600.0)
    parser.add_argument("--min-truncation-ratio", type=float, default=0.88)
    parser.add_argument("--max-tokens", type=int, default=32768)
    parser.add_argument("--target-t1", type=int, default=5000, help="Target T1 trajectories")
    parser.add_argument("--target-t2", type=int, default=3000, help="Target T2 trajectories")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Discover samples
    print("Discovering samples...", file=sys.stderr)
    samples = discover_samples(args.input_dir)
    print(f"  Found {len(samples)} T1 samples", file=sys.stderr)

    # Filter
    print("Applying filters...", file=sys.stderr)
    filtered_t1, filtered_t2, stats = filter_samples(
        samples,
        max_patch_lines=args.max_patch_lines,
        max_avg_tool_tokens=args.max_avg_tool_tokens,
        min_truncation_ratio=args.min_truncation_ratio,
        max_tokens=args.max_tokens,
    )

    print(f"\nFilter statistics:", file=sys.stderr)
    for key, val in sorted(stats.items()):
        print(f"  {key}: {val}", file=sys.stderr)

    print(f"\nAfter filtering:", file=sys.stderr)
    print(f"  T1 passed: {len(filtered_t1)}", file=sys.stderr)
    print(f"  T2 passed: {len(filtered_t2)}", file=sys.stderr)

    # Select final dataset
    selected = select_dataset(filtered_t1, filtered_t2, args.target_t1, args.target_t2)
    actual_t1 = sum(1 for s in selected if s.get("rollout_type") == "T1")
    actual_t2 = sum(1 for s in selected if s.get("rollout_type") == "T2")

    print(f"\nFinal dataset:", file=sys.stderr)
    print(f"  T1: {actual_t1} (target: {args.target_t1})", file=sys.stderr)
    print(f"  T2: {actual_t2} (target: {args.target_t2})", file=sys.stderr)
    print(f"  Total: {len(selected)}", file=sys.stderr)

    # Save selection manifest
    manifest = {
        "filter_config": {
            "max_patch_lines": args.max_patch_lines,
            "max_avg_tool_tokens": args.max_avg_tool_tokens,
            "min_truncation_ratio": args.min_truncation_ratio,
            "max_tokens": args.max_tokens,
            "target_t1": args.target_t1,
            "target_t2": args.target_t2,
        },
        "statistics": stats,
        "selected_count": len(selected),
        "selected_t1": actual_t1,
        "selected_t2": actual_t2,
        "selected_run_ids": [s["run_id"] for s in selected],
    }

    manifest_path = args.output_dir / "filter_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Copy/symlink selected trajectories to output dir
    selection_path = args.output_dir / "selected_samples.jsonl"
    with open(selection_path, "w") as f:
        for sample in selected:
            entry = {
                "run_id": sample["run_id"],
                "rollout_type": sample.get("rollout_type"),
                "trajectory_path": str(
                    sample["t1_trajectory"] if sample.get("rollout_type") == "T1"
                    else sample["t2_trajectory"]
                ),
                "patch_path": str(
                    sample["p1"] if sample.get("rollout_type") == "T1"
                    else sample["p2"]
                ),
            }
            # Add type-specific metadata
            if sample.get("rollout_type") == "T1":
                entry["tokens"] = sample.get("t1_tokens")
                entry["truncation_ratio"] = sample.get("t1_truncation_ratio")
                entry["patch_lines"] = sample.get("t1_patch_lines")
            else:
                entry["tokens"] = sample.get("t2_tokens")
                entry["truncation_ratio"] = sample.get("t2_truncation_ratio")
                entry["patch_lines"] = sample.get("t2_patch_lines")
                entry["recall_score"] = sample.get("t2_recall_score")
            f.write(json.dumps(entry) + "\n")

    print(f"\nOutputs:", file=sys.stderr)
    print(f"  Manifest: {manifest_path}", file=sys.stderr)
    print(f"  Selection: {selection_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
