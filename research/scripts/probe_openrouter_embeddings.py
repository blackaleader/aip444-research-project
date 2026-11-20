#!/usr/bin/env python3
"""Small live probe of OpenRouter embeddings (Stage 5 connectivity check)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load_dotenv(path: Path) -> None:
    import os

    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def main() -> int:
    _load_dotenv(ROOT / ".env")
    from repo_search.embeddings import (
        DEFAULT_EMBEDDING_MODEL,
        EXPECTED_DIMENSIONS,
        OpenRouterEmbedder,
        resolve_openrouter_api_key,
    )

    if not resolve_openrouter_api_key():
        report = {
            "status": "pending",
            "reason": "OPENROUTER_API_KEY / LLM_API_KEY not set",
            "model": DEFAULT_EMBEDDING_MODEL,
            "live_api_verified": False,
        }
        print(json.dumps(report, indent=2))
        return 2

    with OpenRouterEmbedder(model=DEFAULT_EMBEDDING_MODEL, cache=None) as emb:
        result = emb.embed_texts(["Stage 5 OpenRouter embedding probe."])
        report = {
            "status": "ok",
            "live_api_verified": True,
            "requested_model": DEFAULT_EMBEDDING_MODEL,
            "returned_model": result.model,
            "dimensions": result.dimensions,
            "expected_dimensions": EXPECTED_DIMENSIONS,
            "dimensions_match_expected": result.dimensions == EXPECTED_DIMENSIONS,
            "usage": {
                "prompt_tokens": result.usage.prompt_tokens,
                "total_tokens": result.usage.total_tokens,
                "requests": result.usage.requests,
            },
            "vector_norm_sample": sum(x * x for x in result.vectors[0]) ** 0.5,
            "note": "Credentials not logged.",
        }
        print(json.dumps(report, indent=2))
        return 0 if result.dimensions > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
