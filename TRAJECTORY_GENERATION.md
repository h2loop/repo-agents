# Trajectory Generation

Generates SFT training trajectories using hydron (coding agent) inside Docker containers.

## Pipeline

```
rollout1 (bug fix) → generate_pr (synthetic PR) → rollout2 (reproduce from PR) → soft_verify (compare patches)
```

## Prerequisites

- Docker Desktop running
- Docker image built: `srsran-sera:latest` (ARM64)
- `hydron` binary (Linux ARM64) at repo root
- LiteLLM proxy accessible (default: `https://litellm-prod-909645453767.asia-south1.run.app`)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_BASE_URL` | `https://litellm-prod-909645453767.asia-south1.run.app` | OpenAI-compatible endpoint |
| `LLM_API_KEY` | `sk-1234` | API key for the provider |
| `LLM_MODEL` | `qwen/qwen3-coder-480b-a35b-instruct-maas` | Model ID |
| `HYDRON_HOST_PATH` | `./hydron` | Path to hydron binary on host |

## Quick Start

### Single rollout1 (one trajectory)

```bash
python scripts/rollout1.py \
  --functions data/srsran_functions.jsonl \
  --bug-prompts configs/bug_prompts_srsran.json \
  --template configs/bug_prompt_template.txt \
  --container srsran-sera:latest \
  --output-dir data/raw_test \
  --num-samples 1 \
  --seed 42
```

Output: `data/raw_test/{run_id}_t1_trajectory.jsonl`, `_p1.diff`, `_t1_meta.json`

### Full pipeline (rollout1 + PR + rollout2 + verify)

```bash
python scripts/generate_data.py \
  --functions data/srsran_functions.jsonl \
  --bug-prompts configs/bug_prompts_srsran.json \
  --template configs/bug_prompt_template.txt \
  --commits configs/commits.json \
  --demo-prs-dir configs/demo_prs \
  --output-dir data/raw \
  --max-samples 5 \
  --workers 1
```

Scale up with `--workers 4` (each worker gets its own Docker container).

Add `--resume` to skip already-completed functions.

### Format for SFT training

```bash
python scripts/format_for_training.py \
  --input-dir data/raw \
  --output-dir data/sft
```

## Architecture

- **hydron_runner.py** — Runs hydron inside Docker containers via `docker exec`. Handles provider setup (persists LiteLLM config into hydron's DB on container start), session execution, export via `docker cp`, and patch extraction.
- **trajectory_converter.py** — Converts hydron's session export JSON to SERA JSONL format (adds step numbers, extracts tool metadata, strips `<think>` blocks).
- **rollout1.py** — Change generation: picks a function + bug type, runs hydron to fix it, saves trajectory + patch. Includes container lifecycle and pooling.
- **rollout2.py** — Reproduction: given a synthetic PR description, runs hydron to implement it independently.
- **generate_data.py** — Orchestrator: runs the full 4-stage pipeline with parallel workers and container pools.

## Config Files

- `configs/repo_config.json` — Target repo settings (Docker image, paths, build caveats)
- `configs/bug_prompts_srsran.json` — Bug type descriptions for rollout1
- `configs/bug_prompt_template.txt` — Prompt template with `{func_name}`, `{file_path}`, etc.
- `configs/commits.json` — Commit snapshots to use as Docker images
- `configs/demo_prs/` — Example PRs for few-shot PR generation

## How It Works

1. Container starts with hydron binary mounted at `/hydron`
2. `setup_provider()` runs hydron TUI briefly to persist LiteLLM endpoint config in hydron's SQLite DB
3. `hydron run --auto --format json -m <provider>/<model> "<prompt>"` executes the agent session
4. Session export is copied out via `docker cp` and converted to SERA JSONL format
5. `git diff` inside the container captures the patch
