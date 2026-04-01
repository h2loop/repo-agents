# SERA — Soft-Verified Efficient Repository Agents

## What Is This?

SERA is an end-to-end pipeline for generating high-quality SFT training data from real Git repositories, then fine-tuning an LLM to autonomously fix bugs in that codebase. The current target is **OpenAirInterface 5G** (OAI5G) — a large C/C++ RAN implementation — and the base model is **NVIDIA Nemotron-3-Nano-30B-A3B** (hybrid Mamba-2 + Attention + MoE, 32.88B params, 128 experts with top-6 routing).

The pipeline has 3 phases:
1. **Dataset generation** — mine real bugs from Git history, generate fix trajectories with SWE-agent, soft-verify via patch agreement
2. **Training** — fine-tune Nemotron with Megatron-Bridge on the verified trajectories
3. **Inference** — run the fine-tuned model with a lightweight agent harness (`sera-agent/`)

---

## Project Structure

```
sera/
├── ONBOARDING.md                  ← you are here
├── sera-agent/                    ← inference harness (post-training)
│   ├── sera_agent.py              # Agent loop + CLI
│   ├── tools/
│   │   ├── parser.py              # Nemotron <tool_call> XML parser
│   │   └── editor.py              # str_replace_editor (5 commands)
│   ├── tests/
│   │   └── test_harness.py        # Parser + editor test suite
│   └── CHANGES.md                 # Detailed design decisions
│
├── scripts/                       ← dataset generation pipeline
│   ├── run_sera_pipeline.sh       # Full 6-step pipeline runner
│   ├── create_instances.py        # Step 1: generate SWE-agent instances from functions + bugs
│   ├── scrape_stage_one.py        # Step 3: extract synthetic PRs from stage 1 output
│   ├── verify_patches.py          # Step 5: soft-verify P1 vs P2 patch agreement
│   ├── postprocess_sweagent.py    # Step 6: filter + format into SFT dataset
│   ├── convert_sft_for_megatron.py # Convert SFT → Megatron-Bridge native format
│   ├── extract_functions.py       # Extract C/C++ functions from OAI5G repo
│   ├── generate_data.py           # Standalone data generation (non-SWE-agent path)
│   ├── generate_pr.py             # Generate synthetic PR descriptions
│   ├── filter_data.py             # Filter dataset by quality criteria
│   ├── format_for_training.py     # Format raw rollouts into SFT conversations
│   ├── soft_verify.py             # Soft verification scoring
│   ├── rollout1.py / rollout2.py  # Manual rollout scripts (debugging)
│   └── ping_model.py              # Health-check for LLM endpoint
│
├── configs/
│   ├── nemotron_chat_template_patched.jinja  # CRITICAL: patched template with {% generation %} markers
│   ├── bug_prompts.json           # Bug injection prompt templates
│   ├── commits.json               # Selected OAI5G commit SHAs
│   ├── sweagent/                  # SWE-agent stage 1 & 2 configs
│   └── pipeline/                  # Pipeline orchestration config
│
├── data/
│   ├── sft_dataset/               # Final SFT dataset (SERA format)
│   │   ├── oai5g_train.jsonl      # 378 training samples (SERA format)
│   │   ├── oai5g_held_out.jsonl   # 42 held-out samples
│   │   └── dataset_stats.json     # Stats: token/turn distributions
│   ├── megatron_sft/              # Converted for Megatron-Bridge
│   │   ├── training.jsonl         # 821 samples, 78MB
│   │   ├── validation.jsonl       # 92 samples, 8.3MB
│   │   └── tool_schemas.json      # 3 tool schemas
│   └── raw/                       # Raw SWE-agent outputs (rollouts, diffs, PRs)
│
├── SERA/                          # Upstream SERA framework (reference)
├── docker/                        # Dockerfile.sera + build scripts
├── openairinterface5g/            # OAI5G repo clone (target codebase)
└── repos/                         # Additional repo clones for generic pipeline
```

---

## Phase 1: Dataset Generation

### Overview

SERA generates training data by:
1. Mining real bug-fix commits from Git history
2. Injecting the bug back into the codebase (reverse the fix)
3. Running an LLM agent (via SWE-agent) to re-discover and fix the bug
4. Doing this **twice** with different prompts (T1: commit-based, T2: synthetic PR)
5. Soft-verifying that both patches agree → high confidence the fix is correct

### The 6-Step Pipeline

Run with: `bash scripts/run_sera_pipeline.sh`

| Step | Script | What It Does |
|------|--------|--------------|
| 1 | `create_instances.py` | Combines extracted functions + bug prompts + commit SHAs → SWE-agent instance YAML |
| 2 | SWE-agent `run-batch` | Stage 1 rollouts: agent explores repo, finds bug, produces patch (P1) + self-eval + synthetic PR |
| 3 | `scrape_stage_one.py` | Extracts synthetic PR descriptions from stage 1 output → stage 2 instances |
| 4 | SWE-agent `run-batch` | Stage 2 rollouts: agent uses synthetic PR as the bug description, produces patch (P2) |
| 5 | `verify_patches.py` | Compares P1 vs P2 — if both patches touch the same code region with equivalent changes, the sample is "soft verified" |
| 6 | `postprocess_sweagent.py` | Filters verified samples, formats into SFT conversations with tool calls |

### Prerequisites

- Python 3.10+ with `sweagent` installed (`pip install sweagent`)
- Docker (SWE-agent runs each rollout in a container)
- An LLM endpoint (the pipeline used GPT-4/Claude via LiteLLM — see `configs/litellm_model_registry.json`)
- The target repo cloned at `openairinterface5g/`

### Dataset Format (SERA → Megatron)

The raw SFT dataset (`data/sft_dataset/`) uses SERA's format:
```json
{"conversations": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "...", "tool_calls": [...]}, {"role": "tool", "content": "..."}, ...]}
```

For Megatron-Bridge training, convert with:
```bash
python3 scripts/convert_sft_for_megatron.py
```

This produces `data/megatron_sft/training.jsonl` (821 samples) with key transformations:
- `conversations` → `messages` (Megatron-Bridge native key)
- `tool_calls.arguments` stored as parsed dict (not JSON string) — required because Nemotron's Jinja template iterates `tool_call.arguments|items`
- Consecutive `role="tool"` messages merged (Nemotron template wraps them in a single `<|im_start|>user` block)
- Tool schemas included per-sample in `"tools"` field

### Current Dataset Stats

| Metric | Value |
|--------|-------|
| Training samples | 821 |
| Validation samples | 92 |
| Rollout types | T1: ~600, T2: ~220 |
| Tool call distribution | bash: 14,106 / str_replace_editor: 11,466 / submit: 1,615 |
| Token range | 1,686 – 28,533 tokens per sample |
| Mean turns per sample | 75.2 |

---

## Phase 2: Training with Megatron-Bridge

### The Patched Chat Template (Critical)

**Problem**: Nemotron-3-Nano's original chat template lacks `{% generation %}`/`{% endgeneration %}` markers. Megatron-Bridge's `_chat_preprocess()` uses these markers to build the loss mask. Without them, loss is computed on **all** tokens (system prompt, user messages, tool outputs) — 100% instead of the correct ~19%.

**Solution**: `configs/nemotron_chat_template_patched.jinja` adds `{% generation %}` markers around all 4 assistant output paths:
- Assistant with tool calls (opening + closing)
- Assistant without tool calls (not truncated)
- Assistant truncated with content
- Assistant truncated empty

**Impact**: Loss computed on 18.9% of tokens (5,184,504 assistant tokens out of 27,386,561 total). Verified across all 821 training samples.

### Training Setup

**Model**: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16`

**Framework**: [Megatron-Bridge](https://github.com/NVIDIA/Megatron-Bridge) (NVIDIA's NeMo-based training framework)

**Data config** — point to the converted dataset and patched template:
```python
# In your Megatron-Bridge training config:
cfg.data.train_ds.file_path = "data/megatron_sft/training.jsonl"
cfg.data.validation_ds.file_path = "data/megatron_sft/validation.jsonl"

# CRITICAL: override chat template for correct loss masking
with open("configs/nemotron_chat_template_patched.jinja") as f:
    cfg.tokenizer.chat_template = f.read()
```

**Hardware requirements**:
- Minimum: 8× A100 80GB or 8× H100 80GB
- The model is 32.88B total params but only ~3B active (MoE with 128 experts, top-6 routing)
- All experts must be loaded even though only 6 are active per token

**Key Megatron-Bridge components**:
- `GPTSFTChatDataset` — processes `messages` + `tools` via `apply_chat_template()`
- `_chat_preprocess()` in `datasets/utils.py` — builds `loss_mask` using `GENERATION_REGEX` to find `{% generation %}` markers
- `return_assistant_tokens_mask=True` — HuggingFace tokenizer flag that uses `{% generation %}` to mask non-assistant tokens
- Recipe: `megatron.bridge.recipes.nemotronh.nemotron_3_nano` — contains PEFT/LoRA config templates

### What the Model Sees During Training

A single flat token sequence with a binary loss mask:

```
[MASKED] <|im_start|>system\nYou are an expert C/C++ engineer...<|im_end|>
[MASKED] <|im_start|>user\n<uploaded_files>/repo</uploaded_files>...<|im_end|>
[LOSS=1] <|im_start|>assistant\n<think>Let me find the file...</think>\n<tool_call>...<|im_end|>
[MASKED] <|im_start|>user\n<tool_response>output of command...</tool_response><|im_end|>
[LOSS=1] <|im_start|>assistant\n<think>I see the bug...</think>\n<tool_call>...<|im_end|>
...
[LOSS=1] <|im_start|>assistant\n<tool_call><function=submit></function></tool_call><|im_end|>
```

Gradient only flows through `LOSS=1` positions (assistant turns). The model learns to generate tool calls and reasoning while seeing the full context.

---

## Phase 3: Inference with sera-agent

### Architecture

```
User issue → system + user messages
         ↓
    ┌─→ LLM.generate(messages, tools)
    │        ↓
    │   parse_tool_calls(output) → [ToolCall, ...]
    │        ↓
    │   executor.execute(call) → output string
    │        ↓
    │   messages.append(tool response)
    │        ↓
    └── if call.name == "submit": stop, else: loop
```

**4 files, ~540 lines, zero framework dependencies** beyond `requests`.

### The 3 Tools

| Tool | Description | Training Distribution |
|------|-------------|----------------------|
| `bash` | Execute shell commands (subprocess with timeout + truncation) | 52.1% (14,106 calls) |
| `str_replace_editor` | View/edit/create files (5 commands: view, str_replace, create, insert, undo_edit) | 41.9% (11,466 calls) |
| `submit` | Capture `git diff` as final patch and stop | 5.9% (1,615 calls) |

### Running the Agent

```bash
# 1. Start vLLM with your fine-tuned model
vllm serve ./merged_checkpoint \
    --port 8000 \
    --tensor-parallel-size 4

# 2. Run the agent
cd sera/sera-agent
python3 sera_agent.py \
    --model-url http://localhost:8000/v1 \
    --model-name nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 \
    --repo /path/to/oai5g/repo \
    --issue "Fix the memory leak in remove_job() in job.c" \
    --output trajectory.json

# Or read issue from file
python3 sera_agent.py \
    --repo /path/to/repo \
    --issue-file bug_description.txt \
    --max-steps 30 \
    --output trajectory.json
```

### Tool Call Format

The fine-tuned model outputs Nemotron-native XML:
```xml
<tool_call>
<function=bash>
<parameter=command>
find /repo -name "job.c" -type f
</parameter>
</function>
</tool_call>
```

The parser handles edge cases like `<tool_call>` or `</parameter>` appearing inside parameter values (e.g., in `echo` commands) by only splitting on tags at line boundaries.

### Running Tests

```bash
cd sera/sera-agent
python3 -m tests.test_harness
```

Tests cover: parser unit tests (6 edge cases), editor integration (8 operations), parser on 1 real sample, parser on 50 samples (1,680+ tool calls).

---

## Quick Start Checklist

1. **Clone & setup**:
   ```bash
   cd sera
   python3 -m venv .venv && source .venv/bin/activate
   pip install requests transformers  # for sera-agent + validation
   ```

2. **Verify the dataset** (optional):
   ```bash
   cd sera-agent && python3 -m tests.test_harness
   ```

3. **Convert data for training** (if not already done):
   ```bash
   python3 scripts/convert_sft_for_megatron.py
   # Produces data/megatron_sft/training.jsonl + validation.jsonl
   ```

4. **Train with Megatron-Bridge** on your GPU cluster:
   - Use `configs/nemotron_chat_template_patched.jinja` as the chat template override
   - Point data config to `data/megatron_sft/training.jsonl`
   - Use the Nemotron-3-Nano recipe from Megatron-Bridge

5. **Run inference** with the fine-tuned model:
   ```bash
   vllm serve ./merged_checkpoint --port 8000
   cd sera-agent
   python3 sera_agent.py --repo /path/to/repo --issue "..." --output traj.json
   ```

---

## Key Files to Read First

| File | Why |
|------|-----|
| `sera-agent/CHANGES.md` | Detailed design decisions, edge cases, validation results |
| `scripts/run_sera_pipeline.sh` | The full dataset generation pipeline in one script |
| `configs/nemotron_chat_template_patched.jinja` | The patched template — understand the 4 `{% generation %}` insertion points |
| `scripts/convert_sft_for_megatron.py` | How SERA format maps to Megatron-Bridge format |
| `sera-agent/sera_agent.py` | The complete agent loop in one file |
| `sera-agent/tools/parser.py` | How Nemotron XML tool calls are parsed |
| `data/sft_dataset/dataset_stats.json` | Dataset size and distribution |
