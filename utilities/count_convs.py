#!/usr/bin/env python3
"""Count JSON files where 'conversations' list has length > 2."""

import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <directory>")
        sys.exit(1)

    directory = Path(sys.argv[1])
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory")
        sys.exit(1)

    total = 0
    above_two = 0

    for json_file in directory.glob("*.json"):
        total += 1
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"Skipping {json_file.name}: {e}", file=sys.stderr)
            continue

        conversations = data.get("conversations")
        if isinstance(conversations, list) and len(conversations) > 2:
            above_two += 1

    print(f"Files with conversations > 2: {above_two}")
    print(f"Total JSON files: {total}")


if __name__ == "__main__":
    main()
