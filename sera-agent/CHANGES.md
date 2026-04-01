# SERA Agent — Changelog & Design Decisions

## What This Is

A lightweight inference harness for running the fine-tuned Nemotron-3-Nano-30B-A3B
model on OpenAirInterface 5G bug-fixing tasks. Built as a focused alternative to
full frameworks like SWE-agent or OpenHands — 4 files, ~540 lines, zero framework
dependencies beyond `requests`.

## Files Created in This Session

### sera-agent/ (NEW — inference harness)

```
sera-agent/
├── __init__.py              # Package docstring
├── sera_agent.py            # Main entrypoint: LLMClient, ToolExecutor, SeraAgent, CLI
├── tools/
│   ├── __init__.py
│   ├── parser.py            # Nemotron <tool_call> XML parser
│   └── editor.py            # str_replace_editor implementation
└── tests/
    ├── __init__.py
    └── test_harness.py      # Full test suite
```

### configs/ (MODIFIED — added patched template)

```
configs/
└── nemotron_chat_template_patched.jinja   # Nemotron chat template with {% generation %} markers
```

### scripts/ (EXISTING — conversion script)

```
scripts/
└── convert_sft_for_megatron.py   # SERA → Megatron-Bridge dataset converter
```

### data/megatron_sft/ (NEW — converted training data)

```
data/megatron_sft/
├── training.jsonl       # 821 samples, 78MB — Megatron-Bridge native format
├── validation.jsonl     # 92 samples, 8.3MB
└── tool_schemas.json    # 3 tool schemas
```

---

## Key Changes & Why

### 1. Patched Chat Template (`configs/nemotron_chat_template_patched.jinja`)

**Problem**: Nemotron-3-Nano's original chat template lacks `{% generation %}`/
`{% endgeneration %}` markers. Megatron-Bridge's `_chat_preprocess()` uses these
to build the loss mask. Without them, it falls back to `mask = [1] * len(input_ids)`
— computing loss on ALL tokens (system prompt, user messages, tool responses).

**Fix**: Added `{% generation %}` markers around all 4 assistant output paths in
the Jinja2 template:
- Assistant with tool calls (line 122 + 158)
- Assistant without tool calls, not truncated (line 162)
- Assistant without tool calls, truncated with content (line 170)
- Assistant without tool calls, truncated empty (line 172)

**Impact**: Loss computed on 18.9% of tokens (assistant only) vs 100% (everything).
Verified across all 821 training samples — 5,184,504 assistant tokens vs 22,202,057
masked tokens.

**Usage**: Set `cfg.tokenizer.chat_template` to the file contents in the training
config:
```python
with open("configs/nemotron_chat_template_patched.jinja") as f:
    cfg.tokenizer.chat_template = f.read()
```

### 2. Dataset Conversion (`scripts/convert_sft_for_megatron.py`)

**What it does**: Converts SERA SFT dataset from the raw rollout format (with
`conversations` key using `role`/`content`/`tool_calls`) to Megatron-Bridge's
native format (with `messages` key and structured `tool_calls` using parsed dict
arguments).

**Key decisions**:
- Uses `{"messages": [...]}` format (not `{"conversations": [{"from", "value"}]}`)
  because Megatron-Bridge's `_convert_to_openai_messages()` passes it through
  directly without key remapping.
- Preserves structured `tool_calls` with `arguments` as a parsed dict (not JSON
  string) because Nemotron's Jinja2 template iterates `tool_call.arguments|items`.
- Merges consecutive `role="tool"` messages (3,186 merges across 698/821 samples)
  because Nemotron's template wraps consecutive tool responses in a single
  `<|im_start|>user` block.
- Includes tool schemas per-sample in the `"tools"` field so `apply_chat_template`
  renders them in the system prompt.

**Output**: `training.jsonl` (821 samples) and `validation.jsonl` (92 samples)
in `data/megatron_sft/`.

### 3. Tool Call Parser (`sera-agent/tools/parser.py`)

**What it does**: Extracts structured `ToolCall(name, arguments)` objects from
the model's native XML output format:
```xml
<tool_call>
<function=bash>
<parameter=command>
find /repo -name "foo.c"
</parameter>
</function>
</tool_call>
```

**Edge cases handled**:
- `<tool_call>` inside parameter values (e.g., `echo "<tool_call>"`) — solved by
  only splitting on `<tool_call>` at line boundaries (`(?:^|\n)<tool_call>`).
- `</parameter>` inside parameter values (e.g., `echo "</parameter>"`) — solved by
  only matching `\n</parameter>` (real closing tags are always on their own line).
- Multiple tool calls in one response.
- Submit tool with no parameters.
- Malformed/partial output (returns what it can parse).

**Validation**: 27,187 tool calls parsed across all 821 training samples with
zero errors. Tool distribution: bash=14,106, str_replace_editor=11,466, submit=1,615.

### 4. File Editor (`sera-agent/tools/editor.py`)

**What it does**: Implements the `str_replace_editor` tool with 5 commands matching
the SWE-bench interface used in training data.

**Key behaviors matching training data**:
- `view` output format: `"Here's the result of running 'cat -n' on {path}:\n..."`
  with `{line_no:6d}\t{content}` line formatting.
- `str_replace` rejects ambiguous replacements (multiple matches) with line numbers.
- `str_replace` shows context around the edit after applying.
- `undo_edit` maintains a per-file stack (supports multiple undos).
- `create` fails if file exists (forces `str_replace` for edits).

### 5. Agent Loop (`sera-agent/sera_agent.py`)

**Architecture** (inspired by mini-SWE-agent's simplicity):
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

**Design decisions**:
- **Single-file agent** — no plugin system, no YAML configs, no abstractions.
  The entire loop is visible in `SeraAgent.run()`.
- **OpenAI-compatible client** — works with vLLM, TGI, OpenAI, or any server
  that speaks `/v1/chat/completions`. Uses `requests` directly (no SDK needed).
- **Dual tool_call handling** — if vLLM parses tool calls server-side (returning
  `message.tool_calls`), reconstructs XML so the parser handles it uniformly.
  If the model returns XML in `message.content` (our fine-tuned model's format),
  parses directly.
- **Issue prompt template** — matches training data exactly: `<uploaded_files>`,
  `<pr_description>`, and the same step-by-step instructions.
- **Trajectory saving** — full messages + per-step tool call log saved as JSON
  for debugging and analysis.

---

## Validation Summary

| Test | Scope | Result |
|---|---|---|
| Parser unit tests | 6 edge cases | All pass |
| Editor integration | 8 operations | All pass |
| Parser on 1 sample | 59 tool calls | 0 errors |
| Parser on 50 samples | 1,680 tool calls | 0 errors |
| Parser on full dataset | 27,187 tool calls | 0 errors |
| Loss mask (patched template) | 821 samples, 27.4M tokens | 18.9% assistant, 81.1% masked |
| Full round-trip | parse → execute → template render | Verified |
| Nemotron format compatibility | Template render → parse → execute | Verified |
