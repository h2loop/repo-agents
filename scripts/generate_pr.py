#!/usr/bin/env python3
"""
Phase 5.2: Synthetic PR generation.

Takes a rollout 1 trajectory and generates a synthetic pull request description
using the teacher model + a demonstration PR for formatting guidance.

Usage:
    python scripts/generate_pr.py \
        --trajectory data/raw/001_t1_trajectory.jsonl \
        --demo-pr configs/demo_prs/example_bugfix.md \
        --output data/raw/001_synth_pr.md

    # Batch mode:
    python scripts/generate_pr.py \
        --batch-dir data/raw \
        --demo-prs-dir configs/demo_prs \
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
import random
import sys
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Repo configuration
# ---------------------------------------------------------------------------
REPO_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "repo_config.json"


def _load_repo_config() -> dict:
    if REPO_CONFIG_PATH.exists():
        with open(REPO_CONFIG_PATH) as f:
            return json.load(f)
    return {}


_REPO_CFG = _load_repo_config()
_REPO_DISPLAY_NAME = _REPO_CFG.get("repo_display_name", "OpenAirInterface 5G")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("LLM_BASE_URL", "https://litellm-prod-909645453767.asia-south1.run.app")
API_KEY = os.getenv("LLM_API_KEY", "sk-1234")
MODEL = os.getenv("LLM_MODEL", "qwen/qwen3-coder-480b-a35b-instruct-maas")

PR_GENERATION_PROMPT = """\
You are a senior software engineer. Given the following agent trajectory that made changes \
to the {repo_display_name} codebase, write a concise pull request description.

The PR description should:
1. Have a clear title line (starting with "## Title:")
2. Describe WHAT was changed and WHY
3. List the affected files
4. Note any important implementation details
5. Be written as if you are the author of the change, in present tense

Here is an example PR description for reference:

---
{demo_pr}
---

Now, here is the agent trajectory (tool calls and observations) for the change you need to describe:

---
{trajectory_summary}
---

And here is the final patch:
```diff
{patch}
```

Write the PR description now. Keep it concise but informative (100-300 words).
"""


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

def chat_completion(messages: list[dict], temperature: float = 0.3, max_tokens: int = 2048) -> str:
    """Call the LLM and return the response text."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    msg = resp.json()["choices"][0]["message"]
    return (msg.get("content") or msg.get("reasoning_content") or "")


# ---------------------------------------------------------------------------
# Trajectory processing
# ---------------------------------------------------------------------------

def load_trajectory(path: Path) -> list[dict]:
    """Load a trajectory JSONL file."""
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def summarize_trajectory(trajectory: list[dict], max_chars: int = 6000) -> str:
    """Create a readable summary of the trajectory for the PR generation prompt.

    Includes key tool calls and observations, truncated to stay within token budget.
    """
    parts = []
    for entry in trajectory:
        role = entry.get("role", "")
        content = entry.get("content", "")

        if role == "system" and "Agent submitted" in content:
            parts.append("[Agent completed and submitted]")
            continue

        if role == "assistant":
            # Include reasoning + action
            step = entry.get("step", "?")
            reasoning = entry.get("reasoning_content", "")
            if reasoning:
                parts.append(f"[Step {step} - Reasoning]: {reasoning[:500]}")
            if content:
                parts.append(f"[Step {step} - Action]: {content[:500]}")

        elif role == "tool":
            tool_name = entry.get("tool_name", "unknown")
            tool_args = entry.get("tool_args", {})
            step = entry.get("step", "?")
            # Summarize tool call
            if tool_name == "bash":
                cmd = tool_args.get("command", "")
                parts.append(f"[Step {step} - bash]: $ {cmd[:200]}")
                parts.append(f"  Output: {content[:300]}")
            elif tool_name == "str_replace_editor":
                cmd = tool_args.get("command", "")
                path = tool_args.get("path", "")
                parts.append(f"[Step {step} - {cmd} {path}]")
                if cmd == "view":
                    parts.append(f"  Content: {content[:300]}")

    summary = "\n".join(parts)
    if len(summary) > max_chars:
        summary = summary[:max_chars] + "\n... [truncated]"
    return summary


def load_patch(trajectory_path: Path) -> str:
    """Load the P1 patch file corresponding to a trajectory."""
    # Convention: trajectory is XXX_t1_trajectory.jsonl, patch is XXX_p1.diff
    patch_path = trajectory_path.parent / trajectory_path.name.replace(
        "_t1_trajectory.jsonl", "_p1.diff"
    )
    if patch_path.exists():
        text = patch_path.read_text(errors="replace")
        # Truncate very long patches
        if len(text) > 3000:
            text = text[:3000] + "\n... [patch truncated]"
        return text
    return "[Patch file not found]"


def load_demo_prs(demo_dir: Path) -> list[str]:
    """Load all demonstration PR files from a directory."""
    prs = []
    if demo_dir.is_dir():
        for f in sorted(demo_dir.iterdir()):
            if f.suffix in (".md", ".txt"):
                prs.append(f.read_text(errors="replace"))
    return prs


# ---------------------------------------------------------------------------
# PR generation
# ---------------------------------------------------------------------------

def generate_pr(
    trajectory: list[dict],
    patch: str,
    demo_pr: str,
) -> str:
    """Generate a synthetic PR description for a trajectory."""
    summary = summarize_trajectory(trajectory)

    prompt = PR_GENERATION_PROMPT.format(
        repo_display_name=_REPO_DISPLAY_NAME,
        demo_pr=demo_pr,
        trajectory_summary=summary,
        patch=patch,
    )

    messages = [{"role": "user", "content": prompt}]
    return chat_completion(messages)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process_single(
    trajectory_path: Path,
    demo_prs: list[str],
    output_path: Path,
) -> dict:
    """Process a single trajectory and generate its synthetic PR."""
    trajectory = load_trajectory(trajectory_path)
    patch = load_patch(trajectory_path)
    demo_pr = random.choice(demo_prs) if demo_prs else "No demonstration PR available."

    pr_text = generate_pr(trajectory, patch, demo_pr)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(pr_text)

    return {
        "trajectory": str(trajectory_path),
        "output": str(output_path),
        "pr_length_chars": len(pr_text),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main():
    parser = argparse.ArgumentParser(description="SERA SVG: Synthetic PR generation")
    parser.add_argument("--trajectory", type=Path, help="Single trajectory JSONL to process")
    parser.add_argument("--demo-pr", type=Path, help="Single demonstration PR file")
    parser.add_argument("--output", type=Path, help="Output PR file path")

    # Batch mode
    parser.add_argument("--batch-dir", type=Path, help="Directory of trajectory files for batch processing")
    parser.add_argument("--demo-prs-dir", type=Path, default=Path("configs/demo_prs"),
                        help="Directory of demonstration PRs")
    parser.add_argument("--output-dir", type=Path, help="Output directory for batch mode")

    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    # Load demo PRs
    demo_prs = []
    if args.demo_pr and args.demo_pr.exists():
        demo_prs = [args.demo_pr.read_text()]
    elif args.demo_prs_dir:
        demo_prs = load_demo_prs(args.demo_prs_dir)

    if not demo_prs:
        print("Warning: No demonstration PRs found. Using placeholder.", file=sys.stderr)
        fallback = _REPO_CFG.get(
            "fallback_demo_pr",
            "## Title: Fix bug\n\nFix an issue in the codebase.\n\n### Changes\n- Fixed the relevant source file\n\n### Testing\n- Verified manually",
        )
        demo_prs = [fallback]

    if args.trajectory:
        # Single mode
        if not args.output:
            args.output = args.trajectory.parent / args.trajectory.name.replace(
                "_t1_trajectory.jsonl", "_synth_pr.md"
            )
        result = process_single(args.trajectory, demo_prs, args.output)
        print(json.dumps(result, indent=2))

    elif args.batch_dir:
        # Batch mode
        output_dir = args.output_dir or args.batch_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        traj_files = sorted(args.batch_dir.glob("*_t1_trajectory.jsonl"))
        print(f"Found {len(traj_files)} trajectories to process", file=sys.stderr)

        results = []
        for i, traj_path in enumerate(traj_files):
            out_path = output_dir / traj_path.name.replace(
                "_t1_trajectory.jsonl", "_synth_pr.md"
            )
            # Skip if already exists
            if out_path.exists():
                print(f"  [{i+1}/{len(traj_files)}] Skip (exists): {out_path.name}", file=sys.stderr)
                continue

            print(f"  [{i+1}/{len(traj_files)}] Generating PR for {traj_path.name}...", file=sys.stderr)
            try:
                result = process_single(traj_path, demo_prs, out_path)
                results.append(result)
            except Exception as e:
                print(f"  ERROR: {e}", file=sys.stderr)

        print(f"\nGenerated {len(results)} synthetic PRs", file=sys.stderr)

    else:
        parser.error("Provide either --trajectory or --batch-dir")


if __name__ == "__main__":
    main()
