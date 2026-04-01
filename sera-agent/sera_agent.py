#!/usr/bin/env python3
"""SERA Agent — lightweight inference harness for Nemotron-3-Nano fine-tuned on OAI5G.

This is the main entrypoint. It implements:
  - LLMClient: minimal OpenAI-compatible API client (works with vLLM, TGI, etc.)
  - ToolExecutor: dispatches parsed tool calls to bash/editor/submit
  - SeraAgent: the agentic loop (generate -> parse -> execute -> repeat)

The agent uses the same 3 tools from SERA training data:
  - bash: execute shell commands via subprocess
  - str_replace_editor: view/edit/create files (see tools/editor.py)
  - submit: capture git diff as final patch and stop

Usage:
    # Start vLLM with your fine-tuned model
    vllm serve ./merged_checkpoint --port 8000

    # Run the agent
    python -m sera-agent.sera_agent \\
        --model-url http://localhost:8000/v1 \\
        --model-name nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16 \\
        --repo /path/to/oai5g/repo \\
        --issue "Fix the memory leak in remove_job() in job.c"

    # Or read issue from file
    python -m sera-agent.sera_agent \\
        --model-url http://localhost:8000/v1 \\
        --repo /path/to/repo \\
        --issue-file issue.txt \\
        --output trajectory.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

from tools.parser import ToolCall, parse_tool_calls
from tools.editor import Editor


# ---------------------------------------------------------------------------
# Tool schemas — identical to training data (passed to chat template)
# ---------------------------------------------------------------------------
TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "bash", "description": "Execute a bash command in the repository environment", "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "The bash command to execute"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "str_replace_editor", "description": "View, create, or edit files. Commands: view, str_replace, create, insert, undo_edit", "parameters": {"type": "object", "properties": {"command": {"type": "string"}, "path": {"type": "string"}, "old_str": {"type": "string"}, "new_str": {"type": "string"}, "file_text": {"type": "string"}, "insert_line": {"type": "integer"}, "view_range": {"type": "array", "items": {"type": "integer"}}}, "required": ["command", "path"]}}},
    {"type": "function", "function": {"name": "submit", "description": "Submit the current changes as the final patch", "parameters": {"type": "object", "properties": {}}}},
]

SYSTEM_PROMPT = (
    "You are an expert C/C++ software engineer working on the OpenAirInterface 5G codebase.\n"
    "You can interact with the codebase using bash commands and a file editor to investigate and fix issues."
)


# ---------------------------------------------------------------------------
# LLM Client (OpenAI-compatible — works with vLLM, TGI, OpenAI, etc.)
# ---------------------------------------------------------------------------

class LLMClient:
    """Minimal client for OpenAI-compatible chat completions API.

    Sends messages + tool schemas, receives raw text content.
    Handles both cases: model returns tool calls as XML in content
    (our fine-tuned model) or as native tool_calls (server-side parsing).
    """

    def __init__(self, base_url: str, model_name: str, api_key: str = "EMPTY",
                 max_tokens: int = 4096, temperature: float = 0.0):
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.temperature = temperature

    def generate(self, messages: list[dict], tools: list[dict] | None = None) -> str:
        """Send chat completion request, return raw assistant content string."""
        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=300,
        )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        message = choice["message"]

        # Handle case where vLLM parses tool calls server-side
        # (reconstruct XML so our parser handles it uniformly)
        if message.get("tool_calls"):
            content = message.get("content") or ""
            for tc in message["tool_calls"]:
                func = tc["function"]
                args = func.get("arguments", "{}")
                if isinstance(args, str):
                    args = json.loads(args)
                content += f"\n<tool_call>\n<function={func['name']}>\n"
                for k, v in args.items():
                    content += f"<parameter={k}>\n{v}\n</parameter>\n"
                content += "</function>\n</tool_call>\n"
            return content

        return message.get("content") or ""


# ---------------------------------------------------------------------------
# Tool Executor
# ---------------------------------------------------------------------------

class ToolExecutor:
    """Dispatches parsed ToolCall objects to the appropriate handler.

    Supports:
      bash             — subprocess.run with timeout and output truncation
      str_replace_editor — Editor instance (view/str_replace/create/insert/undo)
      submit           — captures git diff as the final patch
    """

    def __init__(self, working_dir: str, timeout: int = 60):
        self.working_dir = working_dir
        self.timeout = timeout
        self.editor = Editor(working_dir)

    def execute(self, call: ToolCall) -> str:
        """Execute a single tool call, return output string."""
        if call.name == "bash":
            return self._exec_bash(call.arguments.get("command", ""))
        elif call.name == "str_replace_editor":
            return self.editor.execute(call.arguments)
        elif call.name == "submit":
            return self._exec_submit()
        else:
            return f"ERROR: Unknown tool '{call.name}'"

    def _exec_bash(self, command: str) -> str:
        """Execute a bash command with timeout and output truncation."""
        if not command.strip():
            return "ERROR: empty command"
        try:
            result = subprocess.run(
                command,
                shell=True,
                text=True,
                cwd=self.working_dir,
                timeout=self.timeout,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                errors="replace",
            )
            output = result.stdout
            if len(output) > 50_000:
                output = output[:25_000] + "\n\n... [output truncated] ...\n\n" + output[-25_000:]
            return output
        except subprocess.TimeoutExpired:
            return f"ERROR: Command timed out after {self.timeout}s"
        except Exception as e:
            return f"ERROR: {e}"

    def _exec_submit(self) -> str:
        """Capture git diff as the final patch."""
        try:
            result = subprocess.run(
                "git diff",
                shell=True, text=True,
                cwd=self.working_dir,
                timeout=10,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            diff = result.stdout.strip()
            if diff:
                return f"Submission accepted. Diff:\n{diff}"
            else:
                return "WARNING: No changes detected (git diff is empty)."
        except Exception as e:
            return f"ERROR capturing diff: {e}"


# ---------------------------------------------------------------------------
# Agent Loop
# ---------------------------------------------------------------------------

class SeraAgent:
    """Agentic loop: generate -> parse tool calls -> execute -> append result -> repeat.

    Stops when the model calls submit or max_steps is reached.
    """

    def __init__(self, llm: LLMClient, executor: ToolExecutor, *,
                 max_steps: int = 30, verbose: bool = True):
        self.llm = llm
        self.executor = executor
        self.max_steps = max_steps
        self.verbose = verbose
        self.messages: list[dict] = []
        self.trajectory: list[dict] = []

    def run(self, issue_text: str) -> dict:
        """Run the agent on an issue. Returns {patch, steps, status}."""
        self.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": self._format_issue(issue_text)},
        ]
        self.trajectory = []

        patch = ""
        status = "max_steps_reached"

        for step in range(1, self.max_steps + 1):
            if self.verbose:
                print(f"\n{'='*60}")
                print(f"  Step {step}/{self.max_steps}")
                print(f"{'='*60}")

            # 1. Query LLM
            t0 = time.time()
            raw_output = self.llm.generate(self.messages, tools=TOOL_SCHEMAS)
            gen_time = time.time() - t0

            if self.verbose:
                print(f"[LLM response in {gen_time:.1f}s, {len(raw_output)} chars]")

            # 2. Parse tool calls from model output
            preamble, calls = parse_tool_calls(raw_output)

            if self.verbose and preamble:
                display = preamble if len(preamble) < 500 else preamble[:250] + "..." + preamble[-250:]
                print(f"  Text: {display}")

            if not calls:
                self.messages.append({"role": "assistant", "content": raw_output})
                self.trajectory.append({"step": step, "type": "no_tool_call", "content": raw_output})
                if self.verbose:
                    print("  [No tool call in response]")
                continue

            # 3. Add assistant message with tool_calls for chat template
            tool_calls_for_msg = []
            for call in calls:
                tool_calls_for_msg.append({
                    "type": "function",
                    "function": {"name": call.name, "arguments": call.arguments},
                })
            self.messages.append({
                "role": "assistant",
                "content": preamble if preamble else None,
                "tool_calls": tool_calls_for_msg,
            })

            # 4. Execute each tool call and append results
            submitted = False
            for call in calls:
                if self.verbose:
                    args_preview = str(call.arguments)
                    if len(args_preview) > 200:
                        args_preview = args_preview[:200] + "..."
                    print(f"  Tool: {call.name}({args_preview})")

                output = self.executor.execute(call)

                if self.verbose:
                    display = output if len(output) < 300 else output[:150] + "..." + output[-150:]
                    print(f"  Result: {display}")

                self.messages.append({"role": "tool", "content": output})
                self.trajectory.append({
                    "step": step,
                    "type": "tool_call",
                    "tool": call.name,
                    "arguments": call.arguments,
                    "output": output[:5000],
                })

                if call.name == "submit":
                    patch = self._extract_patch()
                    status = "submitted"
                    submitted = True
                    break

            if submitted:
                break

        result = {
            "status": status,
            "patch": patch,
            "steps": len(self.trajectory),
            "messages": len(self.messages),
        }

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"  Agent finished: {status} ({result['steps']} steps)")
            if patch:
                print(f"  Patch: {len(patch)} chars, {patch.count(chr(10))} lines")
            print(f"{'='*60}")

        return result

    def _format_issue(self, issue_text: str) -> str:
        """Format the issue text into the prompt template matching training data."""
        return (
            f"<uploaded_files>\n{self.executor.working_dir}\n</uploaded_files>\n"
            f"I've uploaded the OpenAirInterface 5G C/C++ codebase in the directory "
            f"{self.executor.working_dir}. Consider the following issue:\n\n"
            f"<pr_description>\n{issue_text}\n</pr_description>\n\n"
            f"Can you help me implement the necessary changes to the codebase so that "
            f"the issue described in the <pr_description> is fixed?\n"
            f"Your task is to make the minimal changes to source files in the "
            f"{self.executor.working_dir} directory to ensure the <pr_description> is satisfied.\n"
            f"Follow these steps to resolve the issue:\n"
            f"1. Find and read code relevant to the <pr_description>\n"
            f"2. Investigate the issue by exploring the relevant code paths\n"
            f"3. Edit the source code to resolve the issue\n"
            f"4. Verify your changes make sense\n"
            f"Your thinking should be thorough and so it's fine if it's very long."
        )

    def _extract_patch(self) -> str:
        """Get the current git diff from the working directory."""
        try:
            result = subprocess.run(
                "git diff",
                shell=True, text=True,
                cwd=self.executor.working_dir,
                timeout=10,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def save_trajectory(self, path: str) -> None:
        """Save the full conversation and trajectory to a JSON file."""
        data = {
            "messages": self.messages,
            "trajectory": self.trajectory,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="SERA Agent — run the fine-tuned Nemotron model on OAI5G bug-fixing tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m sera-agent.sera_agent --repo /repo --issue "Fix the null pointer in rrc.c"
  python -m sera-agent.sera_agent --repo /repo --issue-file bug.txt --output traj.json
  python -m sera-agent.sera_agent --model-url http://gpu-server:8000/v1 --repo /repo --issue "..."
        """,
    )
    parser.add_argument("--model-url", default="http://localhost:8000/v1",
                        help="vLLM / OpenAI-compatible API base URL (default: http://localhost:8000/v1)")
    parser.add_argument("--model-name", default="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16",
                        help="Model name for API requests")
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY", "EMPTY"),
                        help="API key (default: EMPTY for local vLLM)")
    parser.add_argument("--repo", required=True,
                        help="Path to the git repository to work on")
    parser.add_argument("--issue", default="",
                        help="Issue/bug description text")
    parser.add_argument("--issue-file",
                        help="Read issue text from file (overrides --issue)")
    parser.add_argument("--max-steps", type=int, default=30,
                        help="Maximum agent steps before stopping (default: 30)")
    parser.add_argument("--max-tokens", type=int, default=4096,
                        help="Max tokens per LLM generation (default: 4096)")
    parser.add_argument("--temperature", type=float, default=0.0,
                        help="Sampling temperature (default: 0.0 = greedy)")
    parser.add_argument("--timeout", type=int, default=60,
                        help="Bash command timeout in seconds (default: 60)")
    parser.add_argument("--output",
                        help="Save full trajectory JSON to this path")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress step-by-step output")
    args = parser.parse_args()

    issue_text = args.issue
    if args.issue_file:
        issue_text = Path(args.issue_file).read_text()
    if not issue_text.strip():
        parser.error("Provide --issue or --issue-file")

    llm = LLMClient(
        base_url=args.model_url,
        model_name=args.model_name,
        api_key=args.api_key,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )
    executor = ToolExecutor(working_dir=args.repo, timeout=args.timeout)
    agent = SeraAgent(llm, executor, max_steps=args.max_steps, verbose=not args.quiet)

    result = agent.run(issue_text)

    if args.output:
        agent.save_trajectory(args.output)
        print(f"Trajectory saved to {args.output}")

    if result["patch"]:
        print("\n--- PATCH ---")
        print(result["patch"])

    sys.exit(0 if result["status"] == "submitted" else 1)


if __name__ == "__main__":
    main()
