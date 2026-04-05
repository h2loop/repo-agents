#!/usr/bin/env python3
"""
Phase 5.4: Soft verification via line-level recall between two patches.

Compares patch P1 (rollout 1) against P2 (rollout 2) using the metric from
the SERA paper: r = |P2 intersect P1| / |P1|

Usage:
    python scripts/soft_verify.py --p1 data/raw/001_p1.diff --p2 data/raw/001_p2.diff

    # Or programmatically:
    from soft_verify import compute_recall, classify_verification
    score = compute_recall(p1_text, p2_text)
    label = classify_verification(score)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def parse_patch_lines(patch_text: str) -> set[str]:
    """Extract the set of meaningful changed lines from a unified diff.

    We consider only added lines (starting with '+') that are not part of the
    diff header.  Lines are stripped of the leading '+' and whitespace-normalized
    to make comparison resilient to formatting differences.
    """
    changed: set[str] = set()
    for line in patch_text.splitlines():
        # Skip diff headers
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("@@"):
            continue
        if line.startswith("diff "):
            continue
        if line.startswith("index "):
            continue

        # Added lines
        if line.startswith("+"):
            content = line[1:]  # strip leading '+'
            # Normalize whitespace for comparison
            normalized = " ".join(content.split()).strip()
            # Skip empty / whitespace-only lines
            if normalized:
                changed.add(normalized)

    return changed


def _fuzzy_match_count(p1_lines: set[str], p2_lines: set[str], threshold: float = 0.7) -> int:
    """Count P1 lines that have a fuzzy match (>= threshold) in P2."""
    from difflib import SequenceMatcher
    matched = 0
    for line1 in p1_lines:
        for line2 in p2_lines:
            if SequenceMatcher(None, line1, line2).ratio() >= threshold:
                matched += 1
                break
    return matched


def compute_recall(p1_text: str, p2_text: str) -> float:
    """Compute line-level recall: r = |P2 ∩ P1| / |P1|.

    Uses exact matching first, then fuzzy matching (>= 0.7 similarity)
    for remaining lines to handle variable-name-only differences.

    Returns 0.0 if P1 has no changed lines (degenerate case).
    """
    p1_lines = parse_patch_lines(p1_text)
    p2_lines = parse_patch_lines(p2_text)

    if not p1_lines:
        return 0.0

    # Exact matches
    exact = p1_lines & p2_lines
    # Fuzzy matches for remaining lines
    remaining_p1 = p1_lines - exact
    remaining_p2 = p2_lines - exact
    fuzzy = _fuzzy_match_count(remaining_p1, remaining_p2) if remaining_p1 and remaining_p2 else 0

    return (len(exact) + fuzzy) / len(p1_lines)


def classify_verification(score: float) -> str:
    """Classify a verification score into a human-readable label."""
    if score >= 1.0:
        return "hard_verified"
    elif score >= 0.5:
        return "soft_verified"
    elif score > 0.0:
        return "weakly_verified"
    else:
        return "unverified"


def verify_pair(p1_path: Path, p2_path: Path) -> dict:
    """Run soft verification on a pair of patch files.

    Returns a dict with score, classification, and line counts.
    """
    p1_text = p1_path.read_text(errors="replace")
    p2_text = p2_path.read_text(errors="replace")

    p1_lines = parse_patch_lines(p1_text)
    p2_lines = parse_patch_lines(p2_text)
    exact = p1_lines & p2_lines
    remaining_p1 = p1_lines - exact
    remaining_p2 = p2_lines - exact
    fuzzy = _fuzzy_match_count(remaining_p1, remaining_p2) if remaining_p1 and remaining_p2 else 0

    score = (len(exact) + fuzzy) / len(p1_lines) if p1_lines else 0.0

    return {
        "p1_file": str(p1_path),
        "p2_file": str(p2_path),
        "p1_changed_lines": len(p1_lines),
        "p2_changed_lines": len(p2_lines),
        "exact_match_lines": len(exact),
        "fuzzy_match_lines": fuzzy,
        "recall_score": round(score, 4),
        "classification": classify_verification(score),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Soft verification: compare two patches via line-level recall"
    )
    parser.add_argument("--p1", type=Path, required=True, help="Path to P1 (rollout 1 patch)")
    parser.add_argument("--p2", type=Path, required=True, help="Path to P2 (rollout 2 patch)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not args.p1.exists():
        sys.exit(f"P1 not found: {args.p1}")
    if not args.p2.exists():
        sys.exit(f"P2 not found: {args.p2}")

    result = verify_pair(args.p1, args.p2)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"P1 changed lines: {result['p1_changed_lines']}")
        print(f"P2 changed lines: {result['p2_changed_lines']}")
        print(f"Intersection:     {result['intersection_lines']}")
        print(f"Recall score:     {result['recall_score']}")
        print(f"Classification:   {result['classification']}")


if __name__ == "__main__":
    main()
