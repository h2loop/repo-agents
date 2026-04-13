# Trajectory Generation

Generates SFT training trajectories using hydron (coding agent) inside Docker containers.

## Pipeline

```
rollout1 (bug fix) → generate_pr (synthetic PR) → rollout2 (reproduce from PR) → soft_verify (compare patches)
```

See [pipeline.md](pipeline.md) for a detailed description of the pipeline design and rationale.

## Prerequisites

- Docker running
- Docker images built for target repo (e.g. `srsran-sera:latest`)
- `hydron` binary (must match container arch — Linux ARM64 for Apple Silicon, Linux x64 for cloud VMs)
- LLM endpoint accessible (default: LiteLLM proxy)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_BASE_URL` | `https://litellm-prod-909645453767.asia-south1.run.app` | OpenAI-compatible endpoint |
| `LLM_API_KEY` | `sk-1234` | API key for the provider |
| `LLM_MODEL` | `qwen/qwen3-coder-480b-a35b-instruct-maas` | Model ID |
| `HYDRON_HOST_PATH` | `./hydron` | Path to hydron binary on host |

## Quick Start

### 1. Extract functions from target repo

```bash
uv run python scripts/extract_functions_generic.py \
  --repo-root /path/to/target_repo \
  --output data/functions.jsonl
```

Supports C, C++, and Go via tree-sitter.

### 2. Build Docker images

```bash
for sha in <commit1> <commit2> ...; do
  docker build -t "repo-sera:${sha:0:7}" \
    --build-arg REPO_DIR=TargetRepo \
    --build-arg REPO_COMMIT="${sha}" \
    -f docker/Dockerfile.sera .
done
```

### 3. Run the pipeline

```bash
uv run python scripts/generate_data.py \
  --functions data/functions.jsonl \
  --bug-prompts configs/bug_prompts_<repo>.json \
  --template configs/bug_prompt_template.txt \
  --commits configs/commits.json \
  --demo-prs-dir configs/demo_prs \
  --output-dir data/raw \
  --max-steps 50 \
  --workers 4 \
  --resume
```

### 4. Format for SFT training

```bash
uv run python scripts/format_for_training.py \
  --input-dir data/raw \
  --output-dir data/sft
```

## Architecture

- **hydron_runner.py** — Runs hydron inside Docker containers via `docker exec` with `--skip-auth --provider-url --provider-key --provider-model` flags. Handles session execution, export via `docker cp`, and patch extraction. Supports `--max-steps`.
- **trajectory_converter.py** — Converts hydron's session export JSON to SERA JSONL format (adds step numbers, extracts tool metadata, strips `<think>` blocks).
- **rollout1.py** — Change generation: picks a function + bug type, runs hydron to fix it, saves trajectory + patch. Includes container lifecycle and pooling.
- **rollout2.py** — Reproduction: given a synthetic PR description, runs hydron to implement it independently.
- **generate_data.py** — Orchestrator: runs the full 4-stage pipeline with parallel workers and container pools.
- **extract_functions_generic.py** — Extracts functions from C/C++/Go repos via tree-sitter.
- **populate_repo_config.py** — Generates `repo_config.json` and assembled bug prompts for a new target repo.

## Config Files

- `configs/repo_config.json` — Target repo settings (language, domain, Docker image, paths)
- `configs/bug_prompts/lang_c.json` — Generic C/C++ bug types (40)
- `configs/bug_prompts/lang_go.json` — Generic Go bug types (29)
- `configs/bug_prompts/domain_telecom_5g.json` — Telecom domain bugs with canonical subsystem paths (25)
- `configs/bug_prompts_<repo>.json` — Assembled per-repo bug prompts (language + remapped domain)
- `configs/bug_prompt_template.txt` — Prompt template with `{func_name}`, `{file_path}`, etc.
- `configs/commits.json` — Commit snapshots to use as Docker images
- `configs/demo_prs/` — Example PRs for few-shot PR generation

## Bug Prompt Architecture

Bug prompts are assembled from two independent dimensions:

1. **Language bugs** (`configs/bug_prompts/lang_*.json`) — language-specific issues (e.g. buffer overflows for C, goroutine leaks for Go). No subsystem restrictions — match all functions.
2. **Domain bugs** (`configs/bug_prompts/domain_*.json`) — domain-specific issues (e.g. telecom protocol bugs). Have canonical subsystem paths that get remapped per-repo by `populate_repo_config.py`.

`repo_config.json` specifies `"language"` and `"domain"` fields. The assembled file (`bug_prompts_<repo>.json`) is the single file the pipeline reads at runtime.

## How It Works

1. Container starts with hydron binary mounted at `/hydron`
2. `hydron run --auto --skip-auth --provider-url ... --provider-model ... "<prompt>"` executes the agent session
3. Session export is copied out via `docker cp` and converted to SERA JSONL format
4. `git diff` inside the container captures the patch
