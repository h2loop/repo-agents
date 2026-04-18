#!/usr/bin/env python
"""Collect verified t1/t2 trajectories across data/<repo>/raw/ into an SFT dataset and zip it."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
OUT_DIR = DATA_DIR / "sft_trajectories"
SCORE_THRESHOLD = 0.5


def iter_verified(raw_dir: Path):
    for vfile in raw_dir.glob("*_verification.json"):
        try:
            score = json.loads(vfile.read_text()).get("recall_score", 0)
        except (json.JSONDecodeError, OSError):
            continue
        if score is None or score <= SCORE_THRESHOLD:
            continue
        base = vfile.name[: -len("_verification.json")]
        yield base, score


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    total = 0
    for repo_dir in sorted(p for p in DATA_DIR.iterdir() if p.is_dir()):
        raw = repo_dir / "raw"
        if not raw.is_dir():
            continue
        copied = 0
        for base, _ in iter_verified(raw):
            for kind in ("t1", "t2"):
                src = raw / f"{base}_{kind}_trajectory.jsonl"
                if src.is_file():
                    shutil.copy2(src, OUT_DIR / f"{base}_{kind}.jsonl")
                    copied += 1
        print(f"{repo_dir.name}: copied {copied} trajectory files")
        total += copied

    print(f"Total trajectory files: {total}")

    archive = shutil.make_archive(str(OUT_DIR), "zip", root_dir=OUT_DIR)
    print(f"Wrote archive: {archive}")


if __name__ == "__main__":
    main()
