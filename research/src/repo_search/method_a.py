"""Method A — one-shot code RAG (exactly one semantic search, no LLM)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from repo_search.evidence import EvidenceLedger, EvidencePack, chunks_to_evidence, pack_from_items
from repo_search.retriever import SemanticRetriever


@dataclass
class MethodAResult:
    evidence_pack: EvidencePack
    stop_reason: str
    tool_call_count: int
    semantic_search_count: int
    llm_call_count: int
    query: str
    latency_ms: float
    retrieval_trace: dict[str, Any]
    ledger: EvidenceLedger
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": "one_shot_rag",
            "stop_reason": self.stop_reason,
            "tool_call_count": self.tool_call_count,
            "semantic_search_count": self.semantic_search_count,
            "llm_call_count": self.llm_call_count,
            "query": self.query,
            "latency_ms": self.latency_ms,
            "evidence_pack": self.evidence_pack.to_dict(),
            "evidence_accounting": {
                **self.ledger.summary(),
                "final_evidence_pack_tokens": self.evidence_pack.token_count,
            },
            "retrieval_trace": self.retrieval_trace,
            "errors": self.errors,
        }


def run_method_a(
    *,
    task_prompt: str,
    retriever: SemanticRetriever,
    top_k: int = 10,
    max_tokens: int = 6000,
) -> MethodAResult:
    """
    Deterministic baseline:
    exact task prompt → exactly one shared semantic search → final evidence pack.
    """
    t0 = time.perf_counter()
    ledger = EvidenceLedger(evidence_budget=max_tokens)
    errors: list[str] = []
    query = task_prompt  # unchanged

    chunks = retriever.search(query, top_k=top_k, max_tokens=max_tokens)
    items = chunks_to_evidence(chunks, source_tool="one_shot_rag")
    for item in items:
        ledger.add_excerpt(item, count_repeat=True)

    pack = pack_from_items(items, max_tokens=max_tokens)
    latency_ms = (time.perf_counter() - t0) * 1000
    trace = {
        "operation": "semantic_search",
        "query": query,
        "query_unchanged": True,
        "top_k": top_k,
        "max_tokens": max_tokens,
        "result_chunk_ids": [c.chunk_id for c in chunks],
        "result_count": len(chunks),
        "llm_calls": 0,
    }
    return MethodAResult(
        evidence_pack=pack,
        stop_reason="completed",
        tool_call_count=1,
        semantic_search_count=1,
        llm_call_count=0,
        query=query,
        latency_ms=latency_ms,
        retrieval_trace=trace,
        ledger=ledger,
        errors=errors,
    )
