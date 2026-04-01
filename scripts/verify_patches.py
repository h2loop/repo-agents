#!/usr/bin/env python3
"""
Soft verification: compare stage 1 patches (P1) against stage 2 patches (P2).

Uses line-level recall from soft_verify.py.
"""

import json
import sys
import yaml
from pathlib import Path
from argparse import ArgumentParser

# Import from sibling module
sys.path.insert(0, str(Path(__file__).parent))
from soft_verify import compute_recall, classify_verification


def main():
    parser = ArgumentParser()
    parser.add_argument("--stage-one-output", type=Path, required=True)
    parser.add_argument("--stage-two-output", type=Path, required=True)
    parser.add_argument("--stage-two-instances", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    with open(args.stage_two_instances) as f:
        instances = yaml.safe_load(f)

    results = []
    stats = {"total": 0, "verified": 0, "no_p2": 0, "error": 0}

    for inst in instances:
        inst_id = inst["id"]
        stats["total"] += 1

        # Get P1 from stage 1 (stored in extra_fields by scrape_stage_one.py)
        p1_text = inst.get("extra_fields", {}).get("stage_one_patch", "")
        if not p1_text:
            # Fall back to reading the .pred file
            pred_file = args.stage_one_output / inst_id / f"{inst_id}.pred"
            if pred_file.exists():
                try:
                    with open(pred_file) as f:
                        p1_text = json.load(f).get("model_patch", "")
                except Exception:
                    pass

        if not p1_text:
            stats["error"] += 1
            continue

        # Get P2 from stage 2
        pred_file = args.stage_two_output / inst_id / f"{inst_id}.pred"
        if not pred_file.exists():
            stats["no_p2"] += 1
            continue

        try:
            with open(pred_file) as f:
                p2_text = json.load(f).get("model_patch", "")
        except Exception:
            stats["no_p2"] += 1
            continue

        if not p2_text:
            stats["no_p2"] += 1
            continue

        # Compute recall
        recall = compute_recall(p1_text, p2_text)
        classification = classify_verification(recall)

        result = {
            "instance_id": inst_id,
            "recall_score": round(recall, 4),
            "classification": classification,
        }
        results.append(result)

        if recall >= 0.5:
            stats["verified"] += 1

    # Save results
    results_file = args.output_dir / "verification_results.jsonl"
    with open(results_file, "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    summary = {
        "stats": stats,
        "classification_counts": {},
    }
    for r in results:
        c = r["classification"]
        summary["classification_counts"][c] = summary["classification_counts"].get(c, 0) + 1

    summary_file = args.output_dir / "verification_summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Verification complete:")
    print(f"  Total instances: {stats['total']}")
    print(f"  Verified (recall >= 0.5): {stats['verified']}")
    print(f"  No P2 patch: {stats['no_p2']}")
    print(f"  Errors: {stats['error']}")
    print(f"  Classification: {json.dumps(summary['classification_counts'], indent=2)}")


if __name__ == "__main__":
    main()
