# Eval Prediction Requirements

Spec for generating **predicted patches** from a code agent against the
`repo-evals` ground-truth dataset. Drop this into `repo-agents` and point
Claude Code at it — the task is to implement a runner that consumes a
**prompts JSONL** (issue + checkout point, no solution) and emits a
**predictions JSONL** compatible with `repo-evals/pipeline_eval.py`.

Scoring happens in `repo-evals` and is out of scope here. The runner must
never see the ground-truth patch, commit SHA, or commit message.

---

## Inputs

### 1. Prompts JSONL

Exported from `repo-evals` by stripping the ground-truth fields from
`dataset_commits.jsonl`. One record per line:

```json
{
  "instance_id": "open5gs__open5gs-51acc388a675",
  "repo": "open5gs/open5gs",
  "platform": "github",
  "clone_url": "https://github.com/open5gs/open5gs.git",
  "base_commit": "7dfd9a39649700c24c22f1978ed7a35541a72cca",
  "issue_title": "Missing IFC data in IMS user context ...",
  "issue_body": "## Description\n\nWhen retrieving IMS subscriber ..."
}
```

- `instance_id` — round-trip to the prediction output unchanged.
- `base_commit` — check this out before running the agent. This is the
  **parent** of the fix commit, so the bug is present. It is not a leak.
- `issue_title` + `issue_body` — the agent's only task prompt.
- No other fields are present. The ground-truth patch, fix SHA, and
  commit message stay in `repo-evals` and are invisible to this runner.

Records for many different repos are interleaved; many instances share a
single repo with different `base_commit`s.

### 2. Model config (CLI)

- `--prompts <path>` — prompts JSONL.
- `--model <name>` — model identifier (free-form, written into output).
- `--provider-url <url>` — OpenAI-compatible base URL.
- `--provider-key <key>` — API key (prefer env var).
- `--num-predictions <int>` — runs per instance (default 1, enables pass@k).
- `--workers <int>` — concurrent instances.
- `--limit <int>` — cap instances for smoke tests.
- `--output <path>` — predictions JSONL (default `predictions.jsonl`).
- `--instance-ids <csv>` — optional filter, useful for retries.
- `--timeout-s <int>` — per-run timeout, default ~600s.

---

## Output

### `predictions.jsonl`

One line per `(instance_id, run_index)`. Required fields:

```json
{
  "instance_id": "open5gs__open5gs-51acc388a675",
  "model": "gemini-3-flash-preview",
  "patch": "diff --git a/lib/dbi/ims.c b/lib/dbi/ims.c\n--- a/lib/dbi/ims.c\n...",
  "exit_code": 0,
  "run_index": 0,
  "duration_s": 42.7,
  "session_id": "…optional agent trace id…"
}
```

- `patch` — unified diff against `base_commit`, equivalent to running
  `git diff` (+ untracked files) at end of session. Empty string on failure.
- `exit_code` — `0` success, non-zero agent error, `-1` timeout/crash.
- Writes are append-only and serialised so the file is safe under
  `--workers > 1` and resumable.

Also emit a sibling `metadata.json` with: model, provider URL (no key),
prompts path + sha256, num_predictions, workers, started_at, finished_at,
counts.

---

## Behavioural requirements

### Repo handling (the main complication — many repos, many instances)

- Cache clones in a working dir keyed by `repo`; do not re-clone per instance.
- For each instance, create an **isolated worktree or container** at
  `base_commit`. Concurrent workers on the same repo must not share a
  checkout — use `git worktree add <path> <base_commit>`, or a per-instance
  shallow clone, or a Docker bind-mount of a fresh copy.
- Support both GitHub and GitLab clone URLs.
- Clean up worktrees after each instance regardless of outcome.

### Agent execution

- The agent's prompt is `issue_title` + `issue_body` and nothing else about
  the fix.
- The agent's working directory is the worktree at `base_commit`.
- At the end of each run, capture the patch via `git diff` on tracked files
  plus untracked files from `git ls-files --others --exclude-standard`.
- On timeout: record `exit_code=-1`, empty `patch`, move on.
- Never commit or push from the worktree.

### Resumability

- On startup, read existing `--output` and skip `(instance_id, run_index)`
  pairs already present with a non-empty `patch` or `exit_code == 0`.
- Failures (empty patch and `exit_code != 0`) are retried.
- Mirrors the resume logic in `repo-evals/pipeline_hydron.py`.

### Concurrency

- `--workers N` runs N instances in parallel using repo-agents' existing
  worker pool.
- Single lock around the JSONL append.
- Clone cache access safe for concurrent `git worktree add`.

### Logging

- Per-instance prefix `[<instance_id>]`.
- Print start, each run completion with patch length + duration + exit code,
  and a final tally.

---

## Non-requirements

- No scoring, no BLEU/AST/edit-distance, no paraphrase generation — that is
  `pipeline_eval.py`.
- No dataset filtering or regeneration — prompts are frozen.
- No evaluation harness integration beyond emitting the JSONL.

---

## Acceptance check

```bash
# in repo-agents
uv run <runner> \
    --prompts /path/to/prompts.jsonl \
    --model <model> \
    --provider-url <url> \
    --provider-key $KEY \
    --num-predictions 1 \
    --workers 4 \
    --limit 5 \
    --output predictions.jsonl

# in repo-evals
uv run python pipeline_eval.py \
    --ground-truth dataset_commits.jsonl \
    --predictions predictions.jsonl \
    --output eval_results.jsonl \
    --metrics bleu ast edit_distance location_iou
```

Must produce one scored row per prompt present in predictions, no schema
errors.

---

## Reference

See `repo-evals/pipeline_hydron.py` for a working single-agent implementation
(hydron binary in Docker). It demonstrates the prediction schema, resume
logic, concurrency, and metadata file — reuse those patterns.
