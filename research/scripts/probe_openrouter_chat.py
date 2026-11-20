#!/usr/bin/env python3
"""Minimal live OpenRouter chat connectivity check (neutral prompt; not a pilot trial)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def main() -> int:
    _load_dotenv(ROOT / ".env")
    from repo_search.chat_client import (
        DEFAULT_PRIMARY_CHAT_MODEL,
        OpenRouterChatClient,
    )
    from repo_search.embeddings import resolve_openrouter_api_key

    if not resolve_openrouter_api_key():
        print(
            json.dumps(
                {
                    "status": "pending",
                    "live_chat_verified": False,
                    "reason": "OPENROUTER_API_KEY not set",
                    "requested_model": DEFAULT_PRIMARY_CHAT_MODEL,
                },
                indent=2,
            )
        )
        return 2

    with OpenRouterChatClient(
        model=DEFAULT_PRIMARY_CHAT_MODEL,
        temperature=0,
        max_completion_tokens=64,
        allow_model_mismatch=False,
    ) as client:
        try:
            resp = client.complete(
                [
                    {
                        "role": "user",
                        "content": "Reply with exactly the word pong and nothing else.",
                    }
                ],
                tools=None,
                tool_choice=None,
            )
        except Exception as exc:  # noqa: BLE001
            print(
                json.dumps(
                    {
                        "status": "error",
                        "live_chat_verified": False,
                        "requested_model": DEFAULT_PRIMARY_CHAT_MODEL,
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:500],
                        "note": "Credentials not logged.",
                    },
                    indent=2,
                )
            )
            return 1

        report = {
            "status": "ok",
            "live_chat_verified": True,
            "requested_model": resp.requested_model,
            "returned_model": resp.model,
            "finish_reason": resp.finish_reason,
            "content_preview": (resp.content or "")[:80],
            "usage": {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total_tokens": resp.usage.total_tokens,
                "cost": resp.usage.cost,
            },
            "latency_ms": round(resp.latency_ms, 2),
            "note": "Neutral connectivity probe only. Not a pilot task or experiment trial.",
        }
        print(json.dumps(report, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
