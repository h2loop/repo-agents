# Running Evaluations with mini-swe-agent

This document explains how to generate patches against the telecom ground-truth
test sets using `scripts/predict_patches.py`, which drives `mini-swe-agent`
inside a fresh Docker container per prediction.

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
2. **Docker** — the runner starts one container per prediction
3. An LLM provider key (Google or OpenAI-compatible)

Install Python dependencies:

```bash
uv sync
```

The default container image is `python:3.12-slim`. The runner installs
`bash`, `git`, and `ca-certificates` inside the container automatically on
first use (apt / apk / dnf / yum / microdnf are all supported), so no
prebuilt image is required. Pass `--container-image` to override.

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
- `eval_output/telecom_gemini25pro_logs/` (per-session trajectories — full
  mini-swe-agent message lists)
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
| `--prompts` | required | Ground-truth JSONL (prompt fields only used) |
| `--model` | required | Model identifier written into output and routed to mini_runner |
| `--container-image` | `python:3.12-slim` | Docker image for each prediction. Bash/git/ca-certificates installed automatically if missing |
| `--container-repo-path` | `/repo` | Path inside the container to clone into |
| `--file-prefix` | — | Sets output paths under `eval_output/<prefix>_*` |
| `--output` | `predictions.jsonl` | Override output path directly |
| `--workers` | 1 | Parallel instances |
| `--timeout-s` | 600 | Per-bash-command timeout inside the container (`MINI_EXEC_TIMEOUT`) |
| `--num-predictions` | 1 | Runs per instance (pass@k) |
| `--limit` | — | Cap total instances |
| `--instance-ids` | — | Comma-separated filter for retries |
| `--eval-logs-dir` | `eval_logs` | Per-session trajectory JSON output |

A prompt line may also include an optional `image` field to override
`--container-image` for that specific instance.

---

## Resuming interrupted runs

The runner skips `(instance_id, run_index)` pairs already in the output file
that have a non-empty patch or `exit_code == 0`. Simply re-run the same
command to pick up where it left off.

To retry only failed instances, pass `--instance-ids` with a comma-separated
list, or delete their lines from the predictions file before re-running.

---

## Environment variables

Provider configuration is read from the environment by `mini_runner` at
import time. `--provider-url` / `--provider-key` populate the corresponding
env vars before import as a convenience.

| Variable | Description |
|---|---|
| `GOOGLE_GENERATIVE_AI_API_KEY_1` | Google key (add `_2`, `_3`, … for multiple keys; round-robin'd per trajectory) |
| `GOOGLE_MODEL` | Model id used with Google keys (default `gemini-2.5-pro`) |
| `GEMINI_BASE_URL` | If set, uses Google's OpenAI-compatible endpoint instead of native |
| `LLM_BASE_URL` | OpenAI-compatible base URL |
| `LLM_API_KEY` | API key for OpenAI-compatible endpoint |
| `LLM_MODEL` | OpenAI-compatible model id |
| `BEDROCK_KEY` | AWS Bedrock bearer token (adds Bedrock to provider pool) |
| `BEDROCK_MODEL` | Bedrock model id (default `bedrock/converse/zai.glm-4.7`) |
| `PROVIDER_MAX_INFLIGHT` | Max concurrent LLM calls per API key (default: 8) |
| `MINI_STEP_LIMIT` | Max agent steps per trajectory (default: 75) |
| `MINI_COST_LIMIT` | Cost cap per trajectory in USD (default: 0 = disabled) |
| `MINI_EXEC_TIMEOUT` | Per-bash-command timeout (default: 600s; same as `--timeout-s`) |
| `MINI_MAX_TRAJECTORY_TOKENS` | Hard cap on trajectory input tokens (default: 128k) |
| `MINI_EXEC_OUTPUT_MAX_BYTES` | Hard cap on stdout/stderr stored per command (default: 32 KiB) |
| `MINI_MSG_RATE_LIMIT_RETRIES` | Per-call rate-limit retry cap (default: 10) |
| `RATE_LIMIT_BASE_BACKOFF` | Initial rate-limit backoff seconds (default: 10) |
| `RATE_LIMIT_MAX_BACKOFF` | Max single rate-limit backoff seconds (default: 300) |
| `CONTAINER_MEMORY_LIMIT` | Per-container memory cap (default: 4g) |

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

If a run is killed mid-flight, leftover containers are labeled
`repo_evals_predict=1`; clean them up with:

```bash
docker ps -q --filter label=repo_evals_predict=1 | xargs -r docker kill
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

- `patch` — unified diff against `base_commit` (tracked + untracked files);
  empty string on failure
- `exit_code` — `0` when mini-swe-agent's `exit_status` is `Submitted`,
  `1` for other terminal statuses (limits exceeded, agent error),
  `-1` for setup/infrastructure failures

Per-session trajectory JSON (in `--eval-logs-dir`) includes the full
`messages` list, `provider_label`, `model`, `exit_status`, `submission`,
`n_calls`, and `cost`.
