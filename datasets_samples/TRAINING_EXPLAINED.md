# Agent Training & Inference Explained

## Part 1: The Data Structure

Each training sample is a **multi-turn conversation**:

```
Message 1: SYSTEM    → Defines available tools
Message 2: USER      → Task description ("fix this bug")
Message 3: ASSISTANT → Think + Tool call        ← MODEL LEARNS THIS
Message 4: USER      → Tool response
Message 5: ASSISTANT → Think + Tool call        ← MODEL LEARNS THIS
Message 6: USER      → Tool response
... repeat until task complete ...
```

---

## Part 2: What the Model Learns

### Input (given to model):
```
SYSTEM: You have these tools: bash, str_replace_editor...

USER: Fix the bug in /testbed. Here's the PR description...

ASSISTANT: <think>Let me explore...</think>
<tool_call>{"name": "bash", "arguments": {"command": "find /testbed -name '*.py'"}}</tool_call>

USER: <tool_response>
/testbed/src/main.py
/testbed/src/utils.py
</tool_response>
```

### Target (model predicts):
```
ASSISTANT: <think>I found the files. Let me read main.py to understand the bug...</think>
<tool_call>{"name": "str_replace_editor", "arguments": {"command": "view", "path": "/testbed/src/main.py"}}</tool_call>
```

The model learns to predict the NEXT assistant turn given all previous context.

---

## Part 3: Training Process

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTTrainer, SFTConfig

# 1. Load base model (e.g., Llama, Mistral, Qwen)
model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.1-8B")
tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3.1-8B")

# 2. Load your formatted data
from datasets import load_dataset
dataset = load_dataset("json", data_files="sera_hf_sft_100.jsonl", split="train")

# 3. Train - loss computed ONLY on assistant turns
trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    args=SFTConfig(
        output_dir="./agent-model",
        max_seq_length=8192,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
    ),
)
trainer.train()
```

### What happens during training:

```
Tokenized conversation:
[SYSTEM] You have tools... [USER] Fix bug... [ASSISTANT] <think>... [USER] <tool_resp>...
   ↓         ↓                   ↓                ↓              ↓           ↓
  MASK     MASK               COMPUTE           MASK          COMPUTE      MASK
                               LOSS                            LOSS

Only ASSISTANT tokens contribute to loss!
```

---

## Part 4: Inference (Using the Trained Model)

You need an **execution harness** - code that runs the loop:

```python
import json
import re
import subprocess

def run_agent(model, tokenizer, task: str):
    """Run the trained agent on a task."""

    # System prompt (same as training)
    system = """You have these tools:
    - bash: run shell commands
    - str_replace_editor: view/edit files

    Use <tool_call>{"name": "...", "arguments": {...}}</tool_call>
    """

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": task}
    ]

    for turn in range(50):  # Max 50 turns
        # 1. Generate model response
        prompt = tokenizer.apply_chat_template(messages, tokenize=False)
        output = model.generate(prompt, max_tokens=2048)
        assistant_msg = output  # The model's response

        messages.append({"role": "assistant", "content": assistant_msg})

        # 2. Check if done (no tool call)
        if "<tool_call>" not in assistant_msg:
            print("Agent finished!")
            return assistant_msg

        # 3. Parse and execute tool call
        tool_call = parse_tool_call(assistant_msg)
        result = execute_tool(tool_call)

        # 4. Add tool response and continue
        messages.append({"role": "user", "content": f"<tool_response>\n{result}\n</tool_response>"})

    return "Max turns reached"


def parse_tool_call(text: str) -> dict:
    """Extract tool call JSON from assistant response."""
    match = re.search(r'<tool_call>\s*(\{.*?\})\s*</tool_call>', text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return None


def execute_tool(tool_call: dict) -> str:
    """Execute a tool and return result."""
    name = tool_call["name"]
    args = tool_call["arguments"]

    if name == "bash":
        result = subprocess.run(
            args["command"],
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout + result.stderr

    elif name == "str_replace_editor":
        if args["command"] == "view":
            with open(args["path"]) as f:
                return f.read()
        # ... handle other commands

    return f"Unknown tool: {name}"


# Run it!
result = run_agent(model, tokenizer, "Fix the bug in auth.py that causes login to fail")
```

---

## Part 5: Concrete Example Flow

### Task: "Fix the off-by-one error in utils.py line 42"

```
┌─────────────────────────────────────────────────────────────────┐
│ TURN 1                                                          │
├─────────────────────────────────────────────────────────────────┤
│ INPUT TO MODEL:                                                 │
│   System: You have tools: bash, str_replace_editor...           │
│   User: Fix the off-by-one error in utils.py line 42            │
│                                                                 │
│ MODEL GENERATES:                                                │
│   <think>                                                       │
│   I need to first look at the file to understand the bug.       │
│   Let me view utils.py around line 42.                          │
│   </think>                                                      │
│   <tool_call>                                                   │
│   {"name": "str_replace_editor",                                │
│    "arguments": {"command": "view", "path": "/repo/utils.py",   │
│                  "view_range": [35, 50]}}                       │
│   </tool_call>                                                  │
│                                                                 │
│ YOUR CODE EXECUTES:                                             │
│   → Reads utils.py lines 35-50                                  │
│   → Returns file content                                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ TURN 2                                                          │
├─────────────────────────────────────────────────────────────────┤
│ INPUT TO MODEL (includes all previous + tool response):         │
│   ...previous messages...                                       │
│   User: <tool_response>                                         │
│         35│ def process_items(items):                           │
│         36│     results = []                                    │
│         37│     for i in range(len(items)):                     │
│         38│         if i < len(items) - 1:  # BUG: off by one   │
│         39│             results.append(items[i])                │
│         40│     return results                                  │
│         </tool_response>                                        │
│                                                                 │
│ MODEL GENERATES:                                                │
│   <think>                                                       │
│   I see the bug! Line 38 uses `< len(items) - 1` which skips    │
│   the last item. It should be `< len(items)` or `<= len - 1`.   │
│   Let me fix it.                                                │
│   </think>                                                      │
│   <tool_call>                                                   │
│   {"name": "str_replace_editor",                                │
│    "arguments": {"command": "str_replace",                      │
│                  "path": "/repo/utils.py",                      │
│                  "old_str": "if i < len(items) - 1:",           │
│                  "new_str": "if i < len(items):"}}              │
│   </tool_call>                                                  │
│                                                                 │
│ YOUR CODE EXECUTES:                                             │
│   → Replaces the string in the file                             │
│   → Returns "Successfully edited"                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ TURN 3                                                          │
├─────────────────────────────────────────────────────────────────┤
│ INPUT TO MODEL:                                                 │
│   ...previous messages...                                       │
│   User: <tool_response>                                         │
│         Successfully edited /repo/utils.py                      │
│         </tool_response>                                        │
│                                                                 │
│ MODEL GENERATES:                                                │
│   <think>                                                       │
│   Fixed! Let me verify by running the tests.                    │
│   </think>                                                      │
│   <tool_call>                                                   │
│   {"name": "bash",                                              │
│    "arguments": {"command": "python -m pytest tests/test_utils.py"}}│
│   </tool_call>                                                  │
│                                                                 │
│ YOUR CODE EXECUTES:                                             │
│   → Runs pytest                                                 │
│   → Returns test results                                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ TURN 4 (Final)                                                  │
├─────────────────────────────────────────────────────────────────┤
│ INPUT TO MODEL:                                                 │
│   User: <tool_response>                                         │
│         ===== 5 passed in 0.3s =====                            │
│         </tool_response>                                        │
│                                                                 │
│ MODEL GENERATES:                                                │
│   The bug has been fixed. The issue was an off-by-one error     │
│   on line 38 where `i < len(items) - 1` excluded the last       │
│   item. Changed to `i < len(items)` and all tests pass.         │
│                                                                 │
│ NO TOOL CALL → Agent finished!                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Summary

| Phase | What Happens |
|-------|--------------|
| **Training** | Model sees full conversations, learns to predict assistant turns (thinking + tool calls) |
| **Inference** | Your harness runs a loop: model generates → you execute tool → feed result back → repeat |
| **Key Insight** | Model only generates text. YOU execute the actual tools and return results. |
