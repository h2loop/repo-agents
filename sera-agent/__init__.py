"""SERA Agent — lightweight inference harness for Nemotron-3-Nano fine-tuned on OAI5G.

This package provides a minimal agent loop that:
  1. Sends conversations to a fine-tuned Nemotron-3-Nano via any OpenAI-compatible API
  2. Parses the model's native <tool_call> XML output
  3. Executes tool calls (bash, str_replace_editor, submit)
  4. Feeds results back and repeats until the model submits a patch

Architecture (4 files, ~540 lines total):
  sera_agent.py  — LLM client, tool executor, agent loop, CLI entrypoint
  tools/parser.py — Nemotron native <tool_call> XML parser
  tools/editor.py — str_replace_editor implementation (view/edit/create/insert/undo)
  tests/test_harness.py — full test suite validated against 27,187 tool calls
"""
