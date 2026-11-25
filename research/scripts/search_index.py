#!/usr/bin/env python3
"""Search a built Stage 5 index: search(query, top_k, max_tokens) from the CLI.

T1 utility (implementation_origin: teammate_1). Requires a built index under
artifacts/indexes/<sha12>/ and OPENROUTER_API_KEY for the query embedding.

Examples:
  python scripts/search_index.py --task-id pi_lazy_extension_loading \
      --query "How are extensions loaded lazily?"
  python scripts/search_index.py --index-dir artifacts/indexes/bfa6862400d0 \
      --query "package filtering rules" --top-k 5 --max-tokens 2000 --validate
"""

from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--task-id", help="Pilot task id from snapshots manifest.")
    target.add_argument("--index-dir", type=Path, help="Explicit index directory.")
    parser.add_argument("--query", required=True, help="Search query text.")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-tokens", type=int, default=6000)
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=None,
        help="Artifacts root (default: research/artifacts).",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate results against schemas/retrieved_chunk.schema.json.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON payload to this file instead of stdout.",
    )
    args = parser.parse_args()
    _load_dotenv(ROOT / ".env")

    from repo_search.embeddings import (
        DEFAULT_EMBEDDING_MODEL,
        EmbeddingCache,
        OpenRouterEmbedder,
        resolve_openrouter_api_key,
    )
    from repo_search.search_cli import (
        SearchCliError,
        resolve_index_dir,
        run_search,
        validate_results_against_schema,
    )
    from repo_search.vector_index import NumpyVectorIndex

    if not resolve_openrouter_api_key():
        print(
            "ERROR: OPENROUTER_API_KEY (or LLM_API_KEY) is not set; "
            "it is required to embed the query.",
            file=sys.stderr,
        )
        return 1

    artifacts = args.artifacts or (ROOT / "artifacts")
    try:
        index_dir = resolve_index_dir(
            task_id=args.task_id,
            index_dir=args.index_dir,
            artifacts_root=artifacts,
        )
        index = NumpyVectorIndex.load(index_dir)
        cache = EmbeddingCache(artifacts / "embedding_cache")
        with OpenRouterEmbedder(cache=cache, model=DEFAULT_EMBEDDING_MODEL) as emb:
            payload = run_search(
                index=index,
                embedder=emb,
                query=args.query,
                top_k=args.top_k,
                max_tokens=args.max_tokens,
            )
        if args.validate:
            validate_results_against_schema(
                payload["results"], ROOT / "schemas" / "retrieved_chunk.schema.json"
            )
            payload["schema_validated"] = True
    except SearchCliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {payload['result_count']} results to {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
