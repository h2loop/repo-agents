#!/usr/bin/env python3
"""
Export verified mini-swe-agent trajectories (T1 + T2) to datasets/miniswe-v1/.

Cohort: verified + both submitted (verification.json present, T1 and T2 both
"Submitted"). Tool message content over 16K chars is truncated to 8K head + 8K
tail with a marker. Token counts (chars // 4) are computed *after* truncation
and written to manifest.jsonl, one row per instance.

Usage:
    python scripts/export_miniswe_v1.py data/raw_telecom_batch/ \
        --out datasets/miniswe-v1
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

TRUNCATE_LIMIT = 16_000
HEAD = 8_000
TAIL = 8_000

INSTANCE_RE = re.compile(r"^(f\d+_b\d+_[a-f0-9]+)_(.+)$")


def truncate_tool_content(text: str) -> str:
    if len(text) <= TRUNCATE_LIMIT:
        return text
    omitted = len(text) - HEAD - TAIL
    return (
        text[:HEAD]
        + f"\n\n[... truncated {omitted} chars of tool output ...]\n\n"
        + text[-TAIL:]
    )


def discover_instances(raw_dir: Path) -> dict[str, dict[str, Path]]:
    instances: dict[str, dict[str, Path]] = defaultdict(dict)
    for entry in os.scandir(raw_dir):
        if not entry.is_file():
            continue
        m = INSTANCE_RE.match(entry.name)
        if m:
            prefix, suffix = m.groups()
            instances[prefix][suffix] = Path(entry.path)
    return dict(instances)


def load_json(path: Path) -> dict | None:
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def is_submitted(meta: dict | None) -> bool:
    if not meta:
        return False
    status = meta.get("agent_exit_status") or meta.get("exit_status")
    return status == "Submitted"


def process_trajectory(in_path: Path, out_path: Path) -> int:
    """Copy trajectory, truncating long tool messages. Return token count (chars // 4)."""
    total_chars = 0
    with open(in_path) as fin, open(out_path, "w") as fout:
        for line in fin:
            line = line.rstrip("\n")
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = msg.get("content")
            if msg.get("role") == "tool" and isinstance(content, str):
                msg["content"] = truncate_tool_content(content)
            fout.write(json.dumps(msg, ensure_ascii=False) + "\n")
            total_chars += len(str(msg.get("content") or ""))
    return total_chars // 4


def resolve_repo_folders(paths: list[str]) -> list[Path]:
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


def export_repo(repo_folder: Path, out_root: Path) -> tuple[int, int, list[dict]]:
    """Export one repo. Returns (n_exported, n_skipped, manifest_rows)."""
    raw_dir = repo_folder / "raw"
    repo_name = repo_folder.name

    instances = discover_instances(raw_dir)
    n_exported = 0
    n_skipped = 0
    rows: list[dict] = []

    for prefix, files in sorted(instances.items()):
        if not {"t1_meta.json", "t2_meta.json", "verification.json",
                "t1_trajectory.jsonl", "t2_trajectory.jsonl"} <= files.keys():
            n_skipped += 1
            continue

        t1_meta = load_json(files["t1_meta.json"])
        t2_meta = load_json(files["t2_meta.json"])
        if not (is_submitted(t1_meta) and is_submitted(t2_meta)):
            n_skipped += 1
            continue

        verification = load_json(files["verification.json"]) or {}
        classification = verification.get("classification", "unknown")
        if classification not in {"hard_verified", "soft_verified"}:
            n_skipped += 1
            continue

        sample_id = f"{repo_name}_{prefix}"
        t1_path = out_root / f"{sample_id}_t1.jsonl"
        t2_path = out_root / f"{sample_id}_t2.jsonl"
        t1_tokens = process_trajectory(files["t1_trajectory.jsonl"], t1_path)
        t2_tokens = process_trajectory(files["t2_trajectory.jsonl"], t2_path)

        rows.append({
            "id": sample_id,
            "repo": repo_name,
            "run_id": prefix,
            "classification": classification,
            "t1_tokens": t1_tokens,
            "t2_tokens": t2_tokens,
            "t1_path": str(t1_path.relative_to(out_root)),
            "t2_path": str(t2_path.relative_to(out_root)),
        })
        n_exported += 1

    return n_exported, n_skipped, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", help="Source folder(s) (parent of repo dirs, or a repo dir directly)")
    parser.add_argument("--out", default="datasets/miniswe-v1", help="Output root directory")
    args = parser.parse_args()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    repo_folders = resolve_repo_folders(args.folders)
    if not repo_folders:
        print("No repo folders with raw/ subdirectory found.", file=sys.stderr)
        sys.exit(1)

    all_rows: list[dict] = []
    cls_counter = Counter()
    for repo in repo_folders:
        exported, skipped, rows = export_repo(repo, out_root)
        all_rows.extend(rows)
        for r in rows:
            cls_counter[r["classification"]] += 1
        print(f"{repo.name}: exported {exported} instances, skipped {skipped}")

    manifest_path = out_root / "manifest.jsonl"
    with open(manifest_path, "w") as f:
        for row in all_rows:
            f.write(json.dumps(row) + "\n")
    print(f"\nWrote manifest: {manifest_path} ({len(all_rows)} rows)")
    print(f"Classification breakdown: {dict(cls_counter)}")


if __name__ == "__main__":
    main()
