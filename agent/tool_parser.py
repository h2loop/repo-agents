"""Parse Nemotron-native <tool_call> XML from model output.

Handles:
- Multiple tool calls in one response
- Multi-line parameter values
- Parameter values containing XML-like content (e.g., echo "<tool_call>")
- Partial/malformed output (returns what it can parse)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, str] = field(default_factory=dict)


def parse_tool_calls(text: str) -> tuple[str, list[ToolCall]]:
    """Parse tool calls from model output text.

    Returns:
        (thinking_and_text, list_of_tool_calls)
        thinking_and_text is everything before the first <tool_call>.
    """
    calls: list[ToolCall] = []

    # In Nemotron's format, <tool_call> always starts at the beginning of a line
    # (or at the very start of the text). This avoids splitting on <tool_call>
    # that appears inside parameter values (e.g., echo "<tool_call>").
    parts = re.split(r"(?:^|\n)<tool_call>\s*\n?", text)
    preamble = parts[0]  # text before first tool_call

    for raw_block in parts[1:]:
        # Remove trailing </tool_call> — also must be on its own line
        block = re.sub(r"\n?</tool_call>\s*$", "", raw_block, count=1)
        call = _parse_single_call(block)
        if call is not None:
            calls.append(call)

    return preamble.strip(), calls


def _parse_single_call(block: str) -> ToolCall | None:
    """Parse a single tool call block (content between <tool_call> and </tool_call>)."""
    # Extract function name: <function=name>
    func_match = re.match(r"\s*<function=([^>]+)>", block)
    if not func_match:
        return None

    name = func_match.group(1).strip()

    # Extract everything between <function=name> and </function>
    func_body_start = func_match.end()
    func_end = block.rfind("</function>")
    if func_end == -1:
        # Malformed — use everything after the function tag
        func_body = block[func_body_start:]
    else:
        func_body = block[func_body_start:func_end]

    # Parse parameters: <parameter=key>\nvalue\n</parameter>
    arguments = _parse_parameters(func_body)

    return ToolCall(name=name, arguments=arguments)


def _parse_parameters(body: str) -> dict[str, str]:
    """Parse <parameter=key>value</parameter> pairs from function body.

    In Nemotron's format, the closing </parameter> always appears on its own
    line (starts after a newline). This distinguishes it from </parameter> that
    may appear inline within a parameter value (e.g., echo "</parameter>").
    """
    params: dict[str, str] = {}
    pos = 0

    while pos < len(body):
        # Find next <parameter=key>
        param_match = re.search(r"<parameter=([^>]+)>\n?", body[pos:])
        if not param_match:
            break

        key = param_match.group(1).strip()
        value_start = pos + param_match.end()

        rest = body[value_start:]

        # Find </parameter> that starts at the beginning of a line (\n</parameter>)
        # This is the real closing tag. Inline occurrences are part of the value.
        close_positions = [m.start() for m in re.finditer(r"\n</parameter>\n?", rest)]

        if not close_positions:
            # Fallback: look for </parameter> anywhere (handles single-line values
            # where value + closing tag are on one line: "value</parameter>")
            fallback = re.search(r"</parameter>", rest)
            if fallback:
                value = rest[: fallback.start()]
                pos = value_start + fallback.end()
            else:
                value = rest.strip()
                pos = len(body)
        else:
            # Pick the first \n</parameter> after the value starts
            # (for multi-param blocks, this is the closest closing tag)
            next_param = re.search(r"\n<parameter=", rest)
            if next_param:
                valid = [p for p in close_positions if p < next_param.start()]
                close_pos = valid[0] if valid else close_positions[0]
            else:
                close_pos = close_positions[0]

            value = rest[:close_pos]
            close_tag_match = re.match(r"\n</parameter>\n?", rest[close_pos:])
            pos = (
                value_start
                + close_pos
                + (close_tag_match.end() if close_tag_match else len("\n</parameter>"))
            )

        # Strip single leading/trailing newline from value
        value = value.strip("\n")
        params[key] = value

    return params
