# SERA — Soft-Verified Efficient Repository Agents

## What Is This?

SERA is an end-to-end pipeline for generating high-quality SFT training data from real Git repositories, then fine-tuning an LLM to autonomously fix bugs in that codebase. The pipeline supports C, C++, and Go codebases, and currently targets telecom repositories (srsRAN Project, OpenAirInterface 5G).

The pipeline has 3 phases:
1. **Dataset generation** — extract functions, generate fix trajectories with hydron, soft-verify via patch agreement
2. **Training** — fine-tune on the verified trajectories
3. **Inference** — run the fine-tuned model with a lightweight agent harness (`sera-agent/`)

---

## Project Structure

```
repo-agents/
├── ONBOARDING.md                  ← you are here
├── TRAJECTORY_GENERATION.md       ← quick-start for trajectory generation
├── pipeline.md                    ← detailed pipeline design and rationale
│
├── scripts/                       ← dataset generation pipeline
│   ├── generate_data.py           # Full 4-stage pipeline orchestrator
│   ├── rollout1.py                # Stage 1: change generation (hydron in Docker)
│   ├── generate_pr.py             # Stage 2: synthetic PR from trajectory
│   ├── rollout2.py                # Stage 3: reproduction from PR
│   ├── soft_verify.py             # Stage 4: line-level patch recall
│   ├── filter_data.py             # Stage 5: quality filtering (SERA criteria)
│   ├── format_for_training.py     # Stage 6: SFT conversation formatting
│   ├── hydron_runner.py           # Hydron subprocess wrapper for Docker
│   ├── trajectory_converter.py    # Hydron export → SERA JSONL format
│   ├── extract_functions_generic.py # C/C++/Go function extraction (tree-sitter)
│   ├── populate_repo_config.py    # Generate repo_config.json for new repos
│   ├── ping_model.py              # Health-check for LLM endpoint
│   └── convert_sft_for_megatron.py # Convert SFT → Megatron-Bridge format
│
├── sera-agent/                    ← inference harness (post-training)
│   ├── sera_agent.py              # Agent loop + CLI
│   ├── tools/
│   │   ├── parser.py              # Tool call XML parser
│   │   └── editor.py              # str_replace_editor (5 commands)
│   └── tests/
│       └── test_harness.py        # Parser + editor test suite
│
├── configs/
│   ├── repo_config.json           # Target repo settings (language, domain, Docker, paths)
│   ├── bug_prompts/               # Source bug prompt files
│   │   ├── lang_c.json            # 40 generic C/C++ bugs
│   │   ├── lang_go.json           # 29 generic Go bugs
│   │   └── domain_telecom_5g.json # 25 telecom domain bugs (canonical subsystems)
│   ├── bug_prompts_srsran.json    # Assembled srsRAN bug prompts (language + domain)
│   ├── bug_prompt_template.txt    # Prompt template for rollout1
│   ├── commits.json               # Commit snapshots for Docker images
│   └── demo_prs/                  # Example PRs for few-shot PR generation
│
├── docker/
│   ├── Dockerfile.sera            # Generic Dockerfile for target repos
│   └── Dockerfile.generic         # Alternative Dockerfile
│
├── data/
│   ├── raw/                       # Raw pipeline outputs (trajectories, patches, PRs)
│   ├── sft_dataset/               # Filtered + formatted SFT data
│   └── *_functions.jsonl          # Extracted functions per repo
│
├── training/                      ← training scripts
│   └── train_sera.py              # Training configuration
│
└── hydron                         ← hydron binary (not checked in)
```

---

## Phase 1: Dataset Generation

### Overview

See [pipeline.md](pipeline.md) for the full pipeline design. In short:

1. Extract functions from target repo (C/C++/Go via tree-sitter)
2. For each function, prompt an agent to fix a bug → produces trajectory T1 + patch P1
3. Generate a synthetic PR description from T1
4. Prompt a fresh agent to implement the PR → produces T2 + P2
5. Compare P1 vs P2 — if they agree, the trajectory is verified
6. Filter by quality criteria and format for SFT training

### Bug Prompt Architecture

Bug prompts are assembled from two dimensions:

- **Language** (`lang_c.json`, `lang_go.json`): language-specific issues like buffer overflows (C) or goroutine leaks (Go). Match all functions.
- **Domain** (`domain_telecom_5g.json`): domain-specific issues like protocol state machine errors. Subsystems are remapped per-repo.

`repo_config.json` specifies `"language"` and `"domain"` (default: `telecom_5g`). `populate_repo_config.py` assembles the final `bug_prompts_<repo>.json`.

### Prerequisites

- Docker running
- `hydron` binary matching container architecture (Linux ARM64 or x64)
- LLM endpoint (LiteLLM proxy or direct provider)
- `uv` for Python dependency management

### Quick Start

```bash
# 1. Extract functions
uv run python scripts/extract_functions_generic.py \
  --repo-root srsRAN_Project --output data/srsran_functions.jsonl

# 2. Build Docker images
for sha in 16d308d a71d6fe 6b48ad7 cb148b7 4bf1543; do
  docker build -t "srsran-sera:${sha}" \
    --build-arg REPO_DIR=srsRAN_Project \
    --build-arg REPO_COMMIT="${sha}" \
    -f docker/Dockerfile.sera .
done
docker tag srsran-sera:4bf1543 srsran-sera:latest

# 3. Run pipeline
uv run python scripts/generate_data.py \
  --functions data/srsran_functions.jsonl \
  --bug-prompts configs/bug_prompts_srsran.json \
  --template configs/bug_prompt_template.txt \
  --commits configs/commits.json \
  --demo-prs-dir configs/demo_prs \
  --output-dir data/raw \
  --max-steps 50 --workers 4 --resume

# 4. Filter + format
uv run python scripts/filter_data.py --input-dir data/raw --output-dir data/filtered
uv run python scripts/format_for_training.py --input-dir data/raw --output-dir data/sft
```

---

## Phase 2: Training

The SFT dataset can be used with any training framework. The repo includes conversion for Megatron-Bridge:

```bash
uv run python scripts/convert_sft_for_megatron.py
```

See the training config in `training/train_sera.py` for details.

---

## Phase 3: Inference with sera-agent

```bash
cd sera-agent
python3 sera_agent.py \
    --model-url http://localhost:8000/v1 \
    --model-name <your-model> \
    --repo /path/to/repo \
    --issue "Fix the memory leak in remove_job() in job.c" \
    --output trajectory.json
```

The agent loop: prompt → LLM generates tool calls → execute tools → append results → repeat until submit.

### Running Tests

```bash
cd sera-agent
python3 -m tests.test_harness
```

---

## Adding a New Repo

1. Clone the repo
2. Run `populate_repo_config.py` to generate config + bug prompts:
   ```bash
   uv run python scripts/populate_repo_config.py \
     --repo-path /path/to/new_repo \
     --domain telecom_5g
   ```
3. Extract functions: `uv run python scripts/extract_functions_generic.py --repo-root ...`
4. Build Docker images with `docker/Dockerfile.sera`
5. Run the pipeline with the generated config files
