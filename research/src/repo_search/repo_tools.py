"""Read-only repository tools bound to a single snapshot worktree + retriever."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from repo_search.chunking import count_tokens, get_encoder
from repo_search.evidence import EvidenceItem, EvidenceLedger, chunks_to_evidence
from repo_search.retriever import SemanticRetriever

ALLOWED_TOOLS = frozenset({"semantic_search", "read_file", "find_symbol", "grep"})


class ToolError(ValueError):
    """Invalid tool arguments or snapshot-boundary violation."""


@dataclass
class ToolResult:
    tool_name: str
    ok: bool
    evidence: list[EvidenceItem] = field(default_factory=list)
    message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "ok": self.ok,
            "message": self.message,
            "evidence": [e.to_dict() for e in self.evidence],
            "raw": self.raw,
        }


@dataclass
class ToolCallRecord:
    tool_name: str
    arguments: dict[str, Any]
    result: ToolResult
    call_index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_index": self.call_index,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result.to_dict(),
        }


class SnapshotToolEnvironment:
    """
    Executes permitted tools inside one assigned snapshot.
    Enforces call limit and cumulative evidence budget.
    """

    def __init__(
        self,
        *,
        worktree: Path,
        snapshot_sha: str,
        retriever: SemanticRetriever,
        ledger: EvidenceLedger,
        max_tool_calls: int = 5,
        top_k: int = 10,
        max_tokens_per_search: int = 6000,
        max_read_tokens: int = 2000,
        max_grep_matches: int = 20,
        max_grep_tokens: int = 2000,
    ) -> None:
        self.worktree = Path(worktree).resolve()
        self.snapshot_sha = snapshot_sha
        self.retriever = retriever
        self.ledger = ledger
        self.max_tool_calls = max_tool_calls
        self.top_k = top_k
        self.max_tokens_per_search = max_tokens_per_search
        self.max_read_tokens = max_read_tokens
        self.max_grep_matches = max_grep_matches
        self.max_grep_tokens = max_grep_tokens
        self.tool_call_count = 0
        self.history: list[ToolCallRecord] = []
        self._encoder = get_encoder("cl100k_base")
        self.known_evidence: dict[str, EvidenceItem] = {}

    def remaining_calls(self) -> int:
        return max(0, self.max_tool_calls - self.tool_call_count)

    def _resolve_path(self, rel: str) -> Path:
        if not rel or rel.startswith("/") or rel.startswith("\\") or ".." in Path(rel).parts:
            raise ToolError(f"invalid path: {rel!r}")
        abs_path = (self.worktree / rel).resolve()
        try:
            abs_path.relative_to(self.worktree)
        except ValueError as exc:
            raise ToolError(f"path escapes snapshot worktree: {rel!r}") from exc
        if not abs_path.is_file():
            raise ToolError(f"file not found in snapshot: {rel}")
        return abs_path

    def execute(self, tool_name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        arguments = dict(arguments or {})
        if tool_name not in ALLOWED_TOOLS:
            raise ToolError(f"forbidden tool: {tool_name}")
        if self.remaining_calls() <= 0:
            raise ToolError("tool call limit reached")
        if self.ledger.remaining() <= 0 and tool_name != "semantic_search":
            # Still allow search attempt but evidence add will truncate/stop
            pass

        self.tool_call_count += 1
        call_index = self.tool_call_count
        try:
            if tool_name == "semantic_search":
                result = self._semantic_search(arguments)
            elif tool_name == "read_file":
                result = self._read_file(arguments)
            elif tool_name == "find_symbol":
                result = self._find_symbol(arguments)
            else:
                result = self._grep(arguments)
        except ToolError as exc:
            result = ToolResult(tool_name=tool_name, ok=False, message=str(exc))
        self.history.append(
            ToolCallRecord(
                tool_name=tool_name,
                arguments=arguments,
                result=result,
                call_index=call_index,
            )
        )
        for item in result.evidence:
            self.known_evidence[item.evidence_id] = item
            if item.chunk_id:
                self.known_evidence[item.chunk_id] = item
        return result

    def _charge(self, items: list[EvidenceItem]) -> list[EvidenceItem]:
        accepted: list[EvidenceItem] = []
        for item in items:
            got = self.ledger.add_excerpt(item, count_repeat=True)
            if got is None:
                break
            accepted.append(got)
        return accepted

    def _semantic_search(self, args: dict[str, Any]) -> ToolResult:
        query = str(args.get("query") or "").strip()
        if not query:
            raise ToolError("semantic_search requires non-empty query")
        top_k = int(args.get("top_k") or self.top_k)
        max_tokens = min(
            int(args.get("max_tokens") or self.max_tokens_per_search),
            self.ledger.remaining() or self.max_tokens_per_search,
        )
        # Cap by remaining budget so search cannot overshoot cumulative budget silently
        max_tokens = min(max_tokens, max(self.ledger.remaining(), 0))
        if max_tokens <= 0:
            return ToolResult(
                tool_name="semantic_search",
                ok=False,
                message="evidence budget exhausted before search",
            )
        chunks = self.retriever.search(query, top_k=top_k, max_tokens=max_tokens)
        items = chunks_to_evidence(chunks, source_tool="semantic_search")
        accepted = self._charge(items)
        return ToolResult(
            tool_name="semantic_search",
            ok=True,
            evidence=accepted,
            message=f"returned {len(accepted)} chunks",
            raw={"query": query, "requested": len(chunks), "accepted": len(accepted)},
        )

    def _read_file(self, args: dict[str, Any]) -> ToolResult:
        path = str(args.get("path") or "")
        abs_path = self._resolve_path(path)
        start = int(args.get("start_line") or 1)
        end = args.get("end_line")
        text = abs_path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        lines = text.split("\n")
        if start < 1:
            raise ToolError("start_line must be >= 1")
        end_line = int(end) if end is not None else len(lines)
        if end_line < start:
            raise ToolError("end_line must be >= start_line")
        end_line = min(end_line, len(lines))
        snippet_lines = lines[start - 1 : end_line]
        # Enforce read token cap
        kept: list[str] = []
        used = 0
        for line in snippet_lines:
            t = count_tokens(line + "\n", self._encoder)
            if kept and used + t > self.max_read_tokens:
                break
            if not kept and t > self.max_read_tokens:
                break
            kept.append(line)
            used += t
        if not kept:
            raise ToolError("requested range exceeds read token limit or is empty")
        actual_end = start + len(kept) - 1
        snippet = "\n".join(kept)
        item = EvidenceItem(
            evidence_id=EvidenceItem.make_id(
                path=path,
                start_line=start,
                end_line=actual_end,
                text=snippet,
                source_tool="read_file",
            ),
            path=path,
            symbol=None,
            start_line=start,
            end_line=actual_end,
            text=snippet,
            token_count=used,
            source_tool="read_file",
        )
        accepted = self._charge([item])
        return ToolResult(
            tool_name="read_file",
            ok=bool(accepted),
            evidence=accepted,
            message="ok" if accepted else "evidence budget exhausted",
        )

    def _find_symbol(self, args: dict[str, Any]) -> ToolResult:
        symbol = str(args.get("symbol") or "").strip()
        if not symbol:
            raise ToolError("find_symbol requires symbol")
        # Prefer index metadata, then filesystem scan
        hits: list[EvidenceItem] = []
        for chunk in self.retriever.index.chunks:
            if chunk.get("symbol") == symbol:
                text = str(chunk.get("text") or "")
                hits.append(
                    EvidenceItem(
                        evidence_id=EvidenceItem.make_id(
                            path=str(chunk.get("path")),
                            start_line=int(chunk["start_line"]),
                            end_line=int(chunk["end_line"]),
                            text=text,
                            source_tool="find_symbol",
                        ),
                        path=str(chunk.get("path")),
                        symbol=symbol,
                        start_line=int(chunk["start_line"]),
                        end_line=int(chunk["end_line"]),
                        text=text,
                        token_count=int(chunk.get("token_count") or count_tokens(text, self._encoder)),
                        source_tool="find_symbol",
                        chunk_id=str(chunk.get("chunk_id") or "") or None,
                        content_hash=str(chunk.get("content_hash") or "") or None,
                    )
                )
            if len(hits) >= 5:
                break
        if not hits:
            # Lightweight filesystem regex fallback within worktree text files
            pattern = re.compile(
                rf"\b(?:function|class|const|interface|type|enum)\s+{re.escape(symbol)}\b"
            )
            for path in sorted(self.worktree.rglob("*")):
                if not path.is_file():
                    continue
                if path.suffix.lower() not in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
                    continue
                try:
                    rel = path.relative_to(self.worktree).as_posix()
                except ValueError:
                    continue
                if any(part in {"node_modules", ".git", "dist", "build"} for part in path.parts):
                    continue
                try:
                    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    continue
                for i, line in enumerate(lines, start=1):
                    if pattern.search(line):
                        start = max(1, i - 5)
                        end = min(len(lines), i + 40)
                        snippet = "\n".join(lines[start - 1 : end])
                        tok = count_tokens(snippet, self._encoder)
                        hits.append(
                            EvidenceItem(
                                evidence_id=EvidenceItem.make_id(
                                    path=rel,
                                    start_line=start,
                                    end_line=end,
                                    text=snippet,
                                    source_tool="find_symbol",
                                ),
                                path=rel,
                                symbol=symbol,
                                start_line=start,
                                end_line=end,
                                text=snippet,
                                token_count=tok,
                                source_tool="find_symbol",
                            )
                        )
                        break
                if len(hits) >= 5:
                    break
        accepted = self._charge(hits)
        return ToolResult(
            tool_name="find_symbol",
            ok=True,
            evidence=accepted,
            message=f"found {len(accepted)} locations for {symbol}",
            raw={"symbol": symbol},
        )

    def _grep(self, args: dict[str, Any]) -> ToolResult:
        pattern = str(args.get("pattern") or "")
        if not pattern:
            raise ToolError("grep requires pattern")
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise ToolError(f"invalid regex: {exc}") from exc
        path_glob = str(args.get("path") or "")
        matches: list[EvidenceItem] = []
        used_tokens = 0
        root = self.worktree
        if path_glob:
            candidate_root = self._resolve_path(path_glob) if Path(path_glob).suffix else (
                self.worktree / path_glob
            )
            if candidate_root.is_file():
                files = [candidate_root]
            elif candidate_root.is_dir():
                files = sorted(p for p in candidate_root.rglob("*") if p.is_file())
            else:
                raise ToolError(f"grep path not found: {path_glob}")
        else:
            files = sorted(p for p in root.rglob("*") if p.is_file())

        for abs_path in files:
            if any(part in {"node_modules", ".git", "dist", "build"} for part in abs_path.parts):
                continue
            if abs_path.suffix.lower() not in {
                ".ts",
                ".tsx",
                ".js",
                ".jsx",
                ".mjs",
                ".cjs",
                ".json",
                ".md",
                ".yml",
                ".yaml",
            }:
                continue
            try:
                rel = abs_path.relative_to(self.worktree).as_posix()
                lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except (OSError, ValueError):
                continue
            for i, line in enumerate(lines, start=1):
                if not regex.search(line):
                    continue
                start = max(1, i - 2)
                end = min(len(lines), i + 2)
                snippet = "\n".join(lines[start - 1 : end])
                tok = count_tokens(snippet, self._encoder)
                if used_tokens + tok > self.max_grep_tokens:
                    accepted = self._charge(matches)
                    return ToolResult(
                        tool_name="grep",
                        ok=True,
                        evidence=accepted,
                        message="grep truncated by token cap",
                        raw={"pattern": pattern, "match_count": len(accepted)},
                    )
                matches.append(
                    EvidenceItem(
                        evidence_id=EvidenceItem.make_id(
                            path=rel,
                            start_line=start,
                            end_line=end,
                            text=snippet,
                            source_tool="grep",
                        ),
                        path=rel,
                        symbol=None,
                        start_line=start,
                        end_line=end,
                        text=snippet,
                        token_count=tok,
                        source_tool="grep",
                    )
                )
                used_tokens += tok
                if len(matches) >= self.max_grep_matches:
                    accepted = self._charge(matches)
                    return ToolResult(
                        tool_name="grep",
                        ok=True,
                        evidence=accepted,
                        message="grep truncated by match cap",
                        raw={"pattern": pattern, "match_count": len(accepted)},
                    )
        accepted = self._charge(matches)
        return ToolResult(
            tool_name="grep",
            ok=True,
            evidence=accepted,
            message=f"grep found {len(accepted)} matches",
            raw={"pattern": pattern, "match_count": len(accepted)},
        )


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "semantic_search",
            "description": "Semantic search over the assigned repository snapshot index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer"},
                    "max_tokens": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file or line range from the assigned snapshot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer"},
                    "end_line": {"type": "integer"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_symbol",
            "description": "Locate a function/class/symbol in the assigned snapshot.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Regex search over text files in the assigned snapshot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string"},
                },
                "required": ["pattern"],
            },
        },
    },
]
