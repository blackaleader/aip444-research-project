"""Persistent NumPy cosine-similarity vector index."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from repo_search.chunking import CodeChunk


@dataclass
class IndexMeta:
    snapshot_sha: str
    embedding_model: str
    dimensions: int
    tokenizer: str
    chunking: dict[str, Any]
    index_build_id: str
    chunk_count: int
    built_at: str
    chunker_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IndexMeta":
        return cls(**data)


def l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return matrix / norms


class NumpyVectorIndex:
    """Local persistent vector store with cosine similarity via normalized dot product."""

    def __init__(
        self,
        *,
        vectors: np.ndarray,
        chunks: list[dict[str, Any]],
        meta: IndexMeta,
    ) -> None:
        if vectors.ndim != 2:
            raise ValueError("vectors must be 2-D")
        if vectors.shape[0] != len(chunks):
            raise ValueError("vector/chunk count mismatch")
        if vectors.shape[1] != meta.dimensions:
            raise ValueError("vector dimensions do not match metadata")
        self.vectors = vectors.astype(np.float32, copy=False)
        self.chunks = chunks
        self.meta = meta

    @classmethod
    def build(
        cls,
        *,
        chunk_objs: Sequence[CodeChunk],
        embeddings: Sequence[Sequence[float]],
        snapshot_sha: str,
        embedding_model: str,
        tokenizer: str,
        chunking: dict[str, Any],
        index_build_id: str,
        chunker_version: str,
    ) -> "NumpyVectorIndex":
        if len(chunk_objs) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        if not embeddings:
            raise ValueError("cannot build empty index")
        mat = np.asarray(embeddings, dtype=np.float32)
        dims = int(mat.shape[1])
        mat = l2_normalize(mat)
        meta = IndexMeta(
            snapshot_sha=snapshot_sha,
            embedding_model=embedding_model,
            dimensions=dims,
            tokenizer=tokenizer,
            chunking=chunking,
            index_build_id=index_build_id,
            chunk_count=len(chunk_objs),
            built_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            chunker_version=chunker_version,
        )
        chunks = [c.to_dict() for c in chunk_objs]
        # Drop bulky text from in-memory optional? Keep text for retrieval evidence.
        return cls(vectors=mat, chunks=chunks, meta=meta)

    def save(self, directory: Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        np.save(directory / "vectors.npy", self.vectors)
        (directory / "chunks.json").write_text(
            json.dumps(self.chunks, indent=2), encoding="utf-8"
        )
        (directory / "meta.json").write_text(
            json.dumps(self.meta.to_dict(), indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, directory: Path) -> "NumpyVectorIndex":
        directory = Path(directory)
        vectors = np.load(directory / "vectors.npy")
        chunks = json.loads((directory / "chunks.json").read_text(encoding="utf-8"))
        meta = IndexMeta.from_dict(
            json.loads((directory / "meta.json").read_text(encoding="utf-8"))
        )
        return cls(vectors=vectors, chunks=chunks, meta=meta)

    def query(
        self,
        query_vector: Sequence[float],
        *,
        top_k: int = 10,
    ) -> list[tuple[dict[str, Any], float]]:
        if top_k <= 0:
            return []
        q = np.asarray(query_vector, dtype=np.float32)
        if q.ndim != 1 or q.shape[0] != self.meta.dimensions:
            raise ValueError(
                f"query dim {q.shape} incompatible with index dim {self.meta.dimensions}"
            )
        qn = q / max(float(np.linalg.norm(q)), 1e-12)
        scores = self.vectors @ qn
        k = min(top_k, scores.shape[0])
        # argpartition then stable sort for determinism
        if k < scores.shape[0]:
            idx = np.argpartition(-scores, k)[:k]
        else:
            idx = np.arange(scores.shape[0])
        # deterministic: score desc, then path, then start_line, then chunk_id
        ranked = sorted(
            idx.tolist(),
            key=lambda i: (
                -float(scores[i]),
                self.chunks[i].get("path") or "",
                int(self.chunks[i].get("start_line") or 0),
                self.chunks[i].get("chunk_id") or "",
            ),
        )
        return [(self.chunks[i], float(scores[i])) for i in ranked]

    def size_bytes_on_disk(self, directory: Path) -> int:
        directory = Path(directory)
        total = 0
        for name in ("vectors.npy", "chunks.json", "meta.json"):
            p = directory / name
            if p.exists():
                total += p.stat().st_size
        return total
