# SERA Trajectory Generation Pipeline

## Goal

Generate high-quality supervised fine-tuning (SFT) trajectories for training coding agents. Each trajectory is a multi-turn conversation where an agent navigates a real codebase, reasons about a problem, and produces a code change.

The key insight is **self-verification**: generate the same change twice through different paths, then compare the patches. If two independent attempts converge on the same fix, the trajectory is likely correct — no human labeling needed.

## Target Codebase

The pipeline operates on a real repository checked out inside Docker containers. The agent sees the full repo and can run arbitrary commands. Supported languages: C, C++, and Go (via tree-sitter function extraction). Configuration lives in `configs/repo_config.json`.

## Pipeline Stages

### Stage 1: Rollout 1 — Change Generation

The pipeline iterates over every function in the codebase (shuffled, optionally capped by `--max-samples`). For each function, it tries up to K bug types (default 3), stopping on the first successful generation.

Each attempt picks a bug type and prompts the agent:

> "There is a {bug_type} downstream of function {func_name} in {file_path}:{line}. Investigate and fix it."

Bug types come from two sources (see Bug Prompt Architecture below):
- **Language bugs**: generic to the programming language (e.g. buffer overflows for C, goroutine leaks for Go)
- **Domain bugs**: specific to the application domain (e.g. telecom protocol state machine errors)

The agent (hydron) runs inside a Docker container with full shell access. It reads code, navigates the repo, reasons about the issue, and makes edits. This produces:

- **T1**: The full agent trajectory (every message, tool call, and tool output)
- **P1**: The resulting `git diff`

The bug prompt is deliberately vague — the agent must investigate whether the bug actually exists and decide what to fix. This produces realistic exploration behavior rather than mechanical patch application.

Patches are rejected immediately if they are empty or contain only comment/whitespace changes.

### Stage 2: Synthetic PR Generation

Take the T1 trajectory and P1 patch from stage 1 and ask a teacher model to write a pull request description, as if the change were a real contribution. The PR describes *what* changed and *why*, using few-shot examples from `configs/demo_prs/` for formatting guidance.

This PR becomes the *only* input for stage 3 — it's the information bottleneck that forces the second agent to work independently.

### Stage 3: Rollout 2 — Reproduction from PR

Give a fresh agent (clean container, no memory of stage 1) only the synthetic PR description:

> "Please implement the following pull request: {pr_text}"

The agent must navigate the codebase from scratch, find the relevant files, understand the described change, and implement it. This produces:

- **T2**: Second trajectory
- **P2**: Second patch

### Stage 4: Soft Verification

Compare P1 and P2 using line-level recall:

```
recall = |lines(P2) ∩ lines(P1)| / |lines(P1)|
```

Lines are whitespace-normalized and fuzzy-matched (>= 0.7 similarity via SequenceMatcher) to handle variable naming differences. Classification:

| Recall | Label | Meaning |
|--------|-------|---------|
| >= 0.8 | hard_verified | Patches are essentially the same |
| >= 0.4 | soft_verified | Substantial overlap, likely correct |
| < 0.4 | unverified | Patches diverged significantly |

### Stage 5: Quality Filtering (SERA Paper Criteria)

Raw trajectories are filtered following the SERA paper (Section 5.2). These aren't arbitrary thresholds — they target specific failure modes in SFT training data:

- **Empty/trivial patches**: Rejected (agent didn't produce a real change)
- **Patch size <= 40 lines**: Large patches tend to be unfocused or hallucinated; small targeted fixes train better agents
- **Avg tool output <= 600 tokens**: Trajectories with huge command outputs (e.g. dumping entire files) teach the model to rely on noisy context instead of targeted investigation
- **Duplicate patch deduplication**: Identical patches from different functions add no training signal
- **Truncation ratio >= 0.88**: The trajectory must fit within the training context window (default 32K tokens) without losing more than 12% — heavily truncated trajectories teach incomplete reasoning chains
- **T2 verification score >= 0.5**: For rollout 2 trajectories, the reproduction must substantially match the original (otherwise it's a failed attempt, not training signal)

After filtering, trajectories are ranked by truncation ratio (T1) and verification score + truncation ratio (T2), then the top N are selected for training.

### Stage 6: SFT Formatting

Surviving trajectories are converted into multi-turn conversation format for fine-tuning:

```json
{"conversations": [
  {"role": "system", "content": "You are an autonomous coding agent..."},
  {"role": "user", "content": "There is a buffer overflow..."},
  {"role": "assistant", "content": "Let me investigate...", "tool_calls": [...]},
  {"role": "tool", "content": "...output..."},
  ...
]}
```

The system prompt is repo-agnostic. Repo-specific context (language, working directory, build notes) is part of the user message.

Split into train/held-out sets. Both T1 and T2 trajectories from verified pairs are usable training data.

## Bug Prompt Architecture

Bug prompts are assembled from two independent dimensions:

```
configs/bug_prompts/
  lang_c.json              # 40 generic C/C++ bugs (no subsystems)
  lang_go.json             # 29 generic Go bugs (no subsystems)
  domain_telecom_5g.json   # 25 telecom bugs (canonical OAI5G subsystem paths)

configs/bug_prompts_<repo>.json  # assembled per-repo (language + remapped domain)
```

**Language bugs** are generic to the programming language — buffer overflows, use-after-free, null pointer derefs for C; unchecked errors, goroutine leaks, nil map writes for Go. They have no subsystem restrictions and match all functions.

**Domain bugs** are specific to the application domain — telecom protocol state machines, timer bugs, ASN.1 encoding errors, HARQ issues. They have canonical subsystem paths (from OAI5G) that get remapped to the target repo's actual directory structure by `populate_repo_config.py` via an LLM call.

`repo_config.json` specifies:
- `"language": "c_cpp"` or `"go"` — selects the language bug file
- `"domain": "telecom_5g"` or `""` — selects the domain bug file (empty = no domain bugs)

The assembled file is the single source of truth at runtime. Adding a new language or domain doesn't require modifying the other dimension.

## Infrastructure

- **Agent runtime**: hydron binary running inside Docker containers via `docker exec`, with `--skip-auth` and provider config passed as CLI flags
- **LLM backend**: OpenAI-compatible endpoint (LiteLLM proxy -> model provider). Default model: Qwen3 Coder 480B (A35B MoE)
- **Container pooling**: Workers reuse containers across samples (reset via `git checkout . && git clean -fd` between runs)
- **Parallelism**: Configurable worker count (`--workers`), each worker gets its own container from a pool
- **Resume**: `--resume` flag skips functions that already have successful T1 metadata in the output directory
- **Max steps**: `--max-steps` caps agent turns per session to control cost and trajectory length

## Artifacts Per Sample

```
{run_id}_t1_trajectory.jsonl   — Rollout 1 trajectory
{run_id}_p1.diff               — Rollout 1 patch
{run_id}_t1_meta.json          — Rollout 1 metadata
{run_id}_synth_pr.md           — Synthetic PR description
{run_id}_t2_trajectory.jsonl   — Rollout 2 trajectory
{run_id}_p2.diff               — Rollout 2 patch
{run_id}_t2_meta.json          — Rollout 2 metadata
{run_id}_verification.json     — Soft verification result
```

## Why This Works

1. **No human labels**: Verification comes from convergence of two independent attempts, not manual review.
2. **Realistic trajectories**: The agent explores, makes mistakes, backtracks — all behaviors we want the student model to learn.
3. **Exhaustive coverage**: Every function in the codebase is attempted (with multiple bug types as fallback), not randomly sampled.
4. **Quality signal**: The verification score provides a continuous quality measure, and the SERA-based filters remove known failure modes for SFT data.
