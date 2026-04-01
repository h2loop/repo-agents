#!/usr/bin/env python3
"""
Phase 5.5: Master orchestrator for SVG data generation pipeline.

Runs the full SVG pipeline end-to-end:
  1. For each commit snapshot, spin up Docker containers
  2. Sample (function, bug) pairs and run rollout 1
  3. Generate synthetic PRs from T1 trajectories
  4. Run rollout 2 from synthetic PRs
  5. Soft-verify P1 vs P2
  6. Save all artifacts with metadata

Usage:
    # Pilot run (20 trajectories)
    python scripts/generate_data.py \
        --functions data/oai5g_functions.jsonl \
        --bug-prompts configs/bug_prompts.json \
        --template configs/bug_prompt_template.txt \
        --commits configs/commits.json \
        --demo-prs-dir configs/demo_prs \
        --output-dir data/raw \
        --num-samples 20

    # Full run (16000 trajectories)
    python scripts/generate_data.py \
        --functions data/oai5g_functions.jsonl \
        --bug-prompts configs/bug_prompts.json \
        --template configs/bug_prompt_template.txt \
        --commits configs/commits.json \
        --demo-prs-dir configs/demo_prs \
        --output-dir data/raw \
        --num-samples 16000 \
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
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rollout1 import (
    load_functions,
    load_bug_prompts,
    format_prompt,
    run_single as run_rollout1_single,
)
from generate_pr import (
    load_demo_prs,
    load_trajectory,
    process_single as generate_pr_single,
)
from rollout2 import run_single_rollout2
from soft_verify import verify_pair, classify_verification


# ---------------------------------------------------------------------------
# Pipeline for a single sample
# ---------------------------------------------------------------------------

def run_full_pipeline(
    sample_id: str,
    func: dict,
    bug: dict,
    template: str,
    container_image: str,
    demo_prs: list[str],
    output_dir: Path,
) -> dict | None:
    """Run the complete SVG pipeline for one (function, bug) pair.

    Steps: rollout1 -> generate_pr -> rollout2 -> soft_verify

    Returns a metadata dict or None on failure.
    """
    run_id = sample_id
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"[{run_id}] func={func['name']} bug={bug['bug_id']}", file=sys.stderr)

    # --- Step 1: Rollout 1 ---
    print(f"[{run_id}] Step 1: Rollout 1 (change generation)...", file=sys.stderr)
    r1_result = run_rollout1_single(
        func, bug, template, container_image, output_dir, run_id,
    )
    if r1_result is None:
        print(f"[{run_id}] FAILED at rollout 1 (rejected or error)", file=sys.stderr)
        return None

    # --- Step 2: Generate synthetic PR ---
    print(f"[{run_id}] Step 2: Generating synthetic PR...", file=sys.stderr)
    traj_path = Path(r1_result["trajectory_path"])
    pr_path = output_dir / f"{run_id}_synth_pr.md"
    try:
        pr_result = generate_pr_single(traj_path, demo_prs, pr_path)
    except Exception as e:
        print(f"[{run_id}] FAILED at PR generation: {e}", file=sys.stderr)
        return None

    # --- Step 3: Rollout 2 ---
    print(f"[{run_id}] Step 3: Rollout 2 (reproduction)...", file=sys.stderr)
    pr_text = pr_path.read_text()
    r2_result = run_single_rollout2(pr_text, container_image, output_dir, run_id)
    if r2_result is None:
        print(f"[{run_id}] FAILED at rollout 2", file=sys.stderr)
        # Still save T1 data — it's usable even without T2
        return {
            "run_id": run_id,
            "status": "t1_only",
            "t1": r1_result,
            "t2": None,
            "verification": None,
        }

    # --- Step 4: Soft verification ---
    print(f"[{run_id}] Step 4: Soft verification...", file=sys.stderr)
    p1_path = Path(r1_result["patch_path"])
    p2_path = Path(r2_result["patch_path"])

    try:
        verification = verify_pair(p1_path, p2_path)
    except Exception as e:
        print(f"[{run_id}] Verification error: {e}", file=sys.stderr)
        verification = {"recall_score": 0.0, "classification": "error"}

    # Save verification result
    verif_path = output_dir / f"{run_id}_verification.json"
    with open(verif_path, "w") as f:
        json.dump(verification, f, indent=2)

    print(
        f"[{run_id}] DONE: score={verification['recall_score']:.2f} "
        f"({verification['classification']})",
        file=sys.stderr,
    )

    return {
        "run_id": run_id,
        "status": "complete",
        "function": func["name"],
        "bug_type": bug["bug_id"],
        "subsystem": func["subsystem"],
        "t1": r1_result,
        "t2": r2_result,
        "verification": verification,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SERA SVG: Full data generation pipeline")
    parser.add_argument("--functions", type=Path, required=True)
    parser.add_argument("--bug-prompts", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--commits", type=Path, required=True)
    parser.add_argument("--demo-prs-dir", type=Path, default=Path("configs/demo_prs"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--num-samples", type=int, default=20, help="Total trajectories to generate")
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers (each uses own container)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", action="store_true", help="Skip already-completed run IDs")
    args = parser.parse_args()

    random.seed(args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load all data
    functions = load_functions(args.functions)
    bug_prompts = load_bug_prompts(args.bug_prompts)
    template = args.template.read_text()
    demo_prs = load_demo_prs(args.demo_prs_dir)

    # Load commit snapshots
    with open(args.commits) as f:
        commits_config = json.load(f)
    commits = [c["sha"] for c in commits_config["commits"] if not c["sha"].startswith("PLACEHOLDER")]

    if not commits:
        print("No valid commits found in commits.json. Using 'latest' image.", file=sys.stderr)
        commits = ["latest"]

    print(f"Configuration:", file=sys.stderr)
    print(f"  Functions:    {len(functions)}", file=sys.stderr)
    print(f"  Bug types:    {len(bug_prompts)}", file=sys.stderr)
    print(f"  Commits:      {commits}", file=sys.stderr)
    print(f"  Demo PRs:     {len(demo_prs)}", file=sys.stderr)
    print(f"  Num samples:  {args.num_samples}", file=sys.stderr)
    print(f"  Workers:      {args.workers}", file=sys.stderr)

    # Check for existing completions (for resume)
    existing_ids = set()
    if args.resume:
        for f in args.output_dir.glob("*_verification.json"):
            existing_ids.add(f.stem.replace("_verification", ""))
        print(f"  Resuming: {len(existing_ids)} already completed", file=sys.stderr)

    # Generate sample plan: distribute across commits evenly
    samples_per_commit = args.num_samples // len(commits)
    remainder = args.num_samples % len(commits)

    sample_plan: list[tuple[str, dict, dict]] = []  # (container_image, func, bug)
    for ci, commit in enumerate(commits):
        n = samples_per_commit + (1 if ci < remainder else 0)
        image = f"oai5g-sera:{commit[:7]}" if commit != "latest" else "oai5g-sera:latest"
        for _ in range(n):
            func = random.choice(functions)
            bug = random.choice(bug_prompts)
            sample_plan.append((image, func, bug))

    # Shuffle to interleave commits
    random.shuffle(sample_plan)

    # Run pipeline
    manifest: list[dict] = []
    completed = 0
    failed = 0

    if args.workers <= 1:
        # Sequential execution
        for i, (image, func, bug) in enumerate(sample_plan):
            sample_id = f"s{i:05d}_{uuid.uuid4().hex[:6]}"

            if sample_id in existing_ids:
                continue

            result = run_full_pipeline(
                sample_id, func, bug, template, image, demo_prs, args.output_dir,
            )
            if result:
                manifest.append(result)
                completed += 1
            else:
                failed += 1

            # Periodic progress
            if (i + 1) % 10 == 0:
                print(
                    f"\n>>> Progress: {completed} completed, {failed} failed, "
                    f"{i+1}/{len(sample_plan)} processed",
                    file=sys.stderr,
                )
    else:
        # Parallel execution
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for i, (image, func, bug) in enumerate(sample_plan):
                sample_id = f"s{i:05d}_{uuid.uuid4().hex[:6]}"
                if sample_id in existing_ids:
                    continue

                future = executor.submit(
                    run_full_pipeline,
                    sample_id, func, bug, template, image, demo_prs, args.output_dir,
                )
                futures[future] = sample_id

            for future in as_completed(futures):
                sample_id = futures[future]
                try:
                    result = future.result()
                    if result:
                        manifest.append(result)
                        completed += 1
                    else:
                        failed += 1
                except Exception as e:
                    print(f"[{sample_id}] Worker exception: {e}", file=sys.stderr)
                    failed += 1

    # Save manifest
    manifest_path = args.output_dir / "generation_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump({
            "total_samples": len(sample_plan),
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
    print(f"Generation complete!", file=sys.stderr)
    print(f"  Completed: {completed}", file=sys.stderr)
    print(f"  Failed:    {failed}", file=sys.stderr)
    print(f"  Manifest:  {manifest_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
