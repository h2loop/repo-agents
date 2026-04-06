#!/usr/bin/env python3
"""
Check current status of a data generation run by reading nohup.out and data/raw artifacts.

Usage:
    python scripts/check_current_status.py
    python scripts/check_current_status.py --nohup path/to/nohup.out --data-dir data/raw
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path


def analyze_nohup(nohup_path: Path, all_runs: bool = False) -> dict:
    """Parse nohup.out for run statistics."""
    content = nohup_path.read_text(errors="replace")

    # If multiple runs exist, default to the last one
    config_positions = [m.start() for m in re.finditer(r"Configuration:", content)]
    multi_run = len(config_positions) > 1
    if multi_run and not all_runs:
        content = content[config_positions[-1]:]

    started = re.findall(r"\[(s\d+_\w+)\] func=(\w+) bug=(\w+)", content)
    done = re.findall(r"\[(s\d+_\w+)\] DONE: score=([\d.]+) \((\w+)\)", content)
    failed_r1 = len(re.findall(r"FAILED at rollout 1", content))
    failed_r2 = len(re.findall(r"FAILED at rollout 2", content))
    failed_pr = len(re.findall(r"FAILED at PR generation", content))

    # Rejection breakdown
    empty_patch = len(re.findall(r"REJECTED.*empty patch", content))
    llm_rejected = len(re.findall(r"REJECTED.*LLM rejected", content))
    comment_only = len(re.findall(r"REJECTED.*comment/whitespace", content))

    # Verification breakdown
    classifications = Counter(c for _, _, c in done)

    # In-progress: started but neither done nor failed
    done_ids = {sid for sid, _, _ in done}
    failed_ids = set()
    for m in re.finditer(r"\[(s\d+_\w+)\] FAILED", content):
        failed_ids.add(m.group(1))
    started_ids = {sid for sid, _, _ in started}
    in_progress = started_ids - done_ids - failed_ids

    return {
        "multi_run": multi_run,
        "started": len(started),
        "done": len(done),
        "failed_r1": failed_r1,
        "failed_r2": failed_r2,
        "failed_pr": failed_pr,
        "empty_patch": empty_patch,
        "llm_rejected": llm_rejected,
        "comment_only": comment_only,
        "in_progress": len(in_progress),
        "classifications": dict(classifications),
    }


def analyze_artifacts(data_dir: Path) -> dict:
    """Scan data directory for artifacts."""
    t1 = sorted(data_dir.glob("*_t1_trajectory.jsonl"))
    t2 = sorted(data_dir.glob("*_t2_trajectory.jsonl"))
    p1 = sorted(data_dir.glob("*_p1.diff"))
    p2 = sorted(data_dir.glob("*_p2.diff"))
    prs = sorted(data_dir.glob("*_synth_pr.md"))
    verifs = sorted(data_dir.glob("*_verification.json"))

    classifications = Counter()
    scores = []
    for vf in verifs:
        v = json.loads(vf.read_text())
        classifications[v.get("classification", "unknown")] += 1
        scores.append(v.get("recall_score", 0.0))

    return {
        "t1_trajectories": len(t1),
        "t2_trajectories": len(t2),
        "p1_diffs": len(p1),
        "p2_diffs": len(p2),
        "synth_prs": len(prs),
        "verifications": len(verifs),
        "classifications": dict(classifications),
        "mean_score": sum(scores) / len(scores) if scores else 0.0,
    }


def main():
    parser = argparse.ArgumentParser(description="Check data generation run status")
    parser.add_argument("--nohup", type=Path, default=Path("nohup.out"))
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--all-runs", action="store_true", help="Include all runs in nohup.out, not just the latest")
    args = parser.parse_args()

    print("=" * 60)
    print("DATA GENERATION STATUS")
    print("=" * 60)

    # --- nohup.out analysis ---
    if args.nohup.exists():
        nohup = analyze_nohup(args.nohup, all_runs=args.all_runs)
        if nohup["multi_run"] and not args.all_runs:
            print("(Note: multiple runs detected, showing latest. Use --all-runs for combined)")
        elif nohup["multi_run"] and args.all_runs:
            print("(Showing combined stats across all runs)")
        print()
        print("Pipeline progress (from nohup.out):")
        print(f"  Samples started:    {nohup['started']}")
        print(f"  In progress:        {nohup['in_progress']}")
        print(f"  Completed:          {nohup['done']}")
        total_failed = nohup["failed_r1"] + nohup["failed_r2"] + nohup["failed_pr"]
        print(f"  Failed:             {total_failed}")
        print(f"    Rollout 1:        {nohup['failed_r1']}")
        if nohup["failed_r2"]:
            print(f"    Rollout 2:        {nohup['failed_r2']}")
        if nohup["failed_pr"]:
            print(f"    PR generation:    {nohup['failed_pr']}")
        print()
        print("Rollout 1 rejection reasons:")
        print(f"  Empty patch:        {nohup['empty_patch']}")
        print(f"  LLM rejected:       {nohup['llm_rejected']}")
        print(f"  Comment-only:       {nohup['comment_only']}")
        bare = nohup["failed_r1"] - nohup["empty_patch"] - nohup["llm_rejected"] - nohup["comment_only"]
        if bare > 0:
            print(f"  Other/no detail:    {bare}")
        print()
        print("Verification (from nohup.out):")
        for label in ["hard_verified", "soft_verified", "weakly_verified", "unverified"]:
            count = nohup["classifications"].get(label, 0)
            pct = count / nohup["done"] * 100 if nohup["done"] else 0
            print(f"  {label:20s} {count:5d}  ({pct:.1f}%)")
        passed = nohup["classifications"].get("hard_verified", 0) + nohup["classifications"].get("soft_verified", 0)
        pct = passed / nohup["done"] * 100 if nohup["done"] else 0
        print(f"  {'PASSED (hard+soft)':20s} {passed:5d}  ({pct:.1f}%)")
    else:
        print(f"\n  nohup.out not found at {args.nohup}")

    # --- Artifact analysis ---
    if args.data_dir.exists():
        artifacts = analyze_artifacts(args.data_dir)
        print()
        print("-" * 60)
        print(f"Artifacts on disk ({args.data_dir}):")
        print(f"  T1 trajectories:    {artifacts['t1_trajectories']}")
        print(f"  P1 diffs:           {artifacts['p1_diffs']}")
        print(f"  Synthetic PRs:      {artifacts['synth_prs']}")
        print(f"  T2 trajectories:    {artifacts['t2_trajectories']}")
        print(f"  P2 diffs:           {artifacts['p2_diffs']}")
        print(f"  Verifications:      {artifacts['verifications']}")
        print()
        print("Verification (from artifacts):")
        for label in ["hard_verified", "soft_verified", "weakly_verified", "unverified"]:
            count = artifacts["classifications"].get(label, 0)
            pct = count / artifacts["verifications"] * 100 if artifacts["verifications"] else 0
            print(f"  {label:20s} {count:5d}  ({pct:.1f}%)")
        passed = artifacts["classifications"].get("hard_verified", 0) + artifacts["classifications"].get("soft_verified", 0)
        pct = passed / artifacts["verifications"] * 100 if artifacts["verifications"] else 0
        print(f"  {'PASSED (hard+soft)':20s} {passed:5d}  ({pct:.1f}%)")
        print(f"  Mean recall score:  {artifacts['mean_score']:.3f}")
    else:
        print(f"\n  Data directory not found at {args.data_dir}")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
