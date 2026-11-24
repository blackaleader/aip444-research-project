"""T1 search helpers: index resolution and single-query search payloads.

implementation_origin: teammate_1. Wraps the Stage 5 SemanticRetriever without
modifying it; the frozen pilot-v1.0 defaults (top_k=10, max_tokens=6000) are
read as defaults only and remain overridable per call.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from repo_search.corpus_build import default_index_dir, load_pilot_snapshot_specs
from repo_search.embeddings import OpenRouterEmbedder
from repo_search.retriever import SemanticRetriever
from repo_search.vector_index import NumpyVectorIndex

PROTOCOL_TOP_K = 10
PROTOCOL_MAX_TOKENS = 6000


class SearchCliError(RuntimeError):
    pass


def resolve_index_dir(
    *,
    task_id: str | None = None,
    index_dir: Path | None = None,
    artifacts_root: Path | None = None,
) -> Path:
    """Resolve an index directory from an explicit path or a pilot task id."""
    if index_dir is not None:
        resolved = Path(index_dir)
        if not (resolved / "meta.json").exists():
            raise SearchCliError(f"no index found at {resolved} (missing meta.json)")
        return resolved
    if not task_id:
        raise SearchCliError("provide either task_id or index_dir")
    specs = {s["task_id"]: s for s in load_pilot_snapshot_specs()}
    spec = specs.get(task_id)
    if spec is None:
        raise SearchCliError(
            f"unknown pilot task_id {task_id!r}; known: {sorted(specs)}"
        )
    resolved = default_index_dir(spec["snapshot_sha"], artifacts_root)
    if not (resolved / "meta.json").exists():
        raise SearchCliError(
            f"index for {task_id} not built at {resolved}; "
            "run scripts/build_corpus_indexes.py first"
        )
    return resolved


def run_search(
    *,
    index: NumpyVectorIndex,
    embedder: OpenRouterEmbedder,
    query: str,
    top_k: int = PROTOCOL_TOP_K,
    max_tokens: int = PROTOCOL_MAX_TOKENS,
) -> dict[str, Any]:
    """One search() call returning a JSON-ready payload of schema-shaped chunks."""
    embedder_model = getattr(embedder, "model", None)
    if embedder_model is not None and embedder_model != index.meta.embedding_model:
        raise SearchCliError(
            "query embedder model "
            f"{embedder_model!r} does not match index embedding model "
            f"{index.meta.embedding_model!r}; silent substitution is forbidden"
        )
    retriever = SemanticRetriever(
        index=index,
        embedder=embedder,
        default_top_k=PROTOCOL_TOP_K,
        default_max_tokens=PROTOCOL_MAX_TOKENS,
    )
    hits = retriever.search(query, top_k=top_k, max_tokens=max_tokens)
    results = [h.to_dict() for h in hits]
    return {
        "query": query,
        "top_k": top_k,
        "max_tokens": max_tokens,
        "index": {
            "snapshot_sha": index.meta.snapshot_sha,
            "embedding_model": index.meta.embedding_model,
            "dimensions": index.meta.dimensions,
            "index_build_id": index.meta.index_build_id,
            "chunk_count": index.meta.chunk_count,
            "chunker_version": index.meta.chunker_version,
        },
        "result_count": len(results),
        "evidence_tokens_used": sum(r["token_count"] for r in results),
        "results": results,
    }


def validate_results_against_schema(
    results: list[dict[str, Any]], schema_path: Path
) -> None:
    """Validate chunk dicts against retrieved_chunk.schema.json (needs jsonschema)."""
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - dev extra not installed
        raise SearchCliError(
            "jsonschema is required for --validate; install dev extras"
        ) from exc
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    for result in results:
        jsonschema.validate(instance=result, schema=schema)
