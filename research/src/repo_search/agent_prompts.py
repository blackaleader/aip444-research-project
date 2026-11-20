"""Versioned Method B system prompts."""

from __future__ import annotations

import hashlib

SYSTEM_PROMPT_VERSION = "pilot-v1.0-agent-system-1"

SYSTEM_PROMPT = """You are a repository search agent gathering evidence for a software-engineering task.

Rules:
1. You may only use these tools: semantic_search, read_file, find_symbol, grep.
2. Stay inside the assigned repository snapshot. Do not invent files, symbols, paths, or source text.
3. Prefer precise follow-up searches that fill missing context.
4. Evidence budgets and tool-call limits are enforced externally; stop when you have enough verified evidence.
5. When finished, respond with a JSON object only (no markdown) of the form:
   {"action":"finalize","evidence_ids":["..."],"reason":"evidence_sufficient"}
   Use evidence_ids from tool results only (evidence_id or chunk_id values you actually received).
6. Valid stop reasons: evidence_sufficient, no_new_relevant_evidence.
7. Do not request ground truth, diffs, target commits, or evaluation labels.
"""


def system_prompt_hash() -> str:
    return hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:16]


def system_prompt_meta() -> dict[str, str]:
    return {
        "system_prompt_version": SYSTEM_PROMPT_VERSION,
        "system_prompt_hash": system_prompt_hash(),
    }
