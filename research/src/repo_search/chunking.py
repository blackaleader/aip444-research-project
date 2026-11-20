"""Symbol-aware chunking with line-based fallback and tiktoken accounting."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import tiktoken

CHUNKER_VERSION = "pilot-v1.0-chunker-1"
DEFAULT_TOKENIZER = "cl100k_base"
DEFAULT_MAX_CHUNK_TOKENS = 800
DEFAULT_OVERLAP_TOKENS = 100

_SYMBOL_START = re.compile(
    r"^(?:"
    r"\s*(?:export\s+)?(?:async\s+)?(?:function\*?|class|interface|type|enum|namespace)\s+\w+"
    r"|export\s+(?:default\s+)?(?:async\s+)?function\*?\s+\w+"
    r"|export\s+(?:default\s+)?class\s+\w+"
    r"|const\s+\w+\s*=\s*(?:async\s+)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"
    r")"
)


@dataclass(frozen=True)
class CodeChunk:
    chunk_id: str
    snapshot_sha: str
    path: str
    symbol: str | None
    start_line: int
    end_line: int
    text: str
    token_count: int
    content_hash: str
    chunker_version: str = CHUNKER_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_encoder(tokenizer_name: str = DEFAULT_TOKENIZER) -> tiktoken.Encoding:
    return tiktoken.get_encoding(tokenizer_name)


def count_tokens(text: str, encoder: tiktoken.Encoding | None = None) -> int:
    enc = encoder or get_encoder()
    return len(enc.encode(text))


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_chunk_id(snapshot_sha: str, path: str, start_line: int, end_line: int, text: str) -> str:
    digest = content_hash(f"{snapshot_sha}|{path}|{start_line}|{end_line}|{text}")[:16]
    safe_path = path.replace("/", "__")
    return f"{snapshot_sha[:12]}:{safe_path}:{start_line}-{end_line}:{digest}"


def _read_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in raw[:4096]:
        return None
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _symbol_breakpoints(lines: list[str]) -> list[int]:
    """1-based line numbers that start a new symbol region (including 1)."""
    points = [1]
    for i, line in enumerate(lines, start=1):
        if i == 1:
            continue
        if _SYMBOL_START.match(line):
            points.append(i)
    return points


def _windows_from_points(
    lines: list[str],
    points: list[int],
    encoder: tiktoken.Encoding,
    max_tokens: int,
    overlap_tokens: int,
) -> list[tuple[int, int, str | None]]:
    """Return (start_line, end_line, symbol_hint) windows."""
    n = len(lines)
    if n == 0:
        return []
    points = sorted(set(points))
    if points[-1] != n + 1:
        # sentinel end
        ends = points[1:] + [n + 1]
    else:
        ends = points[1:]
        points = points[:-1]

    regions: list[tuple[int, int, str | None]] = []
    for start, end_excl in zip(points, ends):
        end = end_excl - 1
        region_lines = lines[start - 1 : end]
        symbol = None
        m = _SYMBOL_START.match(region_lines[0]) if region_lines else None
        if m:
            # crude symbol extract
            parts = region_lines[0].strip().split()
            for j, p in enumerate(parts):
                if p in {"function", "function*", "class", "interface", "type", "enum", "const", "namespace"}:
                    if j + 1 < len(parts):
                        symbol = parts[j + 1].split("(")[0].split("<")[0].rstrip("{=")
                    break
        text = "\n".join(region_lines)
        tok = count_tokens(text, encoder)
        if tok <= max_tokens:
            regions.append((start, end, symbol))
            continue
        # split oversized region with line fallback
        regions.extend(
            _line_fallback_windows(lines, start, end, symbol, encoder, max_tokens, overlap_tokens)
        )
    return regions


def _line_fallback_windows(
    lines: list[str],
    start: int,
    end: int,
    symbol: str | None,
    encoder: tiktoken.Encoding,
    max_tokens: int,
    overlap_tokens: int,
) -> list[tuple[int, int, str | None]]:
    out: list[tuple[int, int, str | None]] = []
    i = start
    while i <= end:
        j = i
        cur: list[str] = []
        cur_tok = 0
        while j <= end:
            line = lines[j - 1]
            line_tok = count_tokens(line + "\n", encoder)
            if cur and cur_tok + line_tok > max_tokens:
                break
            cur.append(line)
            cur_tok += line_tok
            j += 1
            if cur_tok >= max_tokens:
                break
        if not cur:
            # single oversized line
            out.append((i, i, symbol))
            i += 1
            continue
        out.append((i, j - 1, symbol))
        if j > end:
            break
        # overlap by tokens: step back lines until overlap budget filled
        if overlap_tokens <= 0:
            i = j
            continue
        back = j - 1
        acc = 0
        while back > i and acc < overlap_tokens:
            acc += count_tokens(lines[back - 1] + "\n", encoder)
            back -= 1
        i = max(back + 1, i + 1)
        if i >= j:
            i = j
    return out


def chunk_file(
    *,
    abs_path: Path,
    rel_path: str,
    snapshot_sha: str,
    max_chunk_tokens: int = DEFAULT_MAX_CHUNK_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    tokenizer_name: str = DEFAULT_TOKENIZER,
    encoder: tiktoken.Encoding | None = None,
) -> list[CodeChunk]:
    text = _read_text(abs_path)
    if text is None:
        return []
    # Normalize newlines for stable hashing
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if len(lines) == 1 and lines[0] == "":
        return []
    enc = encoder or get_encoder(tokenizer_name)
    use_symbol = abs_path.suffix.lower() in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}
    if use_symbol:
        points = _symbol_breakpoints(lines)
        windows = _windows_from_points(lines, points, enc, max_chunk_tokens, overlap_tokens)
    else:
        windows = _line_fallback_windows(
            lines, 1, len(lines), None, enc, max_chunk_tokens, overlap_tokens
        )

    chunks: list[CodeChunk] = []
    for start, end, symbol in windows:
        chunk_text = "\n".join(lines[start - 1 : end])
        if not chunk_text.strip():
            continue
        tok = count_tokens(chunk_text, enc)
        ch = content_hash(chunk_text)
        cid = make_chunk_id(snapshot_sha, rel_path, start, end, chunk_text)
        chunks.append(
            CodeChunk(
                chunk_id=cid,
                snapshot_sha=snapshot_sha,
                path=rel_path,
                symbol=symbol,
                start_line=start,
                end_line=end,
                text=chunk_text,
                token_count=tok,
                content_hash=ch,
            )
        )
    return chunks
