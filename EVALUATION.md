# Running Evaluations with mini-swe-agent

This document explains how to generate patches against the telecom ground-truth
test sets using `scripts/predict_patches.py` and the `hydron` agent.

---

## Test sets

| File | Instances | Notes |
|---|---|---|
| `groundtruth_telecom.jsonl` | 148 | Full telecom benchmark |
| `groundtruth_telecom_budget100.jsonl` | 100 | Budget subset for faster iteration |

Both files contain the full ground-truth schema (patch, commit SHA, etc.) but
`predict_patches.py` only reads the prompt fields — the ground-truth patch is
never exposed to the agent.

---

## Prerequisites

1. **uv** — `pip install uv` or `brew install uv`
2. **hydron binary** at `./hydron` in the repo root (or set `HYDRON_HOST_PATH`)
3. An LLM provider key (Google or OpenAI-compatible)

Install Python dependencies:

```bash
uv sync
```

---

## Generating predictions

### Google Gemini (recommended)

```bash
export GOOGLE_GENERATIVE_AI_API_KEY_1=<your-key>

uv run python scripts/predict_patches.py \
    --prompts groundtruth_telecom.jsonl \
    --model google/gemini-2.5-pro \
    --file-prefix telecom_gemini25pro \
    --workers 4 \
    --timeout-s 900
```

Output lands in:
- `eval_output/telecom_gemini25pro_predictions.jsonl`
- `eval_output/telecom_gemini25pro_logs/` (per-session trajectories)
- `eval_output/telecom_gemini25pro_predictions.jsonl.metadata.json`

### OpenAI-compatible endpoint (litellm / vLLM / etc.)

```bash
uv run python scripts/predict_patches.py \
    --prompts groundtruth_telecom.jsonl \
    --model qwen/qwen3-coder-480b-a35b-instruct-maas \
    --provider-url https://your-litellm-endpoint \
    --provider-key $LLM_API_KEY \
    --file-prefix telecom_qwen3coder \
    --workers 8
```

### Budget run (100 instances, quick sanity check)

```bash
uv run python scripts/predict_patches.py \
    --prompts groundtruth_telecom_budget100.jsonl \
    --model google/gemini-2.5-pro \
    --file-prefix budget100_gemini25pro \
    --workers 4 \
    --timeout-s 600
```

### Smoke test (5 instances)

```bash
uv run python scripts/predict_patches.py \
    --prompts groundtruth_telecom.jsonl \
    --model google/gemini-2.5-pro \
    --file-prefix smoke_test \
    --workers 2 \
    --limit 5
```

---

## Key flags

| Flag | Default | Description |
|---|---|---|
| `--prompts` | required | Ground-truth JSONL (prompts fields only used) |
| `--model` | required | Model identifier written into output |
| `--file-prefix` | — | Sets output paths under `eval_output/<prefix>_*` |
| `--output` | `predictions.jsonl` | Override output path directly |
| `--workers` | 1 | Parallel instances |
| `--timeout-s` | 600 | Per-session timeout (seconds) |
| `--num-predictions` | 1 | Runs per instance (pass@k) |
| `--limit` | — | Cap total instances |
| `--instance-ids` | — | Comma-separated filter for retries |
| `--cache-dir` | `data/predict_cache/repos` | Cloned repo cache |
| `--worktree-dir` | `data/predict_cache/worktrees` | Temporary worktrees |

---

## Resuming interrupted runs

The runner skips `(instance_id, run_index)` pairs already in the output file
that have a non-empty patch or `exit_code == 0`. Simply re-run the same
command to pick up where it left off.

To retry only failed instances, pass `--instance-ids` with a comma-separated
list, or delete their lines from the predictions file before re-running.

---

## Environment variables

| Variable | Description |
|---|---|
| `GOOGLE_GENERATIVE_AI_API_KEY_1` | Google key (add `_2`, `_3`, … for multiple keys) |
| `LLM_BASE_URL` | OpenAI-compatible base URL |
| `LLM_API_KEY` | API key for OpenAI-compatible endpoint |
| `HYDRON_HOST_PATH` | Path to hydron binary (default: `./hydron`) |
| `HYDRON_SESSION_TIMEOUT` | Per-session timeout override |
| `HYDRON_VARIANT` | Reasoning effort: `none` `minimal` `low` `medium` `high` `xhigh` (default: `low`) |
| `PROVIDER_MAX_INFLIGHT` | Max concurrent sessions per API key (default: 8) |

---

## Running on the GCE instance

```bash
ssh gcp-datagen
cd /mnt/repo-agents

export GOOGLE_GENERATIVE_AI_API_KEY_1=<key>

uv run python scripts/predict_patches.py \
    --prompts groundtruth_telecom.jsonl \
    --model google/gemini-2.5-pro \
    --file-prefix telecom_gemini25pro \
    --workers 8 \
    --timeout-s 900
```

Use `nohup` or `tmux` for long runs:

```bash
tmux new -s eval
# inside tmux:
uv run python scripts/predict_patches.py \
    --prompts groundtruth_telecom.jsonl \
    --model google/gemini-2.5-pro \
    --file-prefix telecom_gemini25pro \
    --workers 8
```

---

## Output schema

Each line in `predictions.jsonl`:

```json
{
  "instance_id": "open5gs__open5gs-51acc388a675",
  "model": "google/gemini-2.5-pro",
  "patch": "diff --git a/lib/dbi/ims.c ...",
  "exit_code": 0,
  "run_index": 0,
  "duration_s": 87.3,
  "session_id": "ses_..."
}
```

- `patch` — unified diff against `base_commit`; empty string on failure
- `exit_code` — `0` success, non-zero agent error, `-1` timeout/crash
