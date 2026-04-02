#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# SERA SVG Pipeline for OpenAirInterface 5G
#
# Full end-to-end pipeline using SWE-agent:
#   1. Create instance YAML from functions + bugs + commits
#   2. Stage 1: SWE-agent rollouts with pipeline mode (rollout 1 + self-eval + synthetic PR)
#   3. Scrape synthetic PRs from stage 1 output into stage 2 instances
#   4. Stage 2: SWE-agent rollouts using synthetic PRs
#   5. Soft verification (compare P1 vs P2 patches)
#   6. Filter + format into SFT training data
#
# Usage:
#   cd /Users/metamyth/projects/sera
#   nohup caffeinate -s bash scripts/run_sera_pipeline.sh > data/sweagent_run/pipeline.log 2>&1 &
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Activate venv
source "$PROJECT_DIR/.venv/bin/activate"

# --- Load repo configuration ---
REPO_CONFIG="$PROJECT_DIR/configs/repo_config.json"

if [ ! -f "$REPO_CONFIG" ]; then
    echo "ERROR: repo_config.json not found at $REPO_CONFIG" >&2
    exit 1
fi

REPO_SHORT_NAME=$(python3 -c "import json; print(json.load(open('$REPO_CONFIG'))['repo_short_name'])")
FUNCTIONS_FILE_REL=$(python3 -c "import json; print(json.load(open('$REPO_CONFIG')).get('functions_file', 'data/${REPO_SHORT_NAME}_functions.jsonl'))")

# --- Configuration ---
NUM_SAMPLES=${NUM_SAMPLES:-1000}
NUM_WORKERS=${NUM_WORKERS:-8}
SEED=${SEED:-42}

FUNCTIONS_FILE="$PROJECT_DIR/$FUNCTIONS_FILE_REL"
BUG_PROMPTS_REL=$(python3 -c "import json; print(json.load(open('$REPO_CONFIG')).get('bug_prompts_file', 'configs/bug_prompts.json'))")
BUG_PROMPTS="$PROJECT_DIR/$BUG_PROMPTS_REL"
COMMITS_FILE="$PROJECT_DIR/configs/commits.json"

STAGE_ONE_CONFIG="configs/sweagent/stage_one.yaml"
STAGE_TWO_CONFIG="configs/sweagent/stage_two.yaml"
PIPELINE_YAML="configs/pipeline/oai5g_pipeline.yaml"

DATA_DIR="$PROJECT_DIR/data/sweagent_run"
STAGE_ONE_INSTANCES="$DATA_DIR/stage_one_instances.yaml"
STAGE_TWO_INSTANCES="$DATA_DIR/stage_two_instances.yaml"
STAGE_ONE_OUTPUT="$DATA_DIR/stage_one_output"
STAGE_TWO_OUTPUT="$DATA_DIR/stage_two_output"

mkdir -p "$DATA_DIR"

echo "============================================"
echo "SERA SVG Pipeline for OAI5G"
echo "  Samples: $NUM_SAMPLES"
echo "  Workers: $NUM_WORKERS"
echo "  Seed:    $SEED"
echo "  Started: $(date)"
echo "============================================"

# --- Step 1: Create instances ---
echo ""
echo "[Step 1/6] Creating stage 1 instances..."
if [ ! -f "$STAGE_ONE_INSTANCES" ]; then
    python "$SCRIPT_DIR/create_instances.py" \
        --functions "$FUNCTIONS_FILE" \
        --bug-prompts "$BUG_PROMPTS" \
        --commits "$COMMITS_FILE" \
        --output "$STAGE_ONE_INSTANCES" \
        --num-samples "$NUM_SAMPLES" \
        --seed "$SEED"
else
    echo "  Instances file already exists, skipping. Delete to regenerate."
fi

# --- Step 2: Stage 1 — SWE-agent with pipeline mode ---
echo ""
echo "[Step 2/6] Running stage 1 (rollout 1 + self-eval + synthetic PR)..."
echo "  Started: $(date)"
.venv/bin/sweagent run-batch \
    --config "$STAGE_ONE_CONFIG" \
    --num_workers "$NUM_WORKERS" \
    --instances.type file \
    --instances.path "$STAGE_ONE_INSTANCES" \
    --instances.shuffle True \
    --output_dir "$STAGE_ONE_OUTPUT" \
    --pipeline True \
    --pipeline_yaml "$PIPELINE_YAML"
echo "  Stage 1 finished: $(date)"
STAGE_ONE_GOOD=$(grep -rl '"is_good_patch": true' "$STAGE_ONE_OUTPUT/" 2>/dev/null | wc -l | tr -d ' ')
STAGE_ONE_TOTAL=$(find "$STAGE_ONE_OUTPUT" -name "*.synth" 2>/dev/null | wc -l | tr -d ' ')
echo "  Stage 1 results: $STAGE_ONE_GOOD good / $STAGE_ONE_TOTAL total"

# --- Step 3: Scrape synthetic PRs into stage 2 instances ---
echo ""
echo "[Step 3/6] Scraping synthetic PRs from stage 1..."
if [ ! -f "$STAGE_TWO_INSTANCES" ]; then
    python "$SCRIPT_DIR/scrape_stage_one.py" \
        --stage-one-instances "$STAGE_ONE_INSTANCES" \
        --stage-one-output "$STAGE_ONE_OUTPUT" \
        --output "$STAGE_TWO_INSTANCES"
else
    echo "  Stage 2 instances already exist, skipping."
fi

# --- Step 4: Stage 2 — SWE-agent with synthetic PRs ---
echo ""
echo "[Step 4/6] Running stage 2 (rollout 2 with synthetic PRs)..."
echo "  Started: $(date)"
.venv/bin/sweagent run-batch \
    --config "$STAGE_TWO_CONFIG" \
    --num_workers "$NUM_WORKERS" \
    --instances.type file \
    --instances.path "$STAGE_TWO_INSTANCES" \
    --instances.shuffle True \
    --output_dir "$STAGE_TWO_OUTPUT"
echo "  Stage 2 finished: $(date)"

# --- Step 5: Soft verification ---
echo ""
echo "[Step 5/6] Running soft verification (comparing P1 vs P2 patches)..."
python "$SCRIPT_DIR/verify_patches.py" \
    --stage-one-output "$STAGE_ONE_OUTPUT" \
    --stage-two-output "$STAGE_TWO_OUTPUT" \
    --stage-two-instances "$STAGE_TWO_INSTANCES" \
    --output-dir "$DATA_DIR/verification"

# --- Step 6: Filter + format ---
echo ""
echo "[Step 6/6] Filtering and formatting into SFT dataset..."
python "$SCRIPT_DIR/postprocess_sweagent.py" \
    --stage-one-output "$STAGE_ONE_OUTPUT" \
    --stage-two-output "$STAGE_TWO_OUTPUT" \
    --verification-dir "$DATA_DIR/verification" \
    --stage-one-instances "$STAGE_ONE_INSTANCES" \
    --stage-two-instances "$STAGE_TWO_INSTANCES" \
    --output-dir "$PROJECT_DIR/data/sft_dataset"

echo ""
echo "============================================"
echo "Pipeline complete!"
echo "  Finished: $(date)"
echo "  SFT dataset: $PROJECT_DIR/data/sft_dataset/"
echo "============================================"
