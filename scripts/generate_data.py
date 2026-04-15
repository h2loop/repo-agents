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
import random
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rollout1 import (
    load_functions,
    load_bug_prompts,
    run_single as run_rollout1_single,
    ContainerPool,
    reset_container,
    REPO_CFG,
)
from generate_pr import (
    load_demo_prs,
    process_single as generate_pr_single,
)
from rollout2 import run_single_rollout2
from soft_verify import verify_pair


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
    pool: ContainerPool | None = None,
    max_steps: int | None = None,
) -> dict | None:
    """Run the complete SVG pipeline for one (function, bug) pair.

    Steps: rollout1 -> generate_pr -> rollout2 -> soft_verify

    If pool is provided, acquires/releases containers from it.

    Returns a metadata dict or None on failure.
    """
    run_id = sample_id
    print(f"\n{'=' * 60}", file=sys.stderr)
    print(f"[{run_id}] func={func['name']} bug={bug['bug_id']}", file=sys.stderr)

    # Acquire container from pool or let run_single manage its own
    cid = pool.acquire() if pool else None

    try:
        # --- Step 1: Rollout 1 ---
        print(f"[{run_id}] Step 1: Rollout 1 (change generation)...", file=sys.stderr)
        r1_result = run_rollout1_single(
            func,
            bug,
            template,
            container_image,
            output_dir,
            run_id,
            container_id=cid,
            max_steps=max_steps,
        )
        if r1_result is None:
            print(
                f"[{run_id}] FAILED at rollout 1 (rejected or error)", file=sys.stderr
            )
            return None

        # Reset container for rollout 2
        if cid:
            reset_container(cid)

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
        r2_result = run_single_rollout2(
            pr_text,
            container_image,
            output_dir,
            run_id,
            container_id=cid,
            max_steps=max_steps,
        )
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

    finally:
        if pool and cid:
            pool.release(cid)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="SERA SVG: Full data generation pipeline"
    )
    parser.add_argument("--functions", type=Path, required=True)
    parser.add_argument("--bug-prompts", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--commits", type=Path, required=True)
    parser.add_argument("--demo-prs-dir", type=Path, default=Path("configs/demo_prs"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: data/raw_{date}_{time})",
    )
    parser.add_argument(
        "--bugs-per-func",
        type=int,
        default=3,
        help="Max bug attempts per function (stop on first success)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Cap total attempts (default: all functions)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel workers (each uses own container)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--resume", action="store_true", help="Skip already-completed run IDs"
    )
    parser.add_argument(
        "--min-lines",
        type=int,
        default=20,
        help="Minimum function body lines (default: 20)",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Max agent steps per hydron session (default: unlimited)",
    )
    args = parser.parse_args()

    random.seed(args.seed)
    if args.output_dir is None:
        args.output_dir = Path(f"data/raw_{time.strftime('%Y%m%d_%H%M%S')}")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Load all data
    functions = load_functions(args.functions)
    functions = [f for f in functions if f.get("body_lines", 0) >= args.min_lines]
    print(
        f"  After min-lines filter ({args.min_lines}): {len(functions)} functions",
        file=sys.stderr,
    )

    # Filter out paths from repo config (e.g. test code, auto-generated files)
    exclude_prefixes = REPO_CFG.get("exclude_path_prefixes", [])
    if exclude_prefixes:
        pre_filter = len(functions)
        functions = [
            f
            for f in functions
            if not any(f["file"].startswith(p) for p in exclude_prefixes)
        ]
        print(
            f"  After path filter ({exclude_prefixes}): {len(functions)} functions (removed {pre_filter - len(functions)})",
            file=sys.stderr,
        )
    bug_prompts = load_bug_prompts(args.bug_prompts)
    template = args.template.read_text()
    demo_prs = load_demo_prs(args.demo_prs_dir)

    # Load commit snapshots
    with open(args.commits) as f:
        commits_config = json.load(f)
    commits = [
        c["sha"]
        for c in commits_config["commits"]
        if not c["sha"].startswith("PLACEHOLDER")
    ]

    if not commits:
        print(
            "No valid commits found in commits.json. Using 'latest' image.",
            file=sys.stderr,
        )
        commits = ["latest"]

    # Build bug-to-function matching
    def pick_bugs_for_func(func: dict, k: int) -> list[dict]:
        """Pick k random bugs compatible with this function's subsystem."""
        compatible = [
            b
            for b in bug_prompts
            if not b.get("subsystems")
            or any(func["subsystem"].startswith(sub) for sub in b["subsystems"])
        ]
        if not compatible:
            compatible = bug_prompts
        return random.sample(compatible, min(k, len(compatible)))

    # Build sample plan: for each function, up to K bug attempts
    # Distribute functions across commits evenly
    docker_prefix = REPO_CFG.get("docker_image_prefix", "sera")
    images = []
    for commit in commits:
        images.append(
            f"{docker_prefix}:{commit[:7]}"
            if commit != "latest"
            else f"{docker_prefix}:latest"
        )

    random.shuffle(functions)
    if args.max_samples:
        functions = functions[: args.max_samples]

    # Each function gets assigned to a commit (round-robin) and up to K bugs
    sample_plan: list[tuple[str, dict, list[dict]]] = []  # (image, func, [bugs])
    for fi, func in enumerate(functions):
        image = images[fi % len(images)]
        bugs = pick_bugs_for_func(func, args.bugs_per_func)
        sample_plan.append((image, func, bugs))

    max_attempts = sum(len(bugs) for _, _, bugs in sample_plan)
    expected_successes = len(sample_plan)  # 1 per function at best

    print("Configuration:", file=sys.stderr)
    print(f"  Functions:       {len(functions)}", file=sys.stderr)
    print(f"  Bug types:       {len(bug_prompts)}", file=sys.stderr)
    print(f"  Bugs per func:   {args.bugs_per_func}", file=sys.stderr)
    print(f"  Commits:         {commits}", file=sys.stderr)
    print(f"  Demo PRs:        {len(demo_prs)}", file=sys.stderr)
    print(f"  Workers:         {args.workers}", file=sys.stderr)
    print(
        f"  Max attempts:    {max_attempts} ({len(sample_plan)} functions x up to {args.bugs_per_func} bugs)",
        file=sys.stderr,
    )
    print(
        f"  Expected output: up to {expected_successes} trajectories (1 per function)",
        file=sys.stderr,
    )

    # Check for existing completions (for resume).
    # A function counts as "already done" only if some bug attempt produced
    # the full triple: T1 meta + T2 meta + verification with recall >= 0.5
    # (matching the soft_verified threshold in soft_verify.py). Attempts that
    # stopped at T1, failed verification, or scored below 0.5 are retried.
    existing_funcs: set[str] = set()
    if args.resume:
        retry_low_score = 0
        retry_missing_t2 = 0
        retry_missing_verif = 0
        for meta_path in args.output_dir.glob("*_t1_meta.json"):
            try:
                meta = json.loads(meta_path.read_text())
                func_key = f"{meta['function']['file']}:{meta['function']['name']}"
                run_id = meta.get("run_id") or meta_path.name[: -len("_t1_meta.json")]

                t2_meta_path = args.output_dir / f"{run_id}_t2_meta.json"
                verif_path = args.output_dir / f"{run_id}_verification.json"

                if not t2_meta_path.exists():
                    retry_missing_t2 += 1
                    continue
                if not verif_path.exists():
                    retry_missing_verif += 1
                    continue
                verif = json.loads(verif_path.read_text())
                if float(verif.get("recall_score", 0.0)) < 0.5:
                    retry_low_score += 1
                    continue

                existing_funcs.add(func_key)
            except Exception:
                pass
        print(
            f"  Resuming: {len(existing_funcs)} functions verified "
            f"(recall >= 0.5); will retry {retry_low_score} low-score, "
            f"{retry_missing_t2} T1-only, {retry_missing_verif} unverified",
            file=sys.stderr,
        )

    # Group sample plan by image and process one image group at a time. This
    # bounds total live containers at `args.workers` regardless of how many
    # unique images exist — the previous per-image pool of size=workers
    # multiplied by N images, overloading the daemon. Original `fi` is
    # preserved so sample_id naming stays stable across resumes.
    groups: dict[str, list[tuple[int, dict, list[dict]]]] = {}
    for fi, (image, func, bugs) in enumerate(sample_plan):
        func_key = f"{func['file']}:{func['name']}"
        if func_key in existing_funcs:
            continue
        groups.setdefault(image, []).append((fi, func, bugs))

    total_to_process = sum(len(items) for items in groups.values())
    print(
        f"\n  Sample plan grouped into {len(groups)} image batches "
        f"({total_to_process} functions to process):",
        file=sys.stderr,
    )
    for image, items in groups.items():
        print(f"    {image}: {len(items)} functions", file=sys.stderr)

    # Run pipeline
    manifest: list[dict] = []
    completed = 0
    failed_funcs = 0
    total_processed = 0

    def run_function_attempts(
        fi: int,
        image: str,
        func: dict,
        bugs: list[dict],
        pool: ContainerPool,
    ) -> dict | None:
        """Try up to K bugs for one function, stop on first success."""
        for bi, bug in enumerate(bugs):
            sample_id = f"f{fi:05d}_b{bi}_{uuid.uuid4().hex[:6]}"
            result = run_full_pipeline(
                sample_id,
                func,
                bug,
                template,
                image,
                demo_prs,
                args.output_dir,
                pool=pool,
                max_steps=args.max_steps,
            )
            if result is not None:
                return result
        return None

    for batch_idx, (image, items) in enumerate(groups.items(), 1):
        # Pool sized for this image only — never exceeds args.workers and is
        # capped by item count when the image's batch is small.
        pool_size = max(1, min(args.workers, len(items)))
        print(
            f"\n  [{batch_idx}/{len(groups)}] {image}: warming pool of "
            f"{pool_size} containers for {len(items)} functions",
            file=sys.stderr,
        )
        pool = ContainerPool(image, size=pool_size)
        try:
            if args.workers <= 1:
                for fi, func, bugs in items:
                    result = run_function_attempts(fi, image, func, bugs, pool)
                    if result:
                        manifest.append(result)
                        completed += 1
                    else:
                        failed_funcs += 1
                    total_processed += 1
                    if total_processed % 10 == 0:
                        print(
                            f"\n>>> Progress: {completed} succeeded, "
                            f"{failed_funcs} failed, "
                            f"{total_processed}/{total_to_process} processed",
                            file=sys.stderr,
                        )
            else:
                with ThreadPoolExecutor(max_workers=pool_size) as executor:
                    futures = {
                        executor.submit(
                            run_function_attempts, fi, image, func, bugs, pool
                        ): (fi, func)
                        for fi, func, bugs in items
                    }
                    for future in as_completed(futures):
                        fi, func = futures[future]
                        try:
                            result = future.result()
                            if result:
                                manifest.append(result)
                                completed += 1
                            else:
                                failed_funcs += 1
                        except Exception as e:
                            print(
                                f"[func {fi}] Worker exception: {e}",
                                file=sys.stderr,
                            )
                            failed_funcs += 1
                        total_processed += 1
        finally:
            print(
                f"  [{batch_idx}/{len(groups)}] {image}: shutting down pool"
                f" ({completed} succeeded, {failed_funcs} failed so far)",
                file=sys.stderr,
            )
            pool.shutdown()

    # Save manifest — on resume, merge with prior samples so counts are
    # cumulative across resume invocations rather than reflecting only
    # the latest run.
    manifest_path = args.output_dir / "generation_manifest.json"
    prior_samples: list[dict] = []
    if args.resume and manifest_path.exists():
        try:
            prior = json.loads(manifest_path.read_text())
            prior_samples = prior.get("samples", []) or []
        except (json.JSONDecodeError, OSError) as e:
            print(
                f"  [manifest] WARNING: could not read prior manifest: {e} — "
                f"overwriting",
                file=sys.stderr,
            )

    # Dedup by run_id; new results win over priors with the same id.
    new_ids = {r.get("run_id") for r in manifest if r.get("run_id")}
    merged = [r for r in prior_samples if r.get("run_id") not in new_ids] + manifest

    with open(manifest_path, "w") as f:
        json.dump(
            {
                "total_functions": len(sample_plan),
                "completed": sum(1 for r in merged if r.get("status") == "complete"),
                "failed_funcs": failed_funcs,
                "bugs_per_func": args.bugs_per_func,
                "t1_only": sum(1 for r in merged if r.get("status") == "t1_only"),
                "fully_verified": sum(
                    1
                    for r in merged
                    if r.get("verification")
                    and r["verification"].get("classification")
                    in ("hard_verified", "soft_verified")
                ),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "samples": merged,
            },
            f,
            indent=2,
        )

    print(f"\n{'=' * 60}", file=sys.stderr)
    print("Generation complete!", file=sys.stderr)
    print(f"  Functions attempted: {completed + failed_funcs}", file=sys.stderr)
    print(f"  Succeeded:           {completed}", file=sys.stderr)
    print(f"  Failed (all bugs):   {failed_funcs}", file=sys.stderr)
    print(f"  Manifest:            {manifest_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
