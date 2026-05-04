#!/usr/bin/env python3
"""
Report data-generation status for one or more repo output directories.

Usage:
    python scripts/data_generation_status.py data/raw_telecom_batch/kamailio-kamailio
    python scripts/data_generation_status.py data/raw_telecom_batch/*

Each target folder is expected to contain a raw/ subdirectory with files like:
    f00000_b0_217ee3_t1_meta.json
    f00000_b0_217ee3_t2_meta.json
    f00000_b0_217ee3_verification.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


def discover_instances(raw_dir: Path) -> dict[str, dict[str, Path]]:
    """Group files by instance prefix (e.g. f00000_b0_217ee3)."""
    instances: dict[str, dict[str, Path]] = defaultdict(dict)
    pattern = re.compile(r"^(f\d+_b\d+_[a-f0-9]+)_(.+)$")
    for entry in os.scandir(raw_dir):
        if not entry.is_file():
            continue
        m = pattern.match(entry.name)
        if m:
            prefix, suffix = m.groups()
            instances[prefix][suffix] = Path(entry.path)
    return dict(instances)


def load_meta(path: Path) -> dict | None:
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def analyze_folder(folder: Path) -> dict:
    raw_dir = folder / "raw"
    if not raw_dir.is_dir():
        return {"error": f"No raw/ directory in {folder}"}

    instances = discover_instances(raw_dir)
    total_instances = len(instances)

    t1_submitted = 0
    t1_other_status = Counter()
    t2_submitted = 0
    t2_other_status = Counter()
    both_submitted = 0

    verified_count = 0
    verification_classes = Counter()
    verified_and_both_submitted = 0

    for prefix, files in instances.items():
        t1_ok = False
        t2_ok = False

        # T1
        if "t1_meta.json" in files:
            meta = load_meta(files["t1_meta.json"])
            if meta:
                status = meta.get("agent_exit_status")
                if status == "Submitted":
                    t1_submitted += 1
                    t1_ok = True
                else:
                    t1_other_status[str(status)] += 1

        # T2
        if "t2_meta.json" in files:
            meta = load_meta(files["t2_meta.json"])
            if meta:
                status = meta.get("agent_exit_status")
                if status == "Submitted":
                    t2_submitted += 1
                    t2_ok = True
                else:
                    t2_other_status[str(status)] += 1

        if t1_ok and t2_ok:
            both_submitted += 1

        # Verification
        if "verification.json" in files:
            verified_count += 1
            vdata = load_meta(files["verification.json"])
            if vdata:
                cls = vdata.get("classification", "unknown")
                verification_classes[cls] += 1
                if t1_ok and t2_ok:
                    verified_and_both_submitted += 1

    return {
        "folder": str(folder),
        "total_instances": total_instances,
        "t1_submitted": t1_submitted,
        "t1_other_status": dict(t1_other_status),
        "t2_submitted": t2_submitted,
        "t2_other_status": dict(t2_other_status),
        "both_submitted": both_submitted,
        "verified_count": verified_count,
        "verification_classes": dict(verification_classes),
        "verified_and_both_submitted": verified_and_both_submitted,
    }


def print_report(stats: dict) -> None:
    if "error" in stats:
        print(f"  ERROR: {stats['error']}")
        return

    total = stats["total_instances"]
    print(f"  Total instances:        {total}")
    print(f"  T1 submitted:           {stats['t1_submitted']}")
    if stats["t1_other_status"]:
        for status, count in sorted(stats["t1_other_status"].items(), key=lambda x: -x[1]):
            print(f"    T1 {status}: {count}")
    print(f"  T2 submitted:           {stats['t2_submitted']}")
    if stats["t2_other_status"]:
        for status, count in sorted(stats["t2_other_status"].items(), key=lambda x: -x[1]):
            print(f"    T2 {status}: {count}")
    print(f"  Both submitted:         {stats['both_submitted']}")
    print(f"  Verified:               {stats['verified_count']}")
    if stats["verification_classes"]:
        for cls, count in sorted(stats["verification_classes"].items(), key=lambda x: -x[1]):
            print(f"    {cls}: {count}")
    print(f"  Verified + both done:   {stats['verified_and_both_submitted']}")


def resolve_folders(paths: list[str]) -> list[Path]:
    """If a path contains raw/ directly, use it. Otherwise scan for subdirs with raw/."""
    folders = []
    for p in paths:
        path = Path(p)
        if not path.is_dir():
            continue
        if (path / "raw").is_dir():
            folders.append(path)
        else:
            for child in sorted(path.iterdir()):
                if child.is_dir() and (child / "raw").is_dir():
                    folders.append(child)
    return folders


def main():
    parser = argparse.ArgumentParser(description="Data generation status report")
    parser.add_argument("folders", nargs="+", help="Target folder(s) or parent directory containing repo subfolders")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    folders = resolve_folders(args.folders)
    if not folders:
        print("No folders with raw/ subdirectory found.", file=sys.stderr)
        sys.exit(1)

    results = []
    for folder in folders:
        results.append(analyze_folder(folder))

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for stats in results:
            print(f"\n{'='*60}")
            print(f"  {stats['folder']}")
            print(f"{'='*60}")
            print_report(stats)

        # Summary if multiple folders
        if len(results) > 1:
            valid = [r for r in results if "error" not in r]
            if valid:
                print(f"\n{'='*60}")
                print(f"  TOTAL (across {len(valid)} repos)")
                print(f"{'='*60}")
                print(f"  Total instances:        {sum(r['total_instances'] for r in valid)}")
                print(f"  T1 submitted:           {sum(r['t1_submitted'] for r in valid)}")
                print(f"  T2 submitted:           {sum(r['t2_submitted'] for r in valid)}")
                print(f"  Both submitted:         {sum(r['both_submitted'] for r in valid)}")
                print(f"  Verified:               {sum(r['verified_count'] for r in valid)}")
                print(f"  Verified + both done:   {sum(r['verified_and_both_submitted'] for r in valid)}")


if __name__ == "__main__":
    main()
