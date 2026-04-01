#!/usr/bin/env python3
"""
Ping a model via the LiteLLM proxy to verify connectivity and availability.

Usage:
    # Ping default model (from LLM_MODEL env var)
    python scripts/ping_model.py

    # Ping a specific model
    python scripts/ping_model.py --model glm/glm-5-maas

    # Ping multiple models
    python scripts/ping_model.py --model glm/glm-5-maas moonshotai/kimi-k2-thinking-maas

Environment variables:
    LLM_BASE_URL  - LiteLLM proxy URL
    LLM_API_KEY   - API key
    LLM_MODEL     - Default model ID (used when --model is not specified)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import requests

BASE_URL = os.getenv("LLM_BASE_URL", "https://litellm-prod-909645453767.asia-south1.run.app")
API_KEY = os.getenv("LLM_API_KEY", "sk-1234")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "vertex_ai/zai-org/glm-5-maas")


def ping_model(model: str, base_url: str = BASE_URL, api_key: str = API_KEY) -> dict:
    """Send a minimal chat completion request to verify model availability.

    Returns a dict with status, latency, model info, and any error details.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say 'pong' and nothing else."}],
        "temperature": 0.0,
        "max_tokens": 16,
    }

    start = time.time()
    try:
        resp = requests.post(
            f"{base_url}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=180,
        )
        latency = time.time() - start

        if resp.status_code == 200:
            data = resp.json()
            msg = data.get("choices", [{}])[0].get("message", {})
            content = (msg.get("content") or msg.get("reasoning_content") or "").strip()
            return {
                "model": model,
                "status": "ok",
                "latency_s": round(latency, 2),
                "response": content,
                "usage": data.get("usage"),
            }
        else:
            return {
                "model": model,
                "status": "error",
                "latency_s": round(latency, 2),
                "http_status": resp.status_code,
                "error": resp.text[:500],
            }

    except requests.exceptions.Timeout:
        return {
            "model": model,
            "status": "timeout",
            "latency_s": round(time.time() - start, 2),
            "error": "Request timed out after 180s",
        }
    except requests.exceptions.ConnectionError as e:
        return {
            "model": model,
            "status": "connection_error",
            "latency_s": round(time.time() - start, 2),
            "error": str(e)[:300],
        }
    except Exception as e:
        return {
            "model": model,
            "status": "error",
            "latency_s": round(time.time() - start, 2),
            "error": str(e)[:300],
        }


def main():
    parser = argparse.ArgumentParser(description="Ping model(s) via LiteLLM proxy")
    parser.add_argument(
        "--model", nargs="*", default=None,
        help="Model ID(s) to ping (default: LLM_MODEL env var)",
    )
    parser.add_argument("--base-url", default=BASE_URL, help="LiteLLM proxy base URL")
    parser.add_argument("--api-key", default=API_KEY, help="API key")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    models = args.model if args.model else [DEFAULT_MODEL]

    results = []
    for model in models:
        print(f"Pinging {model} ...", end=" ", flush=True, file=sys.stderr)
        result = ping_model(model, args.base_url, args.api_key)
        results.append(result)

        if result["status"] == "ok":
            print(
                f"OK  ({result['latency_s']}s) — \"{result['response']}\"",
                file=sys.stderr,
            )
        else:
            print(
                f"FAIL  ({result['status']}, {result['latency_s']}s) — {result.get('error', '')}",
                file=sys.stderr,
            )

    if args.json:
        print(json.dumps(results, indent=2))

    # Exit code: 0 if all ok, 1 if any failed
    if all(r["status"] == "ok" for r in results):
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
