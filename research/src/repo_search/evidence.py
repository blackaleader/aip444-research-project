"""Normalized evidence packs and token accounting for Methods A/B."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Literal

from repo_search.chunking import count_tokens, get_encoder
from repo_search.retriever import RetrievedChunk

SourceTool = Literal[
    "semantic_search",
    "read_file",
    "find_symbol",
    "grep",
    "one_shot_rag",
]


@dataclass
class EvidenceItem:
    evidence_id: str
    path: str
    symbol: str | None
    start_line: int
    end_line: int
    text: str
    token_count: int
    source_tool: SourceTool
    chunk_id: str | None = None
    score: float | None = None
    content_hash: str | None = None
    rank: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def make_id(
        *,
        path: str,
        start_line: int,
        end_line: int,
        text: str,
        source_tool: str,
    ) -> str:
        raw = f"{source_tool}|{path}|{start_line}|{end_line}|{text}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


@dataclass
class EvidencePack:
    items: list[EvidenceItem] = field(default_factory=list)

    @property
    def token_count(self) -> int:
        return sum(i.token_count for i in self.items)

    def to_dict(self) -> dict[str, Any]:
        ranked = []
        for i, item in enumerate(self.items, start=1):
            d = item.to_dict()
            d["rank"] = i
            ranked.append(d)
        return {
            "items": ranked,
            "token_count": self.token_count,
            "file_count": len({i.path for i in self.items}),
        }

    def paths(self) -> list[str]:
        return sorted({i.path for i in self.items})


@dataclass
class EvidenceLedger:
    """Tracks cumulative / unique / pack evidence tokens separately from planning."""

    evidence_budget: int = 6000
    cumulative_evidence_tokens: int = 0
    unique_span_tokens: dict[tuple[str, int, int], int] = field(default_factory=dict)
    excerpts: list[EvidenceItem] = field(default_factory=list)
    encoder_name: str = "cl100k_base"

    def remaining(self) -> int:
        return max(0, self.evidence_budget - self.cumulative_evidence_tokens)

    def unique_evidence_tokens(self) -> int:
        return sum(self.unique_span_tokens.values())

    def add_excerpt(self, item: EvidenceItem, *, count_repeat: bool = True) -> EvidenceItem | None:
        """
        Charge evidence budget for a repository excerpt.
        Repeated spans count again toward cumulative consumption when count_repeat=True.
        Returns the item if accepted (possibly truncated); None if no budget remains.
        """
        if self.remaining() <= 0:
            return None
        text = item.text
        tok = item.token_count
        if tok <= 0:
            tok = count_tokens(text, get_encoder(self.encoder_name))
        if tok > self.remaining():
            # Truncate by lines to fit remaining budget when possible
            lines = text.split("\n")
            kept: list[str] = []
            used = 0
            enc = get_encoder(self.encoder_name)
            for line in lines:
                line_tok = count_tokens(line + "\n", enc)
                if kept and used + line_tok > self.remaining():
                    break
                if not kept and line_tok > self.remaining():
                    return None
                kept.append(line)
                used += line_tok
            if not kept:
                return None
            text = "\n".join(kept)
            tok = used
            item = EvidenceItem(
                evidence_id=EvidenceItem.make_id(
                    path=item.path,
                    start_line=item.start_line,
                    end_line=item.start_line + len(kept) - 1,
                    text=text,
                    source_tool=item.source_tool,
                ),
                path=item.path,
                symbol=item.symbol,
                start_line=item.start_line,
                end_line=item.start_line + len(kept) - 1,
                text=text,
                token_count=tok,
                source_tool=item.source_tool,
                chunk_id=item.chunk_id,
                score=item.score,
                content_hash=item.content_hash,
            )
        if not count_repeat:
            span = (item.path, item.start_line, item.end_line)
            if span in self.unique_span_tokens:
                # Still record exposure for cumulative unique bookkeeping only
                pass
        self.cumulative_evidence_tokens += tok
        span = (item.path, item.start_line, item.end_line)
        self.unique_span_tokens[span] = tok
        self.excerpts.append(item)
        return item

    def summary(self) -> dict[str, Any]:
        return {
            "evidence_budget": self.evidence_budget,
            "cumulative_evidence_tokens": self.cumulative_evidence_tokens,
            "unique_evidence_tokens": self.unique_evidence_tokens(),
            "remaining_evidence_tokens": self.remaining(),
            "excerpt_count": len(self.excerpts),
        }


def chunks_to_evidence(
    chunks: Iterable[RetrievedChunk],
    *,
    source_tool: SourceTool,
) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for ch in chunks:
        items.append(
            EvidenceItem(
                evidence_id=EvidenceItem.make_id(
                    path=ch.path,
                    start_line=ch.start_line,
                    end_line=ch.end_line,
                    text=ch.text,
                    source_tool=source_tool,
                ),
                path=ch.path,
                symbol=ch.symbol,
                start_line=ch.start_line,
                end_line=ch.end_line,
                text=ch.text,
                token_count=ch.token_count,
                source_tool=source_tool,
                chunk_id=ch.chunk_id,
                score=ch.score,
                content_hash=ch.content_hash,
            )
        )
    return items


def pack_from_items(
    items: Iterable[EvidenceItem],
    *,
    max_tokens: int = 6000,
) -> EvidencePack:
    pack = EvidencePack()
    used = 0
    for item in items:
        if used + item.token_count > max_tokens:
            continue
        pack.items.append(item)
        used += item.token_count
    return pack
