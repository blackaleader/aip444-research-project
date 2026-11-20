"""Shared semantic retriever for Stage 5 / Stage 6 methods."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from repo_search.embeddings import OpenRouterEmbedder
from repo_search.vector_index import NumpyVectorIndex


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    snapshot_sha: str
    path: str
    symbol: str | None
    start_line: int
    end_line: int
    text: str
    token_count: int
    content_hash: str
    chunker_version: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SemanticRetriever:
    """
    search(query, top_k, max_tokens) -> list[RetrievedChunk]

    One-shot RAG must call this exactly once per run. Internal embedding
    requests and vector math are implementation details, not search invocations.
    """

    def __init__(
        self,
        *,
        index: NumpyVectorIndex,
        embedder: OpenRouterEmbedder,
        default_top_k: int = 10,
        default_max_tokens: int = 6000,
    ) -> None:
        self.index = index
        self.embedder = embedder
        self.default_top_k = default_top_k
        self.default_max_tokens = default_max_tokens

    def search(
        self,
        query: str,
        top_k: int | None = None,
        max_tokens: int | None = None,
    ) -> list[RetrievedChunk]:
        k = self.default_top_k if top_k is None else top_k
        budget = self.default_max_tokens if max_tokens is None else max_tokens
        if k <= 0 or budget <= 0:
            return []

        qvec = self.embedder.embed_query(query)
        # Over-fetch slightly to allow token-budget trimming after dedupe
        fetch_k = min(max(k * 3, k), len(self.index.chunks))
        hits = self.index.query(qvec, top_k=fetch_k)

        seen_ids: set[str] = set()
        seen_spans: set[tuple[str, int, int]] = set()
        selected: list[RetrievedChunk] = []
        used_tokens = 0

        for chunk, score in hits:
            cid = str(chunk.get("chunk_id") or "")
            path = str(chunk.get("path") or "")
            start = int(chunk.get("start_line") or 0)
            end = int(chunk.get("end_line") or 0)
            span = (path, start, end)
            if cid in seen_ids or span in seen_spans:
                continue
            tok = int(chunk.get("token_count") or 0)
            if selected and used_tokens + tok > budget:
                continue
            if not selected and tok > budget:
                # Still include first hit if it alone exceeds budget? Spec: enforce budget.
                # Skip if single chunk exceeds budget.
                continue
            seen_ids.add(cid)
            seen_spans.add(span)
            selected.append(
                RetrievedChunk(
                    chunk_id=cid,
                    snapshot_sha=str(chunk.get("snapshot_sha") or ""),
                    path=path,
                    symbol=chunk.get("symbol"),
                    start_line=start,
                    end_line=end,
                    text=str(chunk.get("text") or ""),
                    token_count=tok,
                    content_hash=str(chunk.get("content_hash") or ""),
                    chunker_version=str(chunk.get("chunker_version") or ""),
                    score=float(score),
                )
            )
            used_tokens += tok
            if len(selected) >= k:
                break

        return selected
