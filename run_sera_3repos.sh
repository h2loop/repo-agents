#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

NUM_SAMPLES=${1:-1000}
WORKERS=${2:-4}

echo "============================================="
echo "  SERA Data Generation — 3 Repos Concurrent"
echo "  Samples per repo: $NUM_SAMPLES"
echo "  Workers per repo: $WORKERS"
echo "============================================="

# Step 1: Build Docker images (if not already built)
echo ""
echo ">>> Step 1: Building Docker images..."
bash docker/build_images.sh

# Step 2: Extract functions (if not already extracted)
echo ""
echo ">>> Step 2: Extracting functions..."

mkdir -p data/zephyr data/nuttx data/mbed-os

if [ ! -f data/zephyr/functions.jsonl ]; then
    echo "  Extracting zephyr functions..."
    python3 scripts/extract_functions_generic.py \
        --repo-root repos/zephyr \
        --output data/zephyr/functions.jsonl &
fi

if [ ! -f data/nuttx/functions.jsonl ]; then
    echo "  Extracting nuttx functions..."
    python3 scripts/extract_functions_generic.py \
        --repo-root repos/nuttx \
        --output data/nuttx/functions.jsonl &
fi

if [ ! -f data/mbed-os/functions.jsonl ]; then
    echo "  Extracting mbed-os functions..."
    python3 scripts/extract_functions_generic.py \
        --repo-root repos/mbed-os \
        --output data/mbed-os/functions.jsonl &
fi

wait
echo "  Function extraction complete."

# Step 3: Launch concurrent generation
echo ""
echo ">>> Step 3: Launching SERA generation (3 repos concurrently)..."
echo "  Logs: data/{repo}/generation.log"

mkdir -p data/zephyr/raw data/nuttx/raw data/mbed-os/raw

python3 scripts/generate_data_generic.py \
    --repo-name zephyr \
    --repo-root repos/zephyr \
    --functions data/zephyr/functions.jsonl \
    --bug-prompts configs/bug_prompts_generic.json \
    --template configs/bug_prompt_template.txt \
    --demo-prs-dir configs/demo_prs \
    --output-dir data/zephyr/raw \
    --docker-image sera-zephyr:latest \
    --num-samples "$NUM_SAMPLES" \
    --workers "$WORKERS" \
    --resume \
    2>&1 | tee data/zephyr/generation.log &
PID_ZEPHYR=$!

python3 scripts/generate_data_generic.py \
    --repo-name nuttx \
    --repo-root repos/nuttx \
    --functions data/nuttx/functions.jsonl \
    --bug-prompts configs/bug_prompts_generic.json \
    --template configs/bug_prompt_template.txt \
    --demo-prs-dir configs/demo_prs \
    --output-dir data/nuttx/raw \
    --docker-image sera-nuttx:latest \
    --num-samples "$NUM_SAMPLES" \
    --workers "$WORKERS" \
    --seed 123 \
    --resume \
    2>&1 | tee data/nuttx/generation.log &
PID_NUTTX=$!

python3 scripts/generate_data_generic.py \
    --repo-name mbed-os \
    --repo-root repos/mbed-os \
    --functions data/mbed-os/functions.jsonl \
    --bug-prompts configs/bug_prompts_generic.json \
    --template configs/bug_prompt_template.txt \
    --demo-prs-dir configs/demo_prs \
    --output-dir data/mbed-os/raw \
    --docker-image sera-mbed-os:latest \
    --num-samples "$NUM_SAMPLES" \
    --workers "$WORKERS" \
    --seed 456 \
    --resume \
    2>&1 | tee data/mbed-os/generation.log &
PID_MBEDOS=$!

echo ""
echo "  PIDs: zephyr=$PID_ZEPHYR  nuttx=$PID_NUTTX  mbed-os=$PID_MBEDOS"
echo "  Waiting for all to complete..."

wait $PID_ZEPHYR
echo "  [DONE] Zephyr"
wait $PID_NUTTX
echo "  [DONE] NuttX"
wait $PID_MBEDOS
echo "  [DONE] Mbed-OS"

echo ""
echo "============================================="
echo "  All 3 repos completed!"
echo "  Manifests:"
echo "    data/zephyr/raw/generation_manifest.json"
echo "    data/nuttx/raw/generation_manifest.json"
echo "    data/mbed-os/raw/generation_manifest.json"
echo "============================================="
