"""Separate shared corpus embedding costs from query-time embedding costs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class UsageLedger:
    """Tracks embedding usage by phase without assigning shared costs to methods."""

    corpus_indexing: dict[str, Any] = field(default_factory=dict)
    query_time: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(
        default_factory=lambda: [
            "Shared corpus indexing costs are not assigned exclusively to Method A or B.",
            "Query-time embedding costs are recorded per search invocation.",
        ]
    )

    def record_corpus(self, snapshot_sha: str, payload: dict[str, Any]) -> None:
        self.corpus_indexing[snapshot_sha] = {
            **payload,
            "shared_preparation_cost": True,
            "assigned_to_method": None,
        }

    def record_query(self, *, label: str, payload: dict[str, Any]) -> None:
        bucket = self.query_time.setdefault(label, {"requests": 0, "entries": []})
        bucket["requests"] = int(bucket["requests"]) + 1
        bucket["entries"].append(payload)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "UsageLedger":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            corpus_indexing=data.get("corpus_indexing") or {},
            query_time=data.get("query_time") or {},
            notes=list(data.get("notes") or []),
        )
