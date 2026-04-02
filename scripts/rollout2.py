#!/usr/bin/env python3
"""
Phase 5.3: Rollout 2 — Reproduction from synthetic PR description.

Given ONLY a synthetic PR description (no original bug prompt, no function hint),
drives the teacher model through SWE-agent to reproduce the change.

Produces:
  - T2: full agent trajectory (JSONL)
  - P2: unified diff of the reproduced change

Usage:
    python scripts/rollout2.py \
        --pr data/raw/001_synth_pr.md \
        --container oai5g-sera:latest \
        --output-dir data/raw \
        --run-id 001

    # Batch mode:
    python scripts/rollout2.py \
        --batch-dir data/raw \
        --container oai5g-sera:latest \
        --output-dir data/raw

Environment variables:
    LLM_BASE_URL  - LiteLLM proxy URL
    LLM_API_KEY   - API key
    LLM_MODEL     - Model ID
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

# Reuse components from rollout1
from rollout1 import (
    SYSTEM_PROMPT,
    REPO_CFG,
    chat_completion,
    start_container,
    stop_container,
    get_patch,
    run_rollout,
)

# Repo-specific values from config
_REPO_DISPLAY_NAME = REPO_CFG.get("repo_display_name", "OpenAirInterface 5G")
_SYSTEM_PROMPT_CONTEXT = REPO_CFG.get("system_prompt_context", "")
_BUILD_CAVEAT = REPO_CFG.get("build_caveat", "")
_CONTAINER_REPO_PATH = REPO_CFG.get("container_repo_path", "/repo")
_DOCKER_IMAGE_PREFIX = REPO_CFG.get("docker_image_prefix", "sera")

# Override the system prompt slightly for rollout 2 — no bug hint, just PR description
_build_caveat_line = f"\n{_BUILD_CAVEAT}" if _BUILD_CAVEAT else ""
ROLLOUT2_SYSTEM_PROMPT = f"""\
You are an expert C/C++ software engineer working on the {_REPO_DISPLAY_NAME} codebase.
{_SYSTEM_PROMPT_CONTEXT}

You have access to the following tools to navigate and modify the codebase:

1. **bash** - Execute shell commands. Use for: grep, find, ls, gcc -fsyntax-only, etc.
2. **str_replace_editor** - View and edit files. Commands:
   - view: View file contents (with optional line range)
   - str_replace: Replace a specific string in a file
   - create: Create a new file
   - insert: Insert text at a specific line

Working directory is {_CONTAINER_REPO_PATH}.{_build_caveat_line}

You will be given a pull request description. Your task is to implement the changes
described in the PR. Navigate the codebase, understand the relevant code, and make
the necessary modifications.

When you are done making your changes, output SUBMIT to indicate you are finished.

Think step by step. First understand what the PR is asking for, then locate the relevant
code, and finally implement the changes.
"""


def run_single_rollout2(
    pr_text: str,
    container_image: str,
    output_dir: Path,
    run_id: str,
) -> dict | None:
    """Run a single rollout 2 for a given synthetic PR.

    Returns metadata dict on success, None on failure.
    """
    prompt = f"Please implement the following pull request:\n\n{pr_text}"

    # Start container
    print(f"  Starting container {container_image}...", file=sys.stderr)
    container_id = start_container(container_image)

    try:
        # Temporarily override the system prompt for rollout 2
        import rollout1
        original_sys = rollout1.SYSTEM_PROMPT
        rollout1.SYSTEM_PROMPT = ROLLOUT2_SYSTEM_PROMPT

        try:
            trajectory = run_rollout(container_id, prompt)
        finally:
            rollout1.SYSTEM_PROMPT = original_sys

        # Extract patch
        patch = get_patch(container_id)

        # Save artifacts
        traj_path = output_dir / f"{run_id}_t2_trajectory.jsonl"
        patch_path = output_dir / f"{run_id}_p2.diff"
        meta_path = output_dir / f"{run_id}_t2_meta.json"

        with open(traj_path, "w") as f:
            for entry in trajectory:
                f.write(json.dumps(entry) + "\n")

        with open(patch_path, "w") as f:
            f.write(patch)

        metadata = {
            "run_id": run_id,
            "pr_text": pr_text[:500],  # truncated for metadata
            "trajectory_path": str(traj_path),
            "patch_path": str(patch_path),
            "patch_lines": len([
                l for l in patch.splitlines()
                if l.startswith("+") and not l.startswith("+++")
            ]),
            "trajectory_steps": len([e for e in trajectory if e["role"] == "assistant"]),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        with open(meta_path, "w") as f:
            json.dump(metadata, f, indent=2)

        print(
            f"  OK: {metadata['trajectory_steps']} steps, "
            f"{metadata['patch_lines']} patch lines",
            file=sys.stderr,
        )
        return metadata

    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return None

    finally:
        stop_container(container_id)


def main():
    parser = argparse.ArgumentParser(description="SERA SVG Rollout 2: Reproduction from PR")
    parser.add_argument("--pr", type=Path, help="Single synthetic PR file to process")
    parser.add_argument("--container", type=str, default=f"{_DOCKER_IMAGE_PREFIX}:latest", help="Docker image")
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw"), help="Output directory")
    parser.add_argument("--run-id", type=str, default=None, help="Run ID")

    # Batch mode
    parser.add_argument("--batch-dir", type=Path, help="Directory with *_synth_pr.md files")

    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.pr:
        # Single mode
        run_id = args.run_id or args.pr.stem.replace("_synth_pr", "")
        pr_text = args.pr.read_text()
        result = run_single_rollout2(pr_text, args.container, args.output_dir, run_id)
        if result:
            print(json.dumps(result, indent=2))
        else:
            sys.exit(1)

    elif args.batch_dir:
        # Batch mode
        pr_files = sorted(args.batch_dir.glob("*_synth_pr.md"))
        print(f"Found {len(pr_files)} synthetic PRs to process", file=sys.stderr)

        results = []
        for i, pr_path in enumerate(pr_files):
            run_id = pr_path.stem.replace("_synth_pr", "")

            # Skip if T2 already exists
            t2_path = args.output_dir / f"{run_id}_t2_trajectory.jsonl"
            if t2_path.exists():
                print(f"  [{i+1}/{len(pr_files)}] Skip (exists): {run_id}", file=sys.stderr)
                continue

            print(f"  [{i+1}/{len(pr_files)}] Processing {run_id}...", file=sys.stderr)
            pr_text = pr_path.read_text()
            result = run_single_rollout2(pr_text, args.container, args.output_dir, run_id)
            if result:
                results.append(result)

        print(f"\nCompleted: {len(results)}/{len(pr_files)} rollout 2s", file=sys.stderr)

    else:
        parser.error("Provide either --pr or --batch-dir")


if __name__ == "__main__":
    main()
