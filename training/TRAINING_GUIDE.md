# SERA Training Guide — Nemotron-3-Nano-30B-A3B with Megatron-Bridge

## Overview

This guide covers fine-tuning **NVIDIA Nemotron-3-Nano-30B-A3B** (hybrid Mamba-2 + Attention + MoE, 32.88B total params, ~3B active) on the SERA OAI5G SFT dataset using **Megatron-Bridge**.

Two training modes are supported:
- **LoRA** (recommended to start) — trains adapter layers only, 1 node / 8 GPUs
- **Full SFT** — trains all parameters, 2 nodes / 16 GPUs recommended

---

## Prerequisites

### Hardware
| Mode | GPUs | VRAM per GPU | Nodes |
|------|------|-------------|-------|
| LoRA | 8× H100 or A100 80GB | 80GB | 1 |
| Full SFT | 16× H100 or A100 80GB | 80GB | 2 |

The model has 128 MoE experts. Even though only 6 are active per token (~3B active params), all 128 experts (~32.88B params) must be loaded.

### Software
- Python 3.10+
- PyTorch >= 2.6.0
- Megatron-Bridge (clone from NVIDIA, install with `uv sync` or `pip install -e .`)
- CUDA 12.x + NCCL
- Transformer Engine, mamba-ssm, causal-conv1d, flash-linear-attention (installed by Megatron-Bridge)

### Model Weights
Download the pretrained checkpoint:
```bash
# From Hugging Face
huggingface-cli download nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 \
    --local-dir /workspace/models/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16
```

---

## Cluster Setup

```bash
# 1. Clone this repo
git clone https://github.com/h2loop/repo-agents.git
cd repo-agents

# 2. Clone Megatron-Bridge (if not already on cluster)
git clone https://github.com/NVIDIA/Megatron-Bridge.git /workspace/Megatron-Bridge
cd /workspace/Megatron-Bridge
uv sync  # or: pip install -e .

# 3. Verify dataset is in place
ls data/megatron_sft/
# training.jsonl (821 samples, 78MB)
# validation.jsonl (92 samples, 8.3MB)
# tool_schemas.json (3 tool schemas)
```

---

## Training

### Option A: LoRA (Recommended First)

**Single-node, 8 GPUs:**
```bash
cd /workspace/Megatron-Bridge

torchrun --nproc_per_node=8 \
    /workspace/repo-agents/training/train_sera.py \
    --peft lora \
    --seq-length 4096 \
    --data-dir /workspace/repo-agents/data/megatron_sft \
    --config-file /workspace/repo-agents/training/sera_overrides.yaml \
    checkpoint.pretrained_checkpoint=/workspace/models/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 \
    checkpoint.save=/workspace/results/sera_lora
```

**With SLURM:**
```bash
cd /workspace/repo-agents
sbatch training/slurm_sera_lora.sh
```

**LoRA config** (from recipe, targeting Mamba + Attention + MoE layers):
- Target modules: `linear_qkv`, `linear_proj`, `linear_fc1`, `linear_fc2`, `in_proj`, `out_proj`
- Rank: 32, Alpha: 32
- LR: 1e-4 (cosine decay)

### Option B: Full SFT

**Two nodes, 16 GPUs:**
```bash
cd /workspace/repo-agents
sbatch training/slurm_sera_sft.sh
```

Key differences from LoRA:
- LR: 5e-6 (10× lower)
- TP=2, EP=8, SP=True (needs more parallelism)
- All parameters updated

---

## The Patched Chat Template (Critical)

**Problem**: Nemotron's original chat template lacks `{% generation %}`/`{% endgeneration %}` markers. Megatron-Bridge uses these to build the `loss_mask` tensor. Without them, loss is computed on **100% of tokens** (system, user, tool outputs) instead of only assistant tokens.

**Solution**: `configs/nemotron_chat_template_patched.jinja` adds markers around all 4 assistant output paths in the template. The training script (`train_sera.py`) automatically loads this template and passes it via `dataset_kwargs["chat_template"]`.

**Impact**: Loss computed on **18.9%** of tokens (assistant only) instead of 100%. Verified across all 821 training samples.

The 4 patch points in the Jinja template:
```
Line 122: assistant with tool_calls — opening {% generation %}
Line 158: assistant with tool_calls — closing {% endgeneration %}
Line 162: assistant without tools (not truncated)
Line 170: assistant truncated with content
Line 172: assistant truncated empty
```

---

## Dataset Format

Each sample in `training.jsonl` is a multi-turn conversation:

```json
{
  "messages": [
    {"role": "system", "content": "You are an expert C/C++ engineer..."},
    {"role": "user", "content": "<uploaded_files>/repo</uploaded_files>\nI've uploaded..."},
    {"role": "assistant", "content": "<think>...</think>", "tool_calls": [
      {"function": {"name": "bash", "arguments": {"command": "find /repo -name 'job.c'"}}}
    ]},
    {"role": "tool", "content": "/repo/openair2/LAYER2/RLC/job.c"},
    ...
    {"role": "assistant", "content": "", "tool_calls": [
      {"function": {"name": "submit", "arguments": {}}}
    ]}
  ],
  "tools": [
    {"type": "function", "function": {"name": "bash", ...}},
    {"type": "function", "function": {"name": "str_replace_editor", ...}},
    {"type": "function", "function": {"name": "submit", ...}}
  ]
}
```

Key points:
- `tool_calls.arguments` is a **parsed dict** (not JSON string) — required because Nemotron's Jinja template iterates `tool_call.arguments|items`
- Consecutive `role="tool"` messages are merged (template wraps them in a single `<|im_start|>user` block)
- 3 tools: `bash` (52.1%), `str_replace_editor` (41.9%), `submit` (5.9%)
- Per-sample tool schemas in `"tools"` field

### What the Model Sees During Training

A single flat token sequence with a binary loss mask:
```
[MASKED]  <|im_start|>system\n...system prompt + tool schemas...<|im_end|>
[MASKED]  <|im_start|>user\n...issue description...<|im_end|>
[LOSS=1]  <|im_start|>assistant\n<think>...</think>\n<tool_call>...<|im_end|>
[MASKED]  <|im_start|>user\n<tool_response>...output...<|im_end|>
[LOSS=1]  <|im_start|>assistant\n<think>...</think>\n<tool_call>...<|im_end|>
...
[LOSS=1]  <|im_start|>assistant\n<tool_call><function=submit>...</tool_call><|im_end|>
```

Gradient flows only through `LOSS=1` positions (assistant turns).

---

## Key Configuration Parameters

### Parallelism (MoE-specific)

| Parameter | Default | Notes |
|-----------|---------|-------|
| `tensor_model_parallel_size` | 1 (LoRA), 2 (SFT) | Splits attention/MLP across GPUs |
| `pipeline_model_parallel_size` | 1 | Pipeline stages |
| `expert_model_parallel_size` | 8 | **Must be 8** — distributes 128 experts across 8 GPUs |
| `sequence_parallel` | False (LoRA), True (SFT) | Sequence-dim parallelism |
| `context_parallel_size` | 1 | Ring attention for very long sequences |

`expert_model_parallel_size=8` means each GPU holds 16 experts (128/8). This is why you need at least 8 GPUs.

### Training

| Parameter | LoRA | Full SFT |
|-----------|------|----------|
| `train_iters` | 500 | 500 |
| `global_batch_size` | 128 | 128 |
| `micro_batch_size` | 1 | 1 |
| `optimizer.lr` | 1e-4 | 5e-6 |
| `seq_length` | 4096 | 4096 |

### LoRA

| Parameter | Value |
|-----------|-------|
| `target_modules` | linear_qkv, linear_proj, linear_fc1, linear_fc2, in_proj, out_proj |
| `dim` (rank) | 32 |
| `alpha` | 32 |
| `dropout` | 0.0 |

The target modules cover both Mamba-2 layers (`in_proj`, `out_proj`) and Attention+MoE layers (`linear_qkv`, `linear_proj`, `linear_fc1`, `linear_fc2`).

---

## Monitoring

Training logs to TensorBoard by default:
```bash
tensorboard --logdir /workspace/results/sera_lora/tb_logs
```

If WandB is configured:
```bash
export WANDB_API_KEY="your_key"
# Override in YAML or CLI: logger.wandb_project=sera-nemotron-sft
```

### What to Watch
- **Loss curve**: Should decrease steadily. Expect initial loss around 2-3 for LoRA.
- **Eval loss**: Check every `eval_interval` steps. Stop if eval loss starts increasing (overfitting).
- **Gradient norms**: Recipe enables `check_for_nan_in_grad=True`.

---

## After Training — Inference with the SERA Agent Harness

The `sera-agent/` directory contains a lightweight, zero-framework agent harness
purpose-built for the fine-tuned model. It implements the same agentic loop the
model was trained on: **generate → parse tool calls → execute → append result → repeat**.

### Step 1: Export / Merge LoRA Weights

For LoRA, merge adapter weights back into the base model to get a standalone checkpoint:

```bash
# Megatron-Bridge provides checkpoint conversion utilities.
# The exact command depends on version — check Megatron-Bridge docs.
# The goal is a single merged HF-format checkpoint directory:
#   /workspace/results/sera_merged/
#     ├── config.json
#     ├── model-00001-of-00004.safetensors
#     ├── ...
#     ├── tokenizer.json
#     └── tokenizer_config.json
```

For full SFT, the checkpoint is already a complete model — just convert from
Megatron distributed format to HF format if needed.

### Step 2: Serve with vLLM

```bash
# Single node, 4-way tensor parallelism (fits on 4× A100/H100 80GB)
vllm serve /workspace/results/sera_merged \
    --port 8000 \
    --tensor-parallel-size 4 \
    --max-model-len 8192 \
    --trust-remote-code

# Verify the server is up
curl http://localhost:8000/v1/models
```

vLLM exposes an OpenAI-compatible `/v1/chat/completions` endpoint. The SERA
agent harness talks to this endpoint — no Megatron-Bridge needed at inference time.

### Step 3: Run the SERA Agent

```bash
cd /workspace/repo-agents/sera-agent

# Basic usage — give it a repo and an issue description
python3 sera_agent.py \
    --model-url http://localhost:8000/v1 \
    --model-name nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 \
    --repo /path/to/openairinterface5g \
    --issue "Fix the memory leak in remove_job() in job.c" \
    --output trajectory.json

# Read issue from a file (for longer descriptions)
python3 sera_agent.py \
    --model-url http://localhost:8000/v1 \
    --model-name nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 \
    --repo /path/to/openairinterface5g \
    --issue-file bug_description.txt \
    --max-steps 30 \
    --output trajectory.json
```

**CLI arguments:**

| Flag | Default | Description |
|------|---------|-------------|
| `--model-url` | `http://localhost:8000/v1` | vLLM server URL |
| `--model-name` | required | Model name as registered in vLLM |
| `--repo` | required | Path to the target repository (agent runs bash/editor here) |
| `--issue` | — | Issue description as a string |
| `--issue-file` | — | Path to a file containing the issue description |
| `--max-steps` | `50` | Max agentic loop iterations before forced stop |
| `--output` | — | Save full trajectory (all messages) to JSON |
| `--temperature` | `0.0` | Sampling temperature |
| `--max-tokens` | `4096` | Max tokens per generation |

### How the Agent Loop Works

```
1. Format system prompt + issue into messages
2. Send messages + tool schemas to vLLM
3. Model responds with <tool_call> XML blocks
4. Parser extracts structured ToolCall objects
5. Executor dispatches each tool call:
   - bash → subprocess.run(command, cwd=repo, timeout=120)
   - str_replace_editor → view/edit/create/insert/undo_edit
   - submit → capture `git diff` as final patch, stop loop
6. Tool output appended as tool response message
7. Go to step 2 (until submit or max_steps)
```

The model outputs Nemotron-native XML tool calls:
```xml
<tool_call>
<function=bash>
<parameter=command>
find /repo -name "job.c" -type f
</parameter>
</function>
</tool_call>
```

The parser (`sera-agent/tools/parser.py`) handles edge cases like `<tool_call>`
appearing inside echo commands or `</parameter>` in file content — it only splits
on tags at line boundaries (validated against 27,187 tool calls, zero errors).

### The 3 Tools

| Tool | Training Distribution | What It Does |
|------|----------------------|--------------|
| `bash` | 52.1% (14,106 calls) | Execute shell commands — `find`, `grep`, `cat`, `make`, `gcc`, etc. |
| `str_replace_editor` | 41.9% (11,466 calls) | 5 commands: `view` (cat -n), `str_replace` (find & replace), `create`, `insert`, `undo_edit` |
| `submit` | 5.9% (1,615 calls) | Runs `git diff` to capture the final patch, then stops the loop |

### Output

With `--output trajectory.json`, the agent saves the full conversation:
```json
{
  "issue": "Fix the memory leak...",
  "repo": "/path/to/oai5g",
  "steps": 12,
  "patch": "diff --git a/...",
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "<think>...</think>\n<tool_call>..."},
    {"role": "tool", "content": "find output..."},
    ...
  ]
}
```

Apply the generated patch:
```bash
cd /path/to/openairinterface5g
git apply /path/to/patch.diff
```

### Running Tests

```bash
cd /workspace/repo-agents/sera-agent
python3 -m tests.test_harness
```

Tests cover parser edge cases (XML in values, multi-line params), editor
operations, and round-trip validation against real training samples.

---

## Files Reference

| File | Purpose |
|------|---------|
| `training/train_sera.py` | Main training script — loads recipe, wires dataset + template |
| `training/sera_overrides.yaml` | YAML config overrides (iters, LR, parallelism, checkpoint paths) |
| `training/slurm_sera_lora.sh` | SLURM job script for LoRA (1 node, 8 GPU) |
| `training/slurm_sera_sft.sh` | SLURM job script for full SFT (2 nodes, 16 GPU) |
| `configs/nemotron_chat_template_patched.jinja` | Patched template with `{% generation %}` markers |
| `data/megatron_sft/training.jsonl` | 821 training samples |
| `data/megatron_sft/validation.jsonl` | 92 validation samples |
| `data/megatron_sft/tool_schemas.json` | Tool schemas (bash, str_replace_editor, submit) |
| `sera-agent/sera_agent.py` | Inference harness — agent loop, LLM client, tool executor |
| `sera-agent/tools/parser.py` | Nemotron `<tool_call>` XML parser |
| `sera-agent/tools/editor.py` | str_replace_editor (view, str_replace, create, insert, undo_edit) |
| `sera-agent/tests/test_harness.py` | Parser + editor test suite (20 tests) |

---

## Troubleshooting

**OOM on 8 GPUs with full SFT**: Use LoRA, or increase `tensor_model_parallel_size` to 2 (requires 16 GPUs minimum with EP=8).

**DeePEP errors**: If your cluster doesn't have DeePEP installed, disable it in `sera_overrides.yaml`:
```yaml
model:
  moe_token_dispatcher_type: alltoall
  moe_flex_dispatcher_backend: null
  moe_shared_expert_overlap: true
```

**Sequence too long**: Default max is 4096. If samples are truncated, increase `seq_length` (up to 8192). Watch memory.

**Loss not decreasing**: Verify the patched template is loaded — check logs for "generation" markers. If loss starts high (~10+) and stays flat, the template may not be applied correctly.
