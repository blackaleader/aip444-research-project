#!/usr/bin/env python3
"""Validate Stage 5 indexes and run retriever smoke tests (not an experiment)."""

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
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def main() -> int:
    _load_dotenv(ROOT / ".env")
    from repo_search.benchmark_loader import method_input_bundle
    from repo_search.embeddings import (
        DEFAULT_EMBEDDING_MODEL,
        EXPECTED_DIMENSIONS,
        EmbeddingCache,
        OpenRouterEmbedder,
    )
    from repo_search.retriever import SemanticRetriever
    from repo_search.vector_index import NumpyVectorIndex

    specs = [
        (
            "pi_lazy_extension_loading",
            "bfa6862400d0aaa3ebf3c09a44a2479487f470f1",
            ROOT / "artifacts" / "indexes" / "bfa6862400d0",
        ),
        (
            "pi_package_filtering",
            "dd838d0fe09db079dcf2f57bab1d79d4df5a0e4c",
            ROOT / "artifacts" / "indexes" / "dd838d0fe09d",
        ),
    ]

    report: dict = {"integrity": [], "smoke": []}

    for tid, sha, directory in specs:
        idx = NumpyVectorIndex.load(directory)
        assert idx.meta.snapshot_sha == sha, (idx.meta.snapshot_sha, sha)
        assert idx.meta.dimensions == EXPECTED_DIMENSIONS
        assert idx.meta.embedding_model == DEFAULT_EMBEDDING_MODEL
        assert idx.vectors.shape == (idx.meta.chunk_count, EXPECTED_DIMENSIONS)
        assert len(idx.chunks) == idx.meta.chunk_count
        n_manifest = sum(
            1 for _ in (directory / "chunks_manifest.jsonl").open(encoding="utf-8")
        )
        assert n_manifest == idx.meta.chunk_count
        sample = idx.chunks[0]
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
        ):
            assert key in sample, key
        assert sample["snapshot_sha"] == sha
        entry = {
            "task_id": tid,
            "snapshot_sha": sha,
            "chunk_count": idx.meta.chunk_count,
            "dimensions": idx.meta.dimensions,
            "index_build_id": idx.meta.index_build_id,
            "index_dir": str(directory),
            "ok": True,
        }
        report["integrity"].append(entry)
        print("OK integrity", json.dumps(entry))

    cache = EmbeddingCache(ROOT / "artifacts" / "embedding_cache")
    with OpenRouterEmbedder(cache=cache, model=DEFAULT_EMBEDDING_MODEL) as emb:
        for tid, sha, directory in specs:
            idx = NumpyVectorIndex.load(directory)
            retriever = SemanticRetriever(
                index=idx,
                embedder=emb,
                default_top_k=10,
                default_max_tokens=6000,
            )
            prompt = method_input_bundle(tid)["task"]["task_prompt"]
            hits = retriever.search(prompt, top_k=10, max_tokens=6000)
            assert len(hits) <= 10
            used = sum(h.token_count for h in hits)
            assert used <= 6000
            for hit in hits:
                assert hit.snapshot_sha == sha
                assert hit.path and hit.chunk_id and hit.text and hit.content_hash
                assert hit.start_line >= 1 and hit.end_line >= hit.start_line
            top = [
                {
                    "score": round(h.score, 4),
                    "path": h.path,
                    "start_line": h.start_line,
                    "end_line": h.end_line,
                    "symbol": h.symbol,
                    "token_count": h.token_count,
                }
                for h in hits[:5]
            ]
            smoke = {
                "task_id": tid,
                "hit_count": len(hits),
                "evidence_tokens": used,
                "query_chars": len(prompt),
                "top5": top,
                "ok": True,
            }
            report["smoke"].append(smoke)
            print("OK smoke", json.dumps(smoke, indent=2))

    out = ROOT / "artifacts" / "stage5_validation_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("WROTE", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
