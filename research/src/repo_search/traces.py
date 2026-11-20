"""Structured execution-trace persistence (no credentials)."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{10,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.I),
    re.compile(r"OPENROUTER_API_KEY\s*=\s*\S+"),
    re.compile(r"LLM_API_KEY\s*=\s*\S+"),
)


def scrub_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: scrub_secrets(v)
            for k, v in obj.items()
            if k.lower() not in {"api_key", "authorization", "secret", "token"}
            or k.lower() in {"token_count", "prompt_tokens", "completion_tokens", "total_tokens"}
        }
    if isinstance(obj, list):
        return [scrub_secrets(x) for x in obj]
    if isinstance(obj, str):
        text = obj
        for pat in SECRET_PATTERNS:
            text = pat.sub("[REDACTED]", text)
        return text
    return obj


def default_trace_dir(research_root: Path) -> Path:
    return research_root / "results" / "raw" / "traces"


def write_trace(
    record: dict[str, Any],
    *,
    directory: Path,
    filename: str | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    safe = scrub_secrets(record)
    name = filename or (
        f"{safe.get('task_id','task')}__{safe.get('method','method')}__"
        f"r{safe.get('repetition',0)}__{int(time.time())}.json"
    )
    path = directory / name
    path.write_text(json.dumps(safe, indent=2, ensure_ascii=False), encoding="utf-8")
    # Also append JSONL index
    jsonl = directory / "runs.jsonl"
    with jsonl.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(safe, ensure_ascii=False) + "\n")
    return path
