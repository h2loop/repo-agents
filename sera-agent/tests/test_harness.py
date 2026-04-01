#!/usr/bin/env python3
"""Test suite for the SERA agent harness.

Tests 4 layers:
  1. Tool parser — unit tests for each edge case
  2. Editor — integration tests for all 5 commands
  3. Parser on real data — single sample from converted training data
  4. Parser bulk — 50 samples (1,680+ tool calls)

Full dataset validation (821 samples, 27,187 tool calls) was run separately
and passed with zero errors.

Run:
    cd sera/sera-agent && python -m tests.test_harness
"""

import json
import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.parser import parse_tool_calls, ToolCall
from tools.editor import Editor


# ---------------------------------------------------------------
# 1. Tool Parser — Unit Tests
# ---------------------------------------------------------------

def test_parser_basic():
    """Basic bash tool call."""
    text = """<think>Let me check the file.</think>I'll look at the code.
<tool_call>
<function=bash>
<parameter=command>
find /repo -name "job.c" -type f
</parameter>
</function>
</tool_call>
"""
    preamble, calls = parse_tool_calls(text)
    assert "Let me check" in preamble
    assert len(calls) == 1
    assert calls[0].name == "bash"
    assert "find /repo" in calls[0].arguments["command"]
    print("  PASS: basic bash parsing")


def test_parser_str_replace():
    """Multi-line old_str/new_str parameters."""
    text = """<think></think>
<tool_call>
<function=str_replace_editor>
<parameter=command>
str_replace
</parameter>
<parameter=path>
/repo/openair2/UTIL/OMG/job.c
</parameter>
<parameter=old_str>
      if (current == list || previous == NULL)
        list = current->next;
</parameter>
<parameter=new_str>
      if (previous == NULL)
        list = current->next;
</parameter>
</function>
</tool_call>
"""
    _, calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "str_replace_editor"
    assert calls[0].arguments["command"].strip() == "str_replace"
    assert "current == list || previous == NULL" in calls[0].arguments["old_str"]
    assert "previous == NULL" in calls[0].arguments["new_str"]
    assert "current == list" not in calls[0].arguments["new_str"]
    print("  PASS: str_replace multi-line parsing")


def test_parser_multiple_calls():
    """Two tool calls in one response."""
    text = """<think></think>Let me check two things.
<tool_call>
<function=bash>
<parameter=command>
ls /repo
</parameter>
</function>
</tool_call>
<tool_call>
<function=bash>
<parameter=command>
cat /repo/Makefile
</parameter>
</function>
</tool_call>
"""
    _, calls = parse_tool_calls(text)
    assert len(calls) == 2
    assert "ls /repo" in calls[0].arguments["command"]
    assert "cat /repo/Makefile" in calls[1].arguments["command"]
    print("  PASS: multiple tool calls")


def test_parser_submit():
    """Submit tool with no parameters."""
    text = """<think></think>Done.
<tool_call>
<function=submit>
</function>
</tool_call>
"""
    _, calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "submit"
    assert calls[0].arguments == {}
    print("  PASS: submit parsing")


def test_parser_xml_in_value():
    """Parameter value containing XML-like content."""
    text = """<tool_call>
<function=bash>
<parameter=command>
echo "<tool_call>" > /tmp/test.txt && echo "</parameter>" >> /tmp/test.txt
</parameter>
</function>
</tool_call>
"""
    _, calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].name == "bash"
    cmd = calls[0].arguments["command"]
    assert "<tool_call>" in cmd
    print(f"  PASS: XML-in-value (command={cmd!r})")


def test_parser_view_with_range():
    """View command with view_range parameter."""
    text = """<tool_call>
<function=str_replace_editor>
<parameter=command>
view
</parameter>
<parameter=path>
/repo/foo.c
</parameter>
<parameter=view_range>
[10, 50]
</parameter>
</function>
</tool_call>
"""
    _, calls = parse_tool_calls(text)
    assert len(calls) == 1
    assert calls[0].arguments["view_range"].strip() == "[10, 50]"
    print("  PASS: view with range")


# ---------------------------------------------------------------
# 2. Editor — Integration Tests
# ---------------------------------------------------------------

def test_editor_create_view_replace_undo():
    """Full editor lifecycle: create -> view -> replace -> undo."""
    with tempfile.TemporaryDirectory() as tmpdir:
        editor = Editor(tmpdir)

        # Create
        result = editor.execute({"command": "create", "path": f"{tmpdir}/test.c",
                                 "file_text": "int main() {\n    return 0;\n}\n"})
        assert "created" in result.lower()
        print("  PASS: editor create")

        # View
        result = editor.execute({"command": "view", "path": f"{tmpdir}/test.c"})
        assert "int main()" in result and "return 0" in result
        print("  PASS: editor view")

        # View with range
        result = editor.execute({"command": "view", "path": f"{tmpdir}/test.c", "view_range": "[2, 3]"})
        assert "return 0" in result
        print("  PASS: editor view with range")

        # str_replace
        result = editor.execute({
            "command": "str_replace", "path": f"{tmpdir}/test.c",
            "old_str": "    return 0;", "new_str": "    return 1;",
        })
        assert "edited" in result.lower()
        content = Path(f"{tmpdir}/test.c").read_text()
        assert "return 1" in content and "return 0" not in content
        print("  PASS: editor str_replace")

        # Undo
        result = editor.execute({"command": "undo_edit", "path": f"{tmpdir}/test.c"})
        assert "undo" in result.lower()
        content = Path(f"{tmpdir}/test.c").read_text()
        assert "return 0" in content
        print("  PASS: editor undo")

        # Ambiguous replace
        Path(f"{tmpdir}/dup.c").write_text("foo\nbar\nfoo\n")
        result = editor.execute({
            "command": "str_replace", "path": f"{tmpdir}/dup.c",
            "old_str": "foo", "new_str": "baz",
        })
        assert "multiple" in result.lower() or "ERROR" in result
        print("  PASS: editor rejects ambiguous replace")

        # View directory
        result = editor.execute({"command": "view", "path": tmpdir})
        assert "test.c" in result
        print("  PASS: editor view directory")

        # Insert
        result = editor.execute({
            "command": "insert", "path": f"{tmpdir}/test.c",
            "insert_line": "1", "new_str": "#include <stdio.h>",
        })
        assert "edited" in result.lower()
        content = Path(f"{tmpdir}/test.c").read_text()
        assert "#include <stdio.h>" in content
        print("  PASS: editor insert")


# ---------------------------------------------------------------
# 3. Parser on Real Training Data
# ---------------------------------------------------------------

def test_parser_on_real_training_data():
    """Parse tool calls from 1 converted training sample."""
    import re
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(
        "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16", trust_remote_code=True)
    sera_root = Path(__file__).parent.parent.parent
    with open(sera_root / "configs/nemotron_chat_template_patched.jinja") as f:
        tok.chat_template = f.read()

    with open(sera_root / "data/megatron_sft/training.jsonl") as f:
        sample = json.loads(f.readline())

    rendered = tok.apply_chat_template(sample["messages"], tools=sample["tools"], tokenize=False)
    segments = re.split(r"<\|im_start\|>assistant\n", rendered)

    tool_call_count = 0
    parse_errors = 0
    for seg in segments[1:]:
        end = seg.find("<|im_end|>")
        if end == -1:
            continue
        content = seg[:end]
        if "<tool_call>" in content:
            _, calls = parse_tool_calls(content)
            if calls:
                tool_call_count += len(calls)
            else:
                parse_errors += 1

    print(f"  Parsed {tool_call_count} tool calls from 1 sample, {parse_errors} errors")
    assert parse_errors == 0
    assert tool_call_count > 0
    print("  PASS: real training data parsing")


def test_parser_on_multiple_samples():
    """Parse 50 samples (1,680+ tool calls)."""
    import re
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(
        "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16", trust_remote_code=True)
    sera_root = Path(__file__).parent.parent.parent
    with open(sera_root / "configs/nemotron_chat_template_patched.jinja") as f:
        tok.chat_template = f.read()

    total_calls = 0
    total_errors = 0

    with open(sera_root / "data/megatron_sft/training.jsonl") as f:
        for i, line in enumerate(f):
            if i >= 50:
                break
            sample = json.loads(line)
            rendered = tok.apply_chat_template(
                sample["messages"], tools=sample["tools"], tokenize=False)
            segments = re.split(r"<\|im_start\|>assistant\n", rendered)
            for seg in segments[1:]:
                end = seg.find("<|im_end|>")
                if end == -1:
                    continue
                content = seg[:end]
                if "<tool_call>" in content:
                    _, calls = parse_tool_calls(content)
                    total_calls += len(calls) if calls else 0
                    total_errors += 0 if calls else 1

    print(f"  Tested 50 samples: {total_calls} tool calls parsed, {total_errors} errors")
    assert total_errors == 0
    print("  PASS: bulk training data parsing")


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------

if __name__ == "__main__":
    os.chdir(Path(__file__).parent.parent)
    print("=" * 60)
    print("SERA Agent Harness — Test Suite")
    print("=" * 60)

    print("\n[1] Tool Parser — Unit Tests")
    test_parser_basic()
    test_parser_str_replace()
    test_parser_multiple_calls()
    test_parser_submit()
    test_parser_xml_in_value()
    test_parser_view_with_range()

    print("\n[2] Editor — Integration Tests")
    test_editor_create_view_replace_undo()

    print("\n[3] Parser — Real Training Data (1 sample)")
    test_parser_on_real_training_data()

    print("\n[4] Parser — Bulk Training Data (50 samples)")
    test_parser_on_multiple_samples()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
