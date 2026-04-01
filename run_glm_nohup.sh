#!/bin/bash
# SERA generation with GLM model — runs in background, survives lid close
# Logs: data/{repo}/glm_generation.log
# Progress: ls data/{repo}/raw/*_verification.json | wc -l

cd /Users/metamyth/projects/sera

echo "Starting SERA GLM generation at $(date)"
echo "Model: vertex_ai/zai-org/glm-5-maas"
echo "Samples per repo: 1000, Workers per repo: 1 (GLM is slow, avoid concurrent overload)"
echo ""

# Zephyr
nohup python3 scripts/generate_data_generic.py \
    --repo-name zephyr \
    --repo-root repos/zephyr \
    --functions data/zephyr/functions.jsonl \
    --bug-prompts configs/bug_prompts_generic.json \
    --template configs/bug_prompt_template.txt \
    --output-dir data/zephyr/raw \
    --docker-image sera-zephyr:latest \
    --num-samples 1000 \
    --workers 1 \
    --seed 42 \
    --resume \
    > data/zephyr/glm_generation.log 2>&1 &
PID_Z=$!

# NuttX
nohup python3 scripts/generate_data_generic.py \
    --repo-name nuttx \
    --repo-root repos/nuttx \
    --functions data/nuttx/functions.jsonl \
    --bug-prompts configs/bug_prompts_generic.json \
    --template configs/bug_prompt_template.txt \
    --output-dir data/nuttx/raw \
    --docker-image sera-nuttx:latest \
    --num-samples 1000 \
    --workers 1 \
    --seed 123 \
    --resume \
    > data/nuttx/glm_generation.log 2>&1 &
PID_N=$!

# Mbed-OS
nohup python3 scripts/generate_data_generic.py \
    --repo-name mbed-os \
    --repo-root repos/mbed-os \
    --functions data/mbed-os/functions.jsonl \
    --bug-prompts configs/bug_prompts_generic.json \
    --template configs/bug_prompt_template.txt \
    --output-dir data/mbed-os/raw \
    --docker-image sera-mbed-os:latest \
    --num-samples 1000 \
    --workers 1 \
    --seed 456 \
    --resume \
    > data/mbed-os/glm_generation.log 2>&1 &
PID_M=$!

echo "Launched all 3 repos:"
echo "  Zephyr:  PID=$PID_Z  log=data/zephyr/glm_generation.log"
echo "  NuttX:   PID=$PID_N  log=data/nuttx/glm_generation.log"
echo "  Mbed-OS: PID=$PID_M  log=data/mbed-os/glm_generation.log"
echo ""
echo "PIDs saved to data/glm_pids.txt"
echo "$PID_Z $PID_N $PID_M" > data/glm_pids.txt

echo ""
echo "Monitor progress:"
echo "  tail -f data/zephyr/glm_generation.log"
echo "  tail -f data/nuttx/glm_generation.log"
echo "  tail -f data/mbed-os/glm_generation.log"
echo ""
echo "Quick status:"
echo "  for r in zephyr nuttx mbed-os; do echo \"\$r: \$(ls data/\$r/raw/*_verification.json 2>/dev/null | wc -l) verified\"; done"
echo ""
echo "Safe to close laptop lid now."
