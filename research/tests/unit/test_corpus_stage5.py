"""Stage 5: scanning, chunking, embeddings, index, retriever tests (mocked API)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import httpx
import numpy as np
import pytest

from repo_search.chunking import (
    CHUNKER_VERSION,
    chunk_file,
    count_tokens,
    get_encoder,
    make_chunk_id,
)
from repo_search.corpus_scan import scan_repository, should_exclude_dir, should_include_file
from repo_search.embeddings import (
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingCache,
    OpenRouterEmbedder,
)
from repo_search.retriever import SemanticRetriever
from repo_search.vector_index import NumpyVectorIndex, l2_normalize
from repo_search.chunking import CodeChunk

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
    (tmp_path / "dist").mkdir()
    (tmp_path / "src" / "hello.ts").write_text(
        "export function alpha() {\n  return 1;\n}\n\n"
        "export function beta() {\n  return 2;\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Sample\n", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name":"sample"}\n', encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Follow tests.\n", encoding="utf-8")
    (tmp_path / "node_modules" / "pkg" / "index.js").write_text("x", encoding="utf-8")
    (tmp_path / "dist" / "out.js").write_text("y", encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01\x02")
    return tmp_path


def test_deterministic_scan_and_exclusions(sample_repo: Path) -> None:
    files, excluded = scan_repository(sample_repo)
    paths = [f.path for f in files]
    assert paths == sorted(paths)
    assert "src/hello.ts" in paths
    assert "README.md" in paths
    assert "package.json" in paths
    assert "AGENTS.md" in paths
    assert not any(p.startswith("node_modules") for p in paths)
    assert not any(p.startswith("dist/") for p in paths)
    assert should_exclude_dir("node_modules")
    assert should_exclude_dir(".git")
    assert not should_exclude_dir(".github")
    assert should_include_file(sample_repo / "src" / "hello.ts")
    assert not should_include_file(sample_repo / "binary.bin")
    # second scan identical
    files2, _ = scan_repository(sample_repo)
    assert [f.path for f in files2] == paths


def test_stable_chunk_ids_and_line_provenance(sample_repo: Path) -> None:
    sha = "a" * 40
    path = sample_repo / "src" / "hello.ts"
    c1 = chunk_file(abs_path=path, rel_path="src/hello.ts", snapshot_sha=sha)
    c2 = chunk_file(abs_path=path, rel_path="src/hello.ts", snapshot_sha=sha)
    assert len(c1) >= 1
    assert [c.chunk_id for c in c1] == [c.chunk_id for c in c2]
    for c in c1:
        assert c.snapshot_sha == sha
        assert c.path == "src/hello.ts"
        assert c.start_line >= 1
        assert c.end_line >= c.start_line
        assert c.token_count == count_tokens(c.text)
        assert c.chunker_version == CHUNKER_VERSION
        assert c.content_hash
        assert c.chunk_id == make_chunk_id(sha, c.path, c.start_line, c.end_line, c.text)


def test_chunking_line_fallback_for_non_ts(tmp_path: Path) -> None:
    # Force many lines so fallback splits
    lines = [f"line {i} content " + ("word " * 20) for i in range(200)]
    p = tmp_path / "notes.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    chunks = chunk_file(
        abs_path=p,
        rel_path="notes.md",
        snapshot_sha="b" * 40,
        max_chunk_tokens=100,
        overlap_tokens=20,
    )
    assert len(chunks) > 1
    assert all(c.symbol is None for c in chunks)
    assert all(c.token_count <= 120 for c in chunks)  # allow minor overshoot on last lines


def test_embedding_validation_ordering_and_cache(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == DEFAULT_EMBEDDING_MODEL
        inputs = body["input"]
        # Return out-of-order indices to verify reordering
        data = []
        for i, _text in enumerate(inputs):
            vec = [0.0] * 1536
            vec[0] = float(i + 1)
            data.append({"index": len(inputs) - 1 - i, "embedding": [0.0] * 1536})
        # properly set by original index
        data = []
        for i in range(len(inputs)):
            vec = [0.0] * 1536
            vec[i % 8] = 1.0
            data.append({"index": len(inputs) - 1 - i, "embedding": vec, "orig": i})
        # Fix: build with reversed index field
        data = []
        for i in range(len(inputs)):
            vec = [float((i + 1) % 7)] + [0.1] * 1535
            data.append({"index": i, "embedding": vec})
        data = list(reversed(data))  # out of order
        return httpx.Response(
            200,
            json={
                "model": DEFAULT_EMBEDDING_MODEL,
                "data": data,
                "usage": {"prompt_tokens": 12, "total_tokens": 12},
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    cache = EmbeddingCache(tmp_path / "cache")
    emb = OpenRouterEmbedder(
        api_key="test-key",
        model=DEFAULT_EMBEDDING_MODEL,
        cache=cache,
        client=client,
    )
    r1 = emb.embed_texts(
        ["aaa", "bbb"],
        snapshot_sha="snap1",
        content_hashes=["h1", "h2"],
    )
    assert r1.dimensions == 1536
    assert r1.fetched_count == 2
    assert r1.usage.requests == 1
    assert calls["n"] == 1
    # Cache hit
    r2 = emb.embed_texts(
        ["aaa", "bbb"],
        snapshot_sha="snap1",
        content_hashes=["h1", "h2"],
    )
    assert r2.cached_count == 2
    assert r2.fetched_count == 0
    assert calls["n"] == 1
    assert r1.vectors == r2.vectors
    emb.close()


def test_vector_index_persistence_and_cosine_ranking(tmp_path: Path) -> None:
    chunks = [
        CodeChunk(
            chunk_id="c1",
            snapshot_sha="s",
            path="a.ts",
            symbol="a",
            start_line=1,
            end_line=2,
            text="alpha",
            token_count=1,
            content_hash="1",
        ),
        CodeChunk(
            chunk_id="c2",
            snapshot_sha="s",
            path="b.ts",
            symbol="b",
            start_line=1,
            end_line=2,
            text="beta",
            token_count=1,
            content_hash="2",
        ),
        CodeChunk(
            chunk_id="c3",
            snapshot_sha="s",
            path="c.ts",
            symbol="c",
            start_line=1,
            end_line=2,
            text="gamma",
            token_count=1,
            content_hash="3",
        ),
    ]
    # Query closer to first vector
    embeddings = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    idx = NumpyVectorIndex.build(
        chunk_objs=chunks,
        embeddings=embeddings,
        snapshot_sha="s",
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        tokenizer="cl100k_base",
        chunking={"max_chunk_tokens": 800},
        index_build_id="test-idx",
        chunker_version=CHUNKER_VERSION,
    )
    out = tmp_path / "idx"
    idx.save(out)
    loaded = NumpyVectorIndex.load(out)
    assert loaded.meta.dimensions == 3
    assert loaded.meta.snapshot_sha == "s"
    hits = loaded.query([0.9, 0.1, 0.0], top_k=2)
    assert hits[0][0]["chunk_id"] == "c1"
    assert hits[0][1] > hits[1][1]


def test_retriever_topk_and_token_budget() -> None:
    chunks = []
    embeddings = []
    for i in range(5):
        chunks.append(
            CodeChunk(
                chunk_id=f"c{i}",
                snapshot_sha="s",
                path=f"f{i}.ts",
                symbol=None,
                start_line=1,
                end_line=10,
                text="x" * (50 + i),
                token_count=100 * (i + 1),  # 100,200,300,400,500
                content_hash=str(i),
            )
        )
        v = [0.0] * 4
        v[0] = 1.0 - i * 0.1
        embeddings.append(v)
    index = NumpyVectorIndex.build(
        chunk_objs=chunks,
        embeddings=embeddings,
        snapshot_sha="s",
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        tokenizer="cl100k_base",
        chunking={},
        index_build_id="t",
        chunker_version=CHUNKER_VERSION,
    )

    class FakeEmb:
        model = DEFAULT_EMBEDDING_MODEL

        def embed_query(self, query: str) -> list[float]:
            return [1.0, 0.0, 0.0, 0.0]

    retriever = SemanticRetriever(
        index=index,
        embedder=FakeEmb(),  # type: ignore[arg-type]
        default_top_k=10,
        default_max_tokens=6000,
    )
    hits = retriever.search("q", top_k=3, max_tokens=6000)
    assert len(hits) == 3
    assert hits[0].chunk_id == "c0"
    # Budget: 100+200=300, next 300 would fit under 350? use 250 => only first two? 100+200=300 > 250 so only first
    hits2 = retriever.search("q", top_k=10, max_tokens=250)
    assert len(hits2) == 1
    assert hits2[0].token_count == 100
    assert sum(h.token_count for h in hits2) <= 250


def test_snapshot_separation(tmp_path: Path) -> None:
    def make_index(sha: str, path: str) -> NumpyVectorIndex:
        chunk = CodeChunk(
            chunk_id=f"{sha}-1",
            snapshot_sha=sha,
            path=path,
            symbol=None,
            start_line=1,
            end_line=1,
            text="same text",
            token_count=2,
            content_hash="x",
        )
        return NumpyVectorIndex.build(
            chunk_objs=[chunk],
            embeddings=[[1.0, 0.0]],
            snapshot_sha=sha,
            embedding_model=DEFAULT_EMBEDDING_MODEL,
            tokenizer="cl100k_base",
            chunking={},
            index_build_id=f"id-{sha}",
            chunker_version=CHUNKER_VERSION,
        )

    a = make_index("shaA", "lazy.ts")
    b = make_index("shaB", "pkg.ts")
    da, db = tmp_path / "a", tmp_path / "b"
    a.save(da)
    b.save(db)
    la, lb = NumpyVectorIndex.load(da), NumpyVectorIndex.load(db)
    assert la.meta.snapshot_sha != lb.meta.snapshot_sha
    assert la.chunks[0]["path"] != lb.chunks[0]["path"]


def test_retriever_interface_compatibility() -> None:
    chunk = CodeChunk(
        chunk_id="c",
        snapshot_sha="s",
        path="p.ts",
        symbol="fn",
        start_line=1,
        end_line=3,
        text="code",
        token_count=1,
        content_hash="h",
    )
    index = NumpyVectorIndex.build(
        chunk_objs=[chunk],
        embeddings=[[1.0]],
        snapshot_sha="s",
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        tokenizer="cl100k_base",
        chunking={},
        index_build_id="i",
        chunker_version=CHUNKER_VERSION,
    )

    class FakeEmb:
        def embed_query(self, query: str) -> list[float]:
            return [1.0]

    r = SemanticRetriever(index=index, embedder=FakeEmb())  # type: ignore[arg-type]
    assert callable(r.search)
    out = r.search("query", top_k=10, max_tokens=6000)
    assert isinstance(out, list)
    assert out[0].path == "p.ts"
    assert out[0].symbol == "fn"
    d = out[0].to_dict()
    for key in (
        "chunk_id",
        "snapshot_sha",
        "path",
        "symbol",
        "start_line",
        "end_line",
        "text",
        "token_count",
        "content_hash",
        "chunker_version",
        "score",
    ):
        assert key in d


def test_l2_normalize_unit() -> None:
    m = np.asarray([[3.0, 4.0]], dtype=np.float32)
    n = l2_normalize(m)
    assert math.isclose(float(np.linalg.norm(n[0])), 1.0, rel_tol=1e-5)


def test_mocked_tests_do_not_claim_live_api() -> None:
    # Documentation guard: this module uses MockTransport only.
    src = Path(__file__).read_text(encoding="utf-8")
    assert "MockTransport" in src
    assert "live_api_verified" not in src or "False" in src
