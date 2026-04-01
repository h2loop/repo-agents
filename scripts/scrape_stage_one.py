#!/usr/bin/env python3
"""
Scrape stage 1 SWE-agent output to create stage 2 instances.

Reads the .synth and .pred files from stage 1 output directories,
extracts successful synthetic PRs, and creates stage 2 instance YAML
where `problem_statement` is the synthetic PR.

This mirrors SERA's `scrape_synthetic_prs()` in distill.py.
"""

import json
import os
import sys
import yaml
from pathlib import Path
from argparse import ArgumentParser


def main():
    parser = ArgumentParser()
    parser.add_argument("--stage-one-instances", type=Path, required=True)
    parser.add_argument("--stage-one-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    with open(args.stage_one_instances) as f:
        instances = yaml.safe_load(f)

    seen_patches = set()
    stage_two_instances = []
    skipped = {"no_pred": 0, "no_synth": 0, "bad_patch": 0, "not_good": 0, "duplicate": 0, "no_pr": 0}

    for inst in instances:
        inst_id = inst["id"]
        inst_dir = args.stage_one_output / inst_id

        # Check for prediction file
        pred_file = inst_dir / f"{inst_id}.pred"
        if not pred_file.exists():
            skipped["no_pred"] += 1
            continue

        try:
            with open(pred_file) as f:
                pred = json.load(f)
        except (json.JSONDecodeError, Exception):
            skipped["no_pred"] += 1
            continue

        model_patch = pred.get("model_patch", "")
        if not model_patch:
            skipped["bad_patch"] += 1
            continue

        # Deduplicate patches
        if model_patch in seen_patches:
            skipped["duplicate"] += 1
            continue
        seen_patches.add(model_patch)

        # Check for synthetic PR metadata
        synth_file = inst_dir / f"{inst_id}.synth"
        if not synth_file.exists():
            skipped["no_synth"] += 1
            continue

        try:
            with open(synth_file) as f:
                synth_meta = json.load(f)
        except (json.JSONDecodeError, Exception):
            skipped["no_synth"] += 1
            continue

        if not synth_meta.get("is_good_patch"):
            skipped["not_good"] += 1
            continue

        synth_pr = synth_meta.get("synth_pr", "")
        if not synth_pr:
            skipped["no_pr"] += 1
            continue

        # Build stage 2 instance — use synthetic PR as the problem_statement
        stage_two_inst = dict(inst)
        stage_two_inst["problem_statement"] = synth_pr
        # Keep extra_fields so stage 2 config can use {{working_dir}} etc.
        stage_two_inst["extra_fields"]["stage_one_patch"] = model_patch
        stage_two_instances.append(stage_two_inst)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        yaml.safe_dump(stage_two_instances, f, indent=2)

    print(f"Stage 1 instances: {len(instances)}")
    print(f"Stage 2 instances: {len(stage_two_instances)}")
    print(f"Skipped: {json.dumps(skipped, indent=2)}")


if __name__ == "__main__":
    main()
