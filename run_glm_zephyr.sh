#!/bin/bash
cd /Users/metamyth/projects/sera

caffeinate -i nohup python3 scripts/generate_data_generic.py \
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

echo "$!" > data/glm_pids.txt
echo "Launched PID: $!"
