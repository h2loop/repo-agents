#!/usr/bin/env bash
#
# Post-generation pipeline: filter data + format for SFT training.
# Run this after generate_data.py has produced samples in data/raw/
#
# Usage:
#   ./scripts/run_post_generation.sh [--max-tokens 32768]
#

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON=".venv/bin/python"
MAX_TOKENS="${1:-32768}"

echo "=== Phase 6: Filtering data ==="
$PYTHON scripts/filter_data.py \
  --input-dir data/raw \
  --output-dir data/filtered \
  --max-patch-lines 40 \
  --max-avg-tool-tokens 600 \
  --min-truncation-ratio 0.88 \
  --max-tokens "$MAX_TOKENS" \
  --target-t1 5000 \
  --target-t2 3000

echo ""
echo "=== Phase 7: Formatting for SFT training ==="
$PYTHON scripts/format_for_training.py \
  --selection data/filtered/selected_samples.jsonl \
  --output-dir data/sft_dataset \
  --held-out-ratio 0.10 \
  --max-tokens "$MAX_TOKENS"

echo ""
echo "=== Done ==="
echo "Training data: data/sft_dataset/oai5g_train.jsonl"
echo "Held-out data: data/sft_dataset/oai5g_held_out.jsonl"
echo "Stats: data/sft_dataset/dataset_stats.json"
