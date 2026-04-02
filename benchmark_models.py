#!/usr/bin/env python3
"""Benchmark GCP MaaS models: latency, throughput, and quality."""

import json
import time
import statistics
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

BASE_URL = "https://litellm-prod-909645453767.asia-south1.run.app"
API_KEY = "sk-1234"

MODELS = {
    "Kimi K2 Thinking": "moonshotai/kimi-k2-thinking-maas",
    "DeepSeek v3.2": "deepseek-ai/deepseek-v3.2-maas",
    "Qwen3 Coder 480B": "qwen/qwen3-coder-480b-a35b-instruct-maas",
}

# ---------------------------------------------------------------------------
# Benchmark prompts — mix of coding, reasoning, and generation tasks
# ---------------------------------------------------------------------------
PROMPTS = [
    {
        "name": "Code: FizzBuzz",
        "category": "coding",
        "messages": [{"role": "user", "content": "Write a Python function for FizzBuzz that takes n and returns a list of strings. Just the code, no explanation."}],
        "max_tokens": 300,
    },
    {
        "name": "Code: Binary Search Bug",
        "category": "coding",
        "messages": [{"role": "user", "content": "Find and fix the bug in this code:\n```python\ndef binary_search(arr, target):\n    lo, hi = 0, len(arr)\n    while lo < hi:\n        mid = (lo + hi) / 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return -1\n```\nReturn only the corrected function."}],
        "max_tokens": 300,
    },
    {
        "name": "Code: Regex Parser",
        "category": "coding",
        "messages": [{"role": "user", "content": "Write a Python function that extracts all email addresses from a given string using regex. Return a list. Just the code."}],
        "max_tokens": 200,
    },
    {
        "name": "Reasoning: Math",
        "category": "reasoning",
        "messages": [{"role": "user", "content": "A train leaves station A at 60 km/h. Another train leaves station B (300 km away) at the same time at 90 km/h toward A. When and where do they meet? Show your work briefly."}],
        "max_tokens": 300,
    },
    {
        "name": "Reasoning: Logic Puzzle",
        "category": "reasoning",
        "messages": [{"role": "user", "content": "Three boxes are labeled Apples, Oranges, and Mixed. All labels are wrong. You pick one fruit from one box. What's the minimum picks needed to correctly label all boxes, and which box do you pick from? Explain briefly."}],
        "max_tokens": 300,
    },
    {
        "name": "Generation: Summarize",
        "category": "generation",
        "messages": [{"role": "user", "content": "Summarize the concept of transformer attention mechanism in exactly 3 sentences for a software engineer who hasn't done ML."}],
        "max_tokens": 200,
    },
    {
        "name": "Generation: Explain Like I'm 5",
        "category": "generation",
        "messages": [{"role": "user", "content": "Explain what a compiler does, like I'm 5 years old. Keep it under 50 words."}],
        "max_tokens": 150,
    },
    {
        "name": "Code: SQL Query",
        "category": "coding",
        "messages": [{"role": "user", "content": "Write a SQL query to find the top 3 customers by total order amount from tables `customers(id, name)` and `orders(id, customer_id, amount)`. Just the query."}],
        "max_tokens": 200,
    },
]


def call_model(model_id: str, messages: list, max_tokens: int, temperature: float = 0.3) -> dict:
    """Call a model and return timing + response metadata."""
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    start = time.perf_counter()
    try:
        resp = requests.post(f"{BASE_URL}/v1/chat/completions", headers=headers, json=payload, timeout=120)
        elapsed = time.perf_counter() - start
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        content = data["choices"][0]["message"].get("content", "") or ""
        reasoning = data["choices"][0]["message"].get("reasoning_content", "")
        return {
            "success": True,
            "latency": elapsed,
            "content": content,
            "reasoning": reasoning or None,
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "tok_per_sec": usage.get("completion_tokens", 0) / elapsed if elapsed > 0 else 0,
            "finish_reason": data["choices"][0].get("finish_reason", "unknown"),
        }
    except Exception as e:
        elapsed = time.perf_counter() - start
        return {"success": False, "latency": elapsed, "error": str(e)}


def run_benchmark():
    """Run all prompts against all models and collect results."""
    results = {}
    total = len(MODELS) * len(PROMPTS)
    done = 0

    for model_name, model_id in MODELS.items():
        results[model_name] = []
        print(f"\n{'='*60}")
        print(f"  {model_name} ({model_id})")
        print(f"{'='*60}")

        for prompt in PROMPTS:
            done += 1
            print(f"  [{done}/{total}] {prompt['name']}...", end=" ", flush=True)
            result = call_model(model_id, prompt["messages"], prompt["max_tokens"])
            result["prompt_name"] = prompt["name"]
            result["category"] = prompt["category"]
            results[model_name].append(result)

            if result["success"]:
                print(f"{result['latency']:.2f}s | {result['completion_tokens']}tok | {result['tok_per_sec']:.1f}tok/s")
            else:
                print(f"FAILED: {result['error'][:80]}")

    return results


def print_summary(results: dict):
    """Print a summary table."""
    print(f"\n\n{'='*80}")
    print(f"  BENCHMARK SUMMARY")
    print(f"{'='*80}\n")

    header = f"{'Metric':<30}"
    for name in results:
        header += f" | {name:>20}"
    print(header)
    print("-" * len(header))

    # Aggregate stats
    for model_name, runs in results.items():
        runs_ok = [r for r in runs if r["success"]]
        if not runs_ok:
            continue

    # Success rate
    row = f"{'Success Rate':<30}"
    for model_name, runs in results.items():
        ok = sum(1 for r in runs if r["success"])
        row += f" | {ok}/{len(runs):>17}"
    print(row)

    # Avg latency
    row = f"{'Avg Latency (s)':<30}"
    for model_name, runs in results.items():
        lats = [r["latency"] for r in runs if r["success"]]
        row += f" | {statistics.mean(lats):>19.2f}s" if lats else f" | {'N/A':>20}"
    print(row)

    # Median latency
    row = f"{'Median Latency (s)':<30}"
    for model_name, runs in results.items():
        lats = [r["latency"] for r in runs if r["success"]]
        row += f" | {statistics.median(lats):>19.2f}s" if lats else f" | {'N/A':>20}"
    print(row)

    # P95 latency
    row = f"{'P95 Latency (s)':<30}"
    for model_name, runs in results.items():
        lats = sorted([r["latency"] for r in runs if r["success"]])
        if lats:
            p95 = lats[int(len(lats) * 0.95)]
            row += f" | {p95:>19.2f}s"
        else:
            row += f" | {'N/A':>20}"
    print(row)

    # Avg tok/s
    row = f"{'Avg Throughput (tok/s)':<30}"
    for model_name, runs in results.items():
        tps = [r["tok_per_sec"] for r in runs if r["success"]]
        row += f" | {statistics.mean(tps):>19.1f}" if tps else f" | {'N/A':>20}"
    print(row)

    # Avg completion tokens
    row = f"{'Avg Completion Tokens':<30}"
    for model_name, runs in results.items():
        toks = [r["completion_tokens"] for r in runs if r["success"]]
        row += f" | {statistics.mean(toks):>19.1f}" if toks else f" | {'N/A':>20}"
    print(row)

    # Total tokens
    row = f"{'Total Tokens Used':<30}"
    for model_name, runs in results.items():
        tot = sum(r["total_tokens"] for r in runs if r["success"])
        row += f" | {tot:>20,}"
    print(row)

    # Per-category breakdown
    categories = sorted(set(p["category"] for p in PROMPTS))
    print(f"\n{'--- Per-Category Avg Latency ---':^{len(header)}}")
    for cat in categories:
        row = f"  {cat.capitalize():<28}"
        for model_name, runs in results.items():
            lats = [r["latency"] for r in runs if r["success"] and r["category"] == cat]
            row += f" | {statistics.mean(lats):>19.2f}s" if lats else f" | {'N/A':>20}"
        print(row)

    print(f"\n{'--- Per-Category Avg tok/s ---':^{len(header)}}")
    for cat in categories:
        row = f"  {cat.capitalize():<28}"
        for model_name, runs in results.items():
            tps = [r["tok_per_sec"] for r in runs if r["success"] and r["category"] == cat]
            row += f" | {statistics.mean(tps):>19.1f}" if tps else f" | {'N/A':>20}"
        print(row)

    # Per-prompt detail
    print(f"\n\n{'='*80}")
    print(f"  PER-PROMPT DETAIL")
    print(f"{'='*80}\n")

    for prompt in PROMPTS:
        print(f"  {prompt['name']} [{prompt['category']}]")
        for model_name, runs in results.items():
            r = next((x for x in runs if x["prompt_name"] == prompt["name"]), None)
            if r and r["success"]:
                print(f"    {model_name:<22} {r['latency']:>7.2f}s  {r['completion_tokens']:>4}tok  {r['tok_per_sec']:>6.1f}tok/s  [{r['finish_reason']}]")
                # Print first 120 chars of response
                preview = (r["content"] or "").replace("\n", " ")[:120]
                print(f"      → {preview}...")
            elif r:
                print(f"    {model_name:<22} FAILED: {r.get('error', 'unknown')[:60]}")
        print()


if __name__ == "__main__":
    print(f"Benchmark started at {datetime.now().isoformat()}")
    print(f"Endpoint: {BASE_URL}")
    print(f"Models: {list(MODELS.keys())}")
    print(f"Prompts: {len(PROMPTS)}")

    results = run_benchmark()

    print_summary(results)

    # Save raw results
    out_path = "/Users/metamyth/projects/sera/benchmark_results.json"
    serializable = {}
    for model_name, runs in results.items():
        serializable[model_name] = runs
    with open(out_path, "w") as f:
        json.dump(serializable, f, indent=2, default=str)
    print(f"\nRaw results saved to {out_path}")
    print(f"Benchmark finished at {datetime.now().isoformat()}")
