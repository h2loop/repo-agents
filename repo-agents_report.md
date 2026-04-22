# SERA: Soft-Verified Efficient Repository Agents

## Introduction

Teaching a language model to act as a competent engineer inside a real codebase — navigating directories, reading unfamiliar C++, proposing a concrete fix, and producing a clean patch — requires training data that looks like real engineering work. The obvious source, human-labeled bug fixes, is expensive and scarce, especially for specialized domains like telecom radio access networks or embedded RTOS codebases where the pool of qualified labelers is small. The common alternative, synthetic single-turn data, teaches the model to produce plausible-looking diffs but not to investigate, explore, or recover from mistakes.

`repo-agents` is our end-to-end system for producing high-quality multi-turn agent trajectories without human labels, and then fine-tuning an open model on them so it can autonomously fix bugs in a specific target codebase. The project is named SERA, for *Soft-Verified Efficient Repository Agents*, following the SERA paper the approach is built on (a copy of the paper is checked into the repo). It currently targets telecom 5G codebases (srsRAN Project, OpenAirInterface 5G) as the flagship case study, and the pipeline has been generalized to handle arbitrary C, C++, and Go repositories — infrastructure is in place for Zephyr, NuttX, mbed-OS and similar embedded codebases.

Our contribution is threefold:

1. **A trajectory generation pipeline** that produces agentic SFT data from any target repo with no human labeling, by running two independent agents on the same problem and keeping only the cases where they converge on the same patch.
2. **A training stack** wired end-to-end against NVIDIA Nemotron-3-Nano-30B-A3B (a hybrid Mamba-2 + Attention + MoE model) via Megatron-Bridge, including a patched chat template that is a prerequisite for training a tool-using agent on this model family.
3. **An inference harness (`sera-agent`)** that runs the fine-tuned model against a real repo with a minimal three-tool interface, plus an evaluation runner (`predict_patches.py`) that produces predictions against the sibling `repo-evals` ground-truth dataset.

## Inputs

The pipeline's input is a target Git repository, a language tag (`c_cpp` or `go`), and optionally a domain tag (`telecom_5g`). Everything downstream is derived.

**Function extraction.** `scripts/extract_functions_generic.py` walks the repo using tree-sitter parsers for C, C++, and Go, and emits a JSONL of every function definition with its name, file, line number, and subsystem tag. For the canonical OAI5G case, this produces 10,056 functions; for srsRAN Project, the extractor is configured to scan `apps/`, `include/`, `lib/`, `tests/`, `utils/` and skip auto-generated ASN.1 code. Functions are the unit of sampling in the pipeline — every function in the codebase is attempted at least once.

**Bug prompt taxonomy.** Prompts are assembled from two independent dimensions. Language bugs (`configs/bug_prompts/lang_c.json`, `lang_go.json`) cover 40 generic C/C++ issues (buffer overflow, use-after-free, null deref, integer overflow, etc.) and 29 Go issues (goroutine leaks, unchecked errors, nil map writes). Domain bugs (`configs/bug_prompts/domain_telecom_5g.json`) cover 25 telecom-specific issues — protocol state machine errors, HARQ timing bugs, ASN.1 encoding errors, timer misuse — written against canonical OAI5G subsystem paths. The two dimensions are assembled per-repo by `populate_repo_config.py`, which uses an LLM call to remap the canonical domain subsystems onto the target repo's actual directory structure. Adding a new language or a new domain does not require touching the other dimension.

**Commit snapshots and Docker images.** For each target repo we pick a handful of commit SHAs (five for srsRAN and for OAI5G) and build a Docker image per SHA from `docker/Dockerfile.sera`. Agents run inside these containers so they have a real build environment, can execute `make`, `grep`, `find`, and so on, and cannot accidentally mutate the host. Multiple SHAs provide commit-level diversity across samples.

**Output artifacts per sample.** Each pipeline run produces, for one (function × bug) pair: a Rollout-1 trajectory (`_t1_trajectory.jsonl`), its patch (`_p1.diff`), a synthetic PR (`_synth_pr.md`), a Rollout-2 trajectory (`_t2_trajectory.jsonl`) and patch (`_p2.diff`), plus metadata and a verification score.

## Methodology

### Trajectory generation via self-verification

The central idea of SERA is that two independent attempts at the same fix, if they converge on similar patches, are almost certainly correct — without any human looking at them. This turns a labeling problem into an agreement problem, which is cheap to measure at scale.

Concretely, the pipeline runs four stages per function, orchestrated by `scripts/generate_data.py`:

**Stage 1 — Rollout 1 (change generation).** A function is picked from the extracted set, paired with a sampled bug type, and the template in `configs/bug_prompt_template.txt` produces a deliberately vague prompt: *"There is a {bug_type} downstream of function {func_name} in {file_path}:{line}. Investigate and fix it."* The vagueness is intentional — the agent must explore the file and neighbouring code to decide whether the bug is real and what to do about it, producing the kind of investigative trajectory we want the student model to imitate. The agent is the `hydron` binary running inside a Docker container, with full shell access, driven by an OpenAI-compatible LLM endpoint (default: Qwen3-Coder-480B via LiteLLM). The resulting trajectory T1 and `git diff` P1 are saved; empty or comment-only patches are rejected immediately.

**Stage 2 — Synthetic PR generation.** A teacher model reads T1 and P1 and writes a pull-request description in the style of real contributions from the target repo, using few-shot examples from `configs/demo_prs/`. This PR description is the *only* information passed to stage 3 — it is the information bottleneck that forces the next agent to work independently. If the second agent could see T1, it would trivially imitate it and the verification signal would be meaningless.

**Stage 3 — Rollout 2 (reproduction).** A fresh container, a fresh agent, and only the synthetic PR. The agent must locate the relevant files on its own, understand the change from the natural-language description, and implement it. This produces T2 and P2.

**Stage 4 — Soft verification.** P1 and P2 are compared by line-level recall after whitespace normalization and fuzzy matching (>= 0.7 similarity via Python's `SequenceMatcher`, to tolerate variable renames):

$$\text{recall} = \frac{\lvert \text{lines}(P_2) \cap \text{lines}(P_1) \rvert}{\lvert \text{lines}(P_1) \rvert}$$

Samples are bucketed into `hard_verified` (recall >= 0.8), `soft_verified` (>= 0.4), and `unverified` (< 0.4). Soft-verified and above are eligible for training.

### Quality filtering

Verified does not automatically mean good-for-SFT. Following the SERA paper (Section 5.2), `scripts/filter_data.py` applies a second gate targeting known failure modes in SFT data:

- **Patch <= 40 lines.** Large patches correlate with unfocused or hallucinated fixes; small targeted patches train better agents.
- **Average tool output <= 600 tokens.** Trajectories that dump whole files teach the model to lean on noisy context instead of running targeted commands.
- **Truncation ratio >= 0.88.** The trajectory must fit in the 32K-token training window without losing more than 12% of its content — heavily truncated traces teach incomplete reasoning chains.
- **Duplicate patch deduplication.** Identical patches from different functions add no training signal and would over-weight a single fix pattern.
- **T2 verification score >= 0.5.** Rollout-2 trajectories only enter the dataset if the reproduction substantially matched the original.

On the OAI5G run, this produced the `data/sft_dataset/` now checked in: 420 trajectories (303 T1 + 117 T2), 378 train / 42 held-out, mean length 8,766 tokens and mean 75 turns per trajectory.

### Training

For fine-tuning we chose **NVIDIA Nemotron-3-Nano-30B-A3B**, a hybrid Mamba-2 + Attention + MoE model (~32.88B total params, ~3B active via 6-of-128 expert routing). The choice was driven by two considerations: the MoE structure lets us train at a much lower active-parameter cost than a dense 30B model, and Nemotron's tool-use chat template aligns with the tool calls in our training data. Training runs under **Megatron-Bridge** with two supported modes — LoRA on 1 node / 8 GPUs (rank 32, alpha 32, targeting `linear_qkv`, `linear_proj`, `linear_fc1`, `linear_fc2`, `in_proj`, `out_proj` so that both Mamba and Attention/MoE layers are adapted) and full SFT on 2 nodes / 16 GPUs at LR 5e-6. `expert_model_parallel_size` is pinned to 8 so each GPU holds exactly 16 of the 128 experts.

One non-obvious change was essential: Nemotron's stock chat template lacks the `{% generation %}` / `{% endgeneration %}` markers that Megatron-Bridge uses to build the loss mask. Without them, loss is computed on 100% of tokens — system prompt, user messages, tool outputs — diluting the gradient signal with content the model should not be imitating. We ship `configs/nemotron_chat_template_patched.jinja`, which adds the markers at the four assistant-output paths in the template (ordinary assistant output, assistant with tool calls, and two truncation branches). With the patch, loss is computed on 18.9% of tokens (assistant turns only), verified across all 821 samples of the training set used during bring-up.

### Inference harness

`sera-agent/` is deliberately minimal: no Langchain, no agent framework, about 300 lines of Python wrapping a vLLM-served checkpoint. The agent loop is *generate -> parse tool calls -> execute -> append result -> repeat*, and there are exactly three tools:

- `bash` (52.1% of training-time tool calls): `subprocess.run` in the repo working directory with a 120s timeout.
- `str_replace_editor` (41.9%): five commands — `view` (cat -n), `str_replace`, `create`, `insert`, `undo_edit`.
- `submit` (5.9%): runs `git diff` to capture the final patch and terminates the loop.

The parser (`sera-agent/tools/parser.py`) handles Nemotron-native XML tool calls and specifically guards against false positives where `<tool_call>` or `</parameter>` appear inside an `echo` or a file's content, by only splitting on tags at line boundaries. It was validated against 27,187 real tool calls from the training set with zero parse errors.

### Evaluation runner

`scripts/predict_patches.py` is the runner that consumes a prompts JSONL from the sibling `repo-evals` dataset — `{instance_id, repo, base_commit, issue_title, issue_body}` per line — and produces a predictions JSONL of `{instance_id, model, patch, exit_code, run_index, duration_s}`. It clones each repo once into a cache, creates an isolated `git worktree` per instance at the specified `base_commit`, runs the agent against that worktree, captures the patch via `git diff` plus untracked files, and cleans up. It is resumable (skips `(instance_id, run_index)` pairs already present with non-empty patch), safe under `--workers > 1` via a lock on the JSONL append, and supports pass@k via `--num-predictions`. Scoring happens out-of-process in `repo-evals/pipeline_eval.py`.

## Engineering

Running trajectory generation at scale is less about the LLM and more about keeping a fleet of agent sessions alive against flaky containers and rate-limited APIs. Each rollout is a `hydron run --auto --skip-auth --format json` invocation executed via `docker exec` into a per-image container pool (`scripts/hydron_runner.py`, `scripts/generate_data.py`), so the agent sees a real filesystem with `make`, `grep`, and `find` but cannot touch the host; trajectories are streamed back as one JSON event per stdout line and the final patch is captured with `git diff` inside the container. The driver groups the sample plan by Docker image and processes one image batch at a time, warming a pool of up to `--workers` containers per batch so total live containers are bounded regardless of how many SHAs are in play, with a `pre_run_cleanup()` that reaps orphaned `sera_pipeline` containers from prior crashed runs before warming the next pool. Concurrency is driven by a `ThreadPoolExecutor`, and because hydron persists session state to `~/.local/share/hydron-cli/kilo.db`, each session is given a private `HOME` via a fresh `tempfile.mkdtemp` with the real `~/.config/hydron-cli` symlinked in — without this, concurrent processes hit EBADF / SQLite lock contention on the shared DB. Rate-limit handling is multi-worker-safe and per-provider: the runner discovers a pool of `Provider(kind, api_key, model)` entries from the environment (any number of `GOOGLE_GENERATIVE_AI_API_KEY_<suffix>` Google-native keys plus an optional OpenAI-compatible LiteLLM provider), picks one round-robin per session, and caps in-flight sessions against any single api_key at `PROVIDER_MAX_INFLIGHT=8` via a per-key semaphore so twenty workers against one key don't all 429 simultaneously. When hydron's combined stdout/stderr matches a 429 / `RateLimitError` / `resource_exhausted` / `retryDelay` signal, the runner parses the server's Retry-After hint out of the output (HTTP header, Google gRPC `retryDelay`, or free-text "retry in Ns"), takes the max of that hint and an exponential backoff with jitter, clamps it to `RATE_LIMIT_MAX_BACKOFF=300s`, and records a cooldown-until timestamp keyed by api_key so one Google key's 429 does not pause workers using a different key or the LiteLLM endpoint; retry picks a different provider first and falls back to the same key once its cooldown expires, which is the only viable path for single-provider setups. Resume is handled at the function granularity: `--resume` scans the output directory for `*_t1_meta.json` plus matching `_t2_meta.json` and `_verification.json` with recall ≥ 0.5, treats only that triple as "done", and explicitly re-queues low-score, T1-only, and unverified attempts, printing a count of each class before execution — so a crashed overnight run resumes without redoing verified work and without silently accepting half-finished samples as completions. The eval-time counterpart (`scripts/predict_patches.py`) applies the same rate-limit and slot-acquisition machinery to host-side hydron sessions running in per-instance `git worktree`s, and is resumable via a file lock on the predictions JSONL so `--workers > 1` appenders don't interleave lines.

## Evaluation

Scoring of the fine-tuned model lives in the sibling `repo-evals` repository and is out of scope for this repo's runner, which only emits predictions. `repo-evals` scores predictions against ground-truth commits using BLEU, AST similarity, edit distance, and location IoU (the overlap between the files the agent changed and the files the ground-truth fix changed).

Within `repo-agents` itself, the quantifiable numbers produced so far describe the **dataset**, not the downstream model:

| Stage | Input | Output | Yield |
|-------|-------|--------|-------|
| T1 rollout (OAI5G) | 337 attempted | 303 passed quality filters | 89.9% |
| T2 rollout (OAI5G) | 297 attempted | 117 passed quality filters | 39.4% |
| Combined SFT set   |               | 420 trajectories (378 train / 42 held-out) | — |

The T2 yield is substantially lower than T1 because T2 has to clear two extra gates: verification recall >= 0.5 against the original patch (eliminating 85 samples) and duplicate-patch deduplication against the existing T1 set (eliminating 92). This matches the design intent — T2 samples only enter training when the reproduction is both correct and novel.

A separate `benchmark_results.json` at the repo root contains single-turn latency/throughput probes of three candidate teacher models (Kimi K2 Thinking, DeepSeek v3.2, Qwen3 Coder 480B) on generic coding prompts. It is a throughput sanity check, not a SERA evaluation, and should not be read as one.

## Analysis

The approach works because the two rollouts are genuinely independent. Stage 1 sees a function and a bug type, stage 3 sees a natural-language PR description — there is no shared tensor, no shared container, no shared conversation history. When P1 and P2 overlap at 40%+ of lines, it is very likely that both agents independently converged on the correct fix, because the space of plausible patches for a given real bug is narrow. When they diverge, one of them is usually wrong (or the "bug" wasn't really a bug), and dropping the sample costs us nothing.

We hypothesize that the relatively low T2 yield (39.4%) is mostly a *feature*, not a bug. Of the 180 T2 samples rejected, 85 failed verification and 92 were duplicates of existing T1 patches. The duplicates mean the second agent found the same small diff without noise — a positive outcome that simply doesn't add training signal. The verification failures are the meaningful rejections, and at ~28% they line up with what one would expect if a substantial minority of synthetic PRs are underspecified or point at code where multiple plausible fixes exist.

The filter thresholds are worth interpreting plainly. The 40-line patch cap and 600-token average-tool-output cap both push the dataset toward *targeted investigation followed by a small, focused fix* — the behaviour we want in an agent. A 500-line patch in training data teaches the model that when in doubt, rewrite half the file. The 88% truncation-ratio threshold is a practical admission that our 32K training window is tight for a tool-using agent that runs `grep` and reads files: at mean 8,766 tokens per trajectory we are comfortable, but the tail (max 28,533) would spill over without truncation, and training on a half-seen trajectory teaches the model to produce patches without the reasoning that led there.

The choice of Nemotron-3-Nano-30B-A3B over a dense model of comparable size reflects a cost bet: per-token FLOPs scale with the ~3B active parameters, not the 32.88B total, while model capacity scales with the total. For an agent that must memorize a specific codebase's idioms and call conventions, capacity matters more than we initially expected, and the MoE structure lets us buy it cheaply. The downside, and the one we were unaware of before bring-up, is that MoE training requires `expert_model_parallel_size=8` as a hard floor — there is no meaningful "single-GPU LoRA" configuration for this model. That constraint made the chat-template patch critical: on 8 GPUs with 128 experts, wasting gradient signal on user/tool tokens is an expensive mistake.

A last observation is about generalization across repos. The pipeline was built against OAI5G, then re-targeted at srsRAN with only configuration changes (no code changes to the core pipeline, only `populate_repo_config.py` to remap domain subsystems). This was surprisingly smooth and suggests the architectural split between language bugs, domain bugs, and repo-specific config is the right one. The analysis in `hw_repos_sera_analysis.md` identifies Zephyr, NuttX, RT-Thread, and mbed-OS as the strongest next targets for the embedded-hardware variant of the same pipeline, chosen on merged-PR volume, merge rate, and subsystem diversity — all properties the pipeline implicitly relies on.

## References

- **SERA paper** — *Soft-Verified Efficient Repository Agents*, included as `SERA Soft Verified Efficient Repository Agents.pdf` at the repo root. Section 5.2 defines the quality filters used in stage 5 of the pipeline.
- **Hydron** — the agent binary used for rollouts. Invoked via `docker exec` with `--skip-auth` and inline provider flags.
- **NVIDIA Nemotron-3-Nano-30B-A3B-BF16** — base model for fine-tuning. Hugging Face: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16`.
- **Megatron-Bridge** — NVIDIA's training framework used for both LoRA and full SFT. <https://github.com/NVIDIA/Megatron-Bridge>.
- **Qwen3-Coder-480B-A35B-Instruct** — default teacher model driving stage-1 and stage-3 rollouts via a LiteLLM proxy.
- **srsRAN Project** — <https://github.com/srsran/srsRAN_Project>. Primary C++ target for the generalized pipeline.
- **OpenAirInterface 5G** — <https://gitlab.eurecom.fr/oai/openairinterface5g>. Original C target and the source of the canonical telecom subsystem taxonomy.
- **tree-sitter** — used for language-agnostic function extraction (`tree-sitter-c`, `tree-sitter-cpp`, `tree-sitter-go`).
- **repo-evals** — sibling repository that owns the ground-truth dataset and scoring. `scripts/predict_patches.py` is the contract between the two.
