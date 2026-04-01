# SERA SVG Pipeline — Working Mechanism

## Full Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PHASE 1: FUNCTION EXTRACTION                      │
│                                                                      │
│  openairinterface5g/ ──→ tree-sitter C/C++ parser                   │
│                              │                                       │
│                              ▼                                       │
│                    oai5g_functions.jsonl                              │
│                    (10,056 functions with name,                       │
│                     file, line, subsystem tag)                        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                    PHASE 2: BUG TAXONOMY                             │
│                                                                      │
│  65 bug types ──→ bug_prompts.json                                  │
│  (40 generic C/C++ + 25 telecom-specific)                           │
│                                                                      │
│  Template: "There is a {bug} downstream of {func} in {subsystem}"   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                    PHASE 3: DOCKER IMAGES                            │
│                                                                      │
│  5 commit SHAs ──→ 5 Docker images + 1 latest                      │
│  (bf69e25, ca119de, 776ca25, 625b4b0, 9777d23)                     │
│                                                                      │
│  Each image: Ubuntu 22.04 + gcc/cmake + OAI5G source at /repo      │
│              checked out to that specific commit                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│               PHASE 5: GENERATION (per sample)                       │
│                                                                      │
│  generate_data.py orchestrates 8 parallel workers                   │
│  Each worker picks: random function + random bug + random commit    │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  STEP 1: ROLLOUT 1 (rollout1.py)                           │     │
│  │                                                             │     │
│  │  1. Format prompt from template + function + bug            │     │
│  │  2. Start fresh Docker container (docker run -d)            │     │
│  │  3. Send system prompt + task to Qwen Coder 480B            │     │
│  │                                                             │     │
│  │  ┌─── AGENT LOOP (up to 70 steps) ───────────────────┐    │     │
│  │  │                                                     │    │     │
│  │  │  LLM returns response                              │    │     │
│  │  │       │                                             │    │     │
│  │  │       ▼                                             │    │     │
│  │  │  parse_assistant_action()                           │    │     │
│  │  │  Detects tool calls in:                             │    │     │
│  │  │  - ```bash\ncommand\n```                            │    │     │
│  │  │  - <|tool_call_begin|>... (Kimi format)             │    │     │
│  │  │  - "SUBMIT" (done signal)                           │    │     │
│  │  │       │                                             │    │     │
│  │  │       ▼                                             │    │     │
│  │  │  execute_tool_call()                                │    │     │
│  │  │  Runs inside Docker via:                            │    │     │
│  │  │    docker exec <container> bash -c "grep ..."       │    │     │
│  │  │    docker exec <container> bash -c "python3 ..."    │    │     │
│  │  │       │                                             │    │     │
│  │  │       ▼                                             │    │     │
│  │  │  Observation sent back to LLM as next user msg      │    │     │
│  │  │       │                                             │    │     │
│  │  │       └──────── loop until SUBMIT or max steps ──┘  │    │     │
│  │  └─────────────────────────────────────────────────────┘    │     │
│  │                                                             │     │
│  │  4. Extract patch: docker exec ... git diff → P1            │     │
│  │  5. Self-evaluate: ask LLM "is this change relevant?"       │     │
│  │     - Empty patch → REJECT                                  │     │
│  │     - LLM says NO → REJECT (retry with different bug)       │     │
│  │     - LLM says YES → ACCEPT                                │     │
│  │  6. Stop container                                          │     │
│  │                                                             │     │
│  │  OUTPUT: T1 trajectory (.jsonl) + P1 patch (.diff)          │     │
│  └─────────────────────────┬───────────────────────────────────┘     │
│                            │                                          │
│                            ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │  STEP 2: PR GENERATION (generate_pr.py)                     │     │
│  │                                                             │     │
│  │  1. Summarize T1 trajectory (truncate to 6000 chars)        │     │
│  │  2. Pick random demo PR from 12 examples                    │     │
│  │  3. Send to LLM: "Write a PR description for this change"  │     │
│  │                                                             │     │
│  │  OUTPUT: synthetic_pr.md                                    │     │
│  └─────────────────────────┬───────────────────────────────────┘     │
│                            │                                          │
│                            ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │  STEP 3: ROLLOUT 2 (rollout2.py)                            │     │
│  │                                                             │     │
│  │  1. Start NEW fresh container (same commit, clean state)    │     │
│  │  2. Give LLM ONLY the synthetic PR (no bug hint)            │     │
│  │  3. Same agent loop as rollout 1                            │     │
│  │  4. Extract patch → P2                                      │     │
│  │  5. Stop container                                          │     │
│  │                                                             │     │
│  │  OUTPUT: T2 trajectory (.jsonl) + P2 patch (.diff)          │     │
│  └─────────────────────────┬───────────────────────────────────┘     │
│                            │                                          │
│                            ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │  STEP 4: SOFT VERIFICATION (soft_verify.py)                 │     │
│  │                                                             │     │
│  │  P1 added lines: {line_a, line_b, line_c, line_d}          │     │
│  │  P2 added lines: {line_a, line_c, line_x}                  │     │
│  │                                                             │     │
│  │  recall = |P2 ∩ P1| / |P1| = 2/4 = 0.50                   │     │
│  │                                                             │     │
│  │  Classification:                                            │     │
│  │    1.0       → hard_verified                                │     │
│  │    ≥ 0.5     → soft_verified                                │     │
│  │    0 < r < 0.5 → weakly_verified                           │     │
│  │    0         → unverified                                   │     │
│  │                                                             │     │
│  │  OUTPUT: verification.json (score + classification)         │     │
│  └─────────────────────────────────────────────────────────────┘     │
│                                                                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
              data/raw/ contains per sample:
              ├── {id}_t1_trajectory.jsonl   (rollout 1 conversation)
              ├── {id}_p1.diff              (rollout 1 patch)
              ├── {id}_t1_meta.json         (metadata)
              ├── {id}_synth_pr.md          (synthetic PR)
              ├── {id}_t2_trajectory.jsonl   (rollout 2 conversation)
              ├── {id}_p2.diff              (rollout 2 patch)
              ├── {id}_t2_meta.json         (metadata)
              └── {id}_verification.json    (recall score)

                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                    PHASE 6: FILTERING (filter_data.py)                │
│                                                                      │
│  For T1 trajectories, reject if:                                    │
│    ✗ Empty patch                                                     │
│    ✗ Patch > 40 lines                                                │
│    ✗ Avg tool output > 600 tokens                                    │
│    ✗ Truncation ratio < 0.88                                         │
│    ✗ Total tokens > 32768                                            │
│    ✗ Duplicate patch (SHA-256 hash match)                            │
│                                                                      │
│  For T2 trajectories, same filters PLUS:                             │
│    ✗ Recall score < 0.5                                              │
│                                                                      │
│  OUTPUT: selected_samples.jsonl                                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│               PHASE 7: SFT FORMATTING (format_for_training.py)       │
│                                                                      │
│  For each selected sample:                                           │
│                                                                      │
│  T1 trajectory → multi-turn conversation:                            │
│    [system] You are an autonomous coding agent...                    │
│    [user]   There is a {bug} in {function}...                        │
│    [assistant] <think>reasoning</think> ```bash grep...```           │
│    [user]   [bash] Exit code: 0 ...output...                        │
│    [assistant] <think>reasoning</think> str_replace...               │
│    ...                                                               │
│    [assistant] SUBMIT                                                │
│                                                                      │
│  T2 trajectory → multi-turn conversation:                            │
│    [system] You are an autonomous coding agent...                    │
│    [user]   Please implement this PR: ## Title: Fix...               │
│    [assistant] <think>reasoning</think> ```bash grep...```           │
│    ...                                                               │
│    [assistant] SUBMIT                                                │
│                                                                      │
│  Split 90/10 → train / held-out                                     │
│                                                                      │
│  OUTPUT:                                                             │
│    oai5g_train.jsonl      (SFT training data)                        │
│    oai5g_held_out.jsonl   (evaluation data)                          │
│    oai5g_train.csv        (human-readable view)                      │
│    dataset_stats.json     (token distribution)                       │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Insight

The **two-rollout design** is a self-consistency check. If the model can't reproduce its own change from a PR description alone, the original trajectory was likely noisy or arbitrary — bad training data. No human labels or test suites needed.

## SFT Training Objective

At each assistant turn, the model learns to predict:
- **Input**: system prompt + all prior turns (prompts, previous responses, tool observations)
- **Output**: reasoning (`<think>` trace) + action (tool call or SUBMIT)

Loss is computed **only on assistant turns**. The model learns *how to think about code* and *what action to take*, not how to produce tool outputs.

## Dataset Composition

| Type | Description | Count Target |
|------|-------------|--------------|
| T1 | Guided fix (bug hint + function location) | 5,000 |
| T2 | PR implementation (only PR description) | 3,000 |
| **Total** | Mixed for well-rounded agent | **8,000** |

T1 teaches exploration/debugging. T2 teaches specification-following. Both needed for a capable repo agent.
