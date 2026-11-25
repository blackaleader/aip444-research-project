"""T1 smoke tests: schema conformance, deterministic retrieval, search CLI helpers.

implementation_origin: teammate_1. Mocked embeddings only — these tests do not
prove live OpenRouter connectivity (see scripts/probe_openrouter_embeddings.py).
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from repo_search import search_cli
from repo_search.chunking import CHUNKER_VERSION, CodeChunk
from repo_search.embeddings import DEFAULT_EMBEDDING_MODEL
from repo_search.retriever import SemanticRetriever
from repo_search.search_cli import (
    SearchCliError,
    resolve_index_dir,
    run_search,
    validate_results_against_schema,
)
from repo_search.vector_index import NumpyVectorIndex

ROOT = Path(__file__).resolve().parents[2]
CHUNK_SCHEMA_PATH = ROOT / "schemas" / "retrieved_chunk.schema.json"


class FakeEmbedder:
    model = DEFAULT_EMBEDDING_MODEL

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    def embed_query(self, query: str) -> list[float]:
        return list(self._vector)


def make_chunk(
    i: int,
    *,
    path: str | None = None,
    token_count: int = 10,
    start_line: int = 1,
) -> CodeChunk:
    return CodeChunk(
        chunk_id=f"chunk-{i}",
        snapshot_sha="s" * 40,
        path=path or f"src/file{i}.ts",
        symbol=f"fn{i}",
        start_line=start_line,
        end_line=start_line + 4,
        text=f"export function fn{i}() {{ return {i}; }}",
        token_count=token_count,
        content_hash=f"hash-{i}",
    )


def make_index(
    chunks: list[CodeChunk], embeddings: list[list[float]]
) -> NumpyVectorIndex:
    return NumpyVectorIndex.build(
        chunk_objs=chunks,
        embeddings=embeddings,
        snapshot_sha="s" * 40,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        tokenizer="cl100k_base",
        chunking={"max_chunk_tokens": 800, "overlap_tokens": 100},
        index_build_id="t1-test-index",
        chunker_version=CHUNKER_VERSION,
    )


@pytest.fixture()
def small_index() -> NumpyVectorIndex:
    chunks = [make_chunk(i) for i in range(4)]
    embeddings = [
        [1.0, 0.0, 0.0],
        [0.8, 0.2, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    return make_index(chunks, embeddings)


def test_search_output_matches_retrieved_chunk_schema(small_index: NumpyVectorIndex) -> None:
    retriever = SemanticRetriever(index=small_index, embedder=FakeEmbedder([1.0, 0.0, 0.0]))
    hits = retriever.search("query", top_k=4, max_tokens=6000)
    assert hits
    schema = json.loads(CHUNK_SCHEMA_PATH.read_text(encoding="utf-8"))
    for hit in hits:
        jsonschema.validate(instance=hit.to_dict(), schema=schema)
    # Helper performs the same validation
    validate_results_against_schema([h.to_dict() for h in hits], CHUNK_SCHEMA_PATH)


def test_retrieval_is_deterministic_across_repeated_calls(small_index: NumpyVectorIndex) -> None:
    retriever = SemanticRetriever(index=small_index, embedder=FakeEmbedder([1.0, 0.0, 0.0]))
    runs = [retriever.search("same query", top_k=4, max_tokens=6000) for _ in range(3)]
    fingerprints = [[(h.chunk_id, h.score) for h in run] for run in runs]
    assert fingerprints[0] == fingerprints[1] == fingerprints[2]
    scores = [h.score for h in runs[0]]
    assert scores == sorted(scores, reverse=True)


def test_equal_scores_break_ties_deterministically() -> None:
    # Identical vectors -> identical scores; order must fall back to path.
    chunks = [
        make_chunk(0, path="src/zeta.ts"),
        make_chunk(1, path="src/alpha.ts"),
        make_chunk(2, path="src/mid.ts"),
    ]
    index = make_index(chunks, [[1.0, 0.0]] * 3)
    retriever = SemanticRetriever(index=index, embedder=FakeEmbedder([1.0, 0.0]))
    hits = retriever.search("q", top_k=3, max_tokens=6000)
    assert [h.path for h in hits] == ["src/alpha.ts", "src/mid.ts", "src/zeta.ts"]


def test_duplicate_spans_are_deduplicated() -> None:
    base = make_chunk(0, path="src/dup.ts", start_line=1)
    dup = CodeChunk(
        chunk_id="chunk-dup",
        snapshot_sha=base.snapshot_sha,
        path=base.path,
        symbol=base.symbol,
        start_line=base.start_line,
        end_line=base.end_line,
        text=base.text,
        token_count=base.token_count,
        content_hash=base.content_hash,
    )
    other = make_chunk(2)
    index = make_index([base, dup, other], [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    retriever = SemanticRetriever(index=index, embedder=FakeEmbedder([1.0, 0.0]))
    hits = retriever.search("q", top_k=3, max_tokens=6000)
    spans = [(h.path, h.start_line, h.end_line) for h in hits]
    assert len(spans) == len(set(spans))
    assert sum(1 for h in hits if h.path == "src/dup.ts") == 1


def test_token_budget_edge_cases() -> None:
    chunks = [
        make_chunk(0, token_count=500),
        make_chunk(1, token_count=100),
        make_chunk(2, token_count=100),
    ]
    index = make_index(chunks, [[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.8, 0.2, 0.0]])
    retriever = SemanticRetriever(index=index, embedder=FakeEmbedder([1.0, 0.0, 0.0]))

    assert retriever.search("q", top_k=0, max_tokens=6000) == []
    assert retriever.search("q", top_k=5, max_tokens=0) == []
    # First-ranked chunk exceeds the whole budget: skipped, smaller chunks fit.
    hits = retriever.search("q", top_k=5, max_tokens=250)
    assert [h.chunk_id for h in hits] == ["chunk-1", "chunk-2"]
    assert sum(h.token_count for h in hits) <= 250


def test_run_search_payload_and_model_mismatch_guard(small_index: NumpyVectorIndex) -> None:
    payload = run_search(
        index=small_index,
        embedder=FakeEmbedder([1.0, 0.0, 0.0]),
        query="payload query",
        top_k=2,
        max_tokens=6000,
    )
    assert payload["query"] == "payload query"
    assert payload["result_count"] == len(payload["results"]) == 2
    assert payload["index"]["snapshot_sha"] == "s" * 40
    assert payload["index"]["embedding_model"] == DEFAULT_EMBEDDING_MODEL
    assert payload["evidence_tokens_used"] == sum(
        r["token_count"] for r in payload["results"]
    )
    schema = json.loads(CHUNK_SCHEMA_PATH.read_text(encoding="utf-8"))
    for result in payload["results"]:
        jsonschema.validate(instance=result, schema=schema)

    mismatched = FakeEmbedder([1.0, 0.0, 0.0])
    mismatched.model = "other/embedding-model"
    with pytest.raises(SearchCliError, match="silent substitution"):
        run_search(index=small_index, embedder=mismatched, query="q")


def test_resolve_index_dir_explicit_and_by_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, small_index: NumpyVectorIndex
) -> None:
    sha = "s" * 40
    built = tmp_path / "indexes" / sha[:12]
    small_index.save(built)

    assert resolve_index_dir(index_dir=built) == built
    with pytest.raises(SearchCliError, match="missing meta.json"):
        resolve_index_dir(index_dir=tmp_path / "nowhere")

    monkeypatch.setattr(
        search_cli,
        "load_pilot_snapshot_specs",
        lambda: [{"task_id": "pi_demo_task", "snapshot_sha": sha, "worktree_path": "x"}],
    )
    assert resolve_index_dir(task_id="pi_demo_task", artifacts_root=tmp_path) == built
    with pytest.raises(SearchCliError, match="unknown pilot task_id"):
        resolve_index_dir(task_id="pi_missing_task", artifacts_root=tmp_path)
    with pytest.raises(SearchCliError, match="provide either"):
        resolve_index_dir()
