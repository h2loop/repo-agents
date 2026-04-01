#!/usr/bin/env python3
"""Quick test: send a real SERA rollout1-style prompt to GLM-5 via the LiteLLM proxy."""

import json
import sys
import time

import requests

BASE_URL = "https://litellm-prod-909645453767.asia-south1.run.app"
API_KEY = "sk-1234"
MODEL = "vertex_ai/zai-org/glm-5-maas"

SYSTEM_PROMPT = """\
You are an expert C/C++ software engineer working on the OpenAirInterface 5G codebase.
You have access to the following tools to navigate and modify the codebase:

1. **bash** - Execute shell commands. Use for: grep, find, ls, gcc -fsyntax-only, etc.
2. **str_replace_editor** - View and edit files. Commands:
   - view: View file contents (with optional line range)
   - str_replace: Replace a specific string in a file
   - create: Create a new file
   - insert: Insert text at a specific line

The codebase is a 5G telecommunications implementation with PHY, MAC, RLC, PDCP, RRC layers.
Working directory is /repo.

When you are done making your changes, output SUBMIT to indicate you are finished.

Think step by step. First understand the code around the indicated function, then investigate
the potential issue, and finally make a targeted fix."""

USER_PROMPT = """\
There is a buffer overflow vulnerability downstream of function nr_dlsch_encoding in the openair1/PHY subsystem.
The function is located at openair1/PHY/NR_TRANSPORT/nr_dlsch.c:120.
Please investigate and fix this issue."""

messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": USER_PROMPT},
]

payload = {
    "model": MODEL,
    "messages": messages,
    "temperature": 0.7,
    "max_tokens": 4096,
}
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

print(f"Model: {MODEL}")
print(f"Sending SERA-style rollout1 prompt ({len(SYSTEM_PROMPT)+len(USER_PROMPT)} chars)...")
start = time.time()

try:
    resp = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=300,
    )
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} | Latency: {elapsed:.1f}s")

    data = resp.json()
    if resp.status_code != 200:
        print(f"ERROR: {resp.text[:500]}")
        sys.exit(1)

    msg = data["choices"][0]["message"]
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or ""
    finish = data["choices"][0].get("finish_reason", "?")
    usage = data.get("usage", {})

    pt = usage.get("prompt_tokens", "?")
    ct = usage.get("completion_tokens", "?")
    tt = usage.get("total_tokens", "?")
    traffic = usage.get("extra_properties", {}).get("google", {}).get("traffic_type", "?")

    print(f"Finish reason: {finish}")
    print(f"Usage: prompt={pt}, completion={ct}, total={tt}")
    print(f"Traffic type: {traffic}")

    if reasoning:
        print(f"\n--- REASONING ({len(reasoning)} chars) ---")
        print(reasoning[:2000])
        if len(reasoning) > 2000:
            print(f"\n... [truncated, {len(reasoning)} total chars]")

    if content:
        print(f"\n--- RESPONSE ({len(content)} chars) ---")
        print(content[:3000])
        if len(content) > 3000:
            print(f"\n... [truncated, {len(content)} total chars]")

    if not content and not reasoning:
        print("\n--- NO CONTENT OR REASONING ---")
        print(json.dumps(data, indent=2)[:1000])

    # Verdict
    combined = (content + reasoning).lower()
    has_tool_use = any(kw in combined for kw in ["bash", "str_replace", "grep", "find", "view", "cat "])
    has_reasoning = bool(reasoning and len(reasoning) > 50)
    has_content = bool(content and len(content) > 50)

    print(f"\n--- VERDICT ---")
    print(f"  Has reasoning: {has_reasoning}")
    print(f"  Has content:   {has_content}")
    print(f"  Tool-aware:    {has_tool_use}")
    print(f"  SERA-ready:    {has_tool_use and (has_reasoning or has_content)}")

except Exception as e:
    elapsed = time.time() - start
    print(f"EXCEPTION after {elapsed:.1f}s: {e}")
    sys.exit(1)
