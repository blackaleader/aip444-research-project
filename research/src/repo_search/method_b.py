"""Method B — agent-directed iterative search with OpenRouter chat + tools."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from repo_search.agent_prompts import SYSTEM_PROMPT, system_prompt_meta
from repo_search.chat_client import ChatResponse, OpenRouterChatClient
from repo_search.evidence import EvidenceItem, EvidenceLedger, EvidencePack, pack_from_items
from repo_search.repo_tools import TOOL_SCHEMAS, SnapshotToolEnvironment, ToolError


class ChatCompleter(Protocol):
    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = "auto",
    ) -> ChatResponse: ...


STOP_REASONS = frozenset(
    {
        "evidence_sufficient",
        "no_new_relevant_evidence",
        "call_limit_reached",
        "evidence_budget_exhausted",
        "tool_or_model_error",
    }
)


@dataclass
class MethodBResult:
    evidence_pack: EvidencePack
    stop_reason: str
    tool_call_count: int
    llm_call_count: int
    initial_query: str
    latency_ms: float
    ledger: EvidenceLedger
    tool_trace: list[dict[str, Any]]
    llm_trace: list[dict[str, Any]]
    planning_tokens: int
    completion_tokens: int
    requested_model: str | None
    returned_model: str | None
    system_prompt_meta: dict[str, str]
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": "agent_directed",
            "stop_reason": self.stop_reason,
            "tool_call_count": self.tool_call_count,
            "llm_call_count": self.llm_call_count,
            "initial_query": self.initial_query,
            "latency_ms": self.latency_ms,
            "evidence_pack": self.evidence_pack.to_dict(),
            "evidence_accounting": {
                **self.ledger.summary(),
                "final_evidence_pack_tokens": self.evidence_pack.token_count,
                "agent_planning_input_tokens": self.planning_tokens,
                "agent_output_tokens": self.completion_tokens,
            },
            "tool_trace": self.tool_trace,
            "llm_trace": self.llm_trace,
            "requested_model": self.requested_model,
            "returned_model": self.returned_model,
            "system_prompt": self.system_prompt_meta,
            "errors": self.errors,
        }


def _summarize_evidence_for_llm(items: list[EvidenceItem], *, limit: int = 12) -> str:
    rows = []
    for item in items[:limit]:
        preview = item.text.replace("\n", " ")[:180]
        rows.append(
            {
                "evidence_id": item.evidence_id,
                "chunk_id": item.chunk_id,
                "path": item.path,
                "symbol": item.symbol,
                "start_line": item.start_line,
                "end_line": item.end_line,
                "token_count": item.token_count,
                "source_tool": item.source_tool,
                "score": item.score,
                "preview": preview,
            }
        )
    return json.dumps(rows, ensure_ascii=False)


def _parse_finalize(content: str | None) -> dict[str, Any] | None:
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # try to find JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
        else:
            return None
    if isinstance(data, dict) and data.get("action") == "finalize":
        return data
    return None


def run_method_b(
    *,
    task_prompt: str,
    tools: SnapshotToolEnvironment,
    chat: ChatCompleter,
    max_llm_rounds: int = 6,
) -> MethodBResult:
    """
    Initial semantic search with exact prompt (counts as tool call #1),
    then iterative LLM-directed tool use within budgets.
    """
    t0 = time.perf_counter()
    errors: list[str] = []
    llm_trace: list[dict[str, Any]] = []
    planning_tokens = 0
    completion_tokens = 0
    requested_model = getattr(chat, "model", None)
    returned_model: str | None = None
    stop_reason = "tool_or_model_error"
    prompt_meta = system_prompt_meta()

    # 1) Mandatory initial semantic search with unchanged prompt
    try:
        initial = tools.execute("semantic_search", {"query": task_prompt})
    except ToolError as exc:
        errors.append(str(exc))
        return MethodBResult(
            evidence_pack=EvidencePack(),
            stop_reason="tool_or_model_error",
            tool_call_count=tools.tool_call_count,
            llm_call_count=0,
            initial_query=task_prompt,
            latency_ms=(time.perf_counter() - t0) * 1000,
            ledger=tools.ledger,
            tool_trace=[h.to_dict() for h in tools.history],
            llm_trace=[],
            planning_tokens=0,
            completion_tokens=0,
            requested_model=requested_model if isinstance(requested_model, str) else None,
            returned_model=None,
            system_prompt_meta=prompt_meta,
            errors=errors,
        )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Task:\n"
                f"{task_prompt}\n\n"
                "An initial semantic_search was already executed with this exact task prompt "
                f"(tool call 1/{tools.max_tool_calls}). Results:\n"
                f"{_summarize_evidence_for_llm(initial.evidence)}\n\n"
                f"Remaining tool calls: {tools.remaining_calls()}. "
                f"Remaining evidence tokens: {tools.ledger.remaining()}.\n"
                "Continue searching if needed, then finalize with verified evidence_ids."
            ),
        },
    ]

    selected_ids: list[str] = []
    llm_calls = 0

    for _round in range(max_llm_rounds):
        if tools.ledger.remaining() <= 0:
            stop_reason = "evidence_budget_exhausted"
            break
        if tools.remaining_calls() <= 0:
            stop_reason = "call_limit_reached"
            break

        try:
            response = chat.complete(messages, tools=TOOL_SCHEMAS, tool_choice="auto")
        except Exception as exc:  # noqa: BLE001 — record and stop
            errors.append(f"llm_error: {exc}")
            stop_reason = "tool_or_model_error"
            break

        llm_calls += 1
        returned_model = response.model
        planning_tokens += response.usage.prompt_tokens
        completion_tokens += response.usage.completion_tokens
        llm_trace.append(response.to_dict())

        if response.tool_calls:
            # OpenAI-style assistant message with tool_calls
            messages.append(
                {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in response.tool_calls
                    ],
                }
            )
            for tc in response.tool_calls:
                if tools.remaining_calls() <= 0:
                    stop_reason = "call_limit_reached"
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps({"ok": False, "message": "call limit reached"}),
                        }
                    )
                    continue
                if tools.ledger.remaining() <= 0:
                    stop_reason = "evidence_budget_exhausted"
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(
                                {"ok": False, "message": "evidence budget exhausted"}
                            ),
                        }
                    )
                    continue
                try:
                    result = tools.execute(tc.name, tc.arguments)
                    payload = {
                        "ok": result.ok,
                        "message": result.message,
                        "evidence": [
                            {
                                "evidence_id": e.evidence_id,
                                "chunk_id": e.chunk_id,
                                "path": e.path,
                                "symbol": e.symbol,
                                "start_line": e.start_line,
                                "end_line": e.end_line,
                                "token_count": e.token_count,
                            }
                            for e in result.evidence
                        ],
                        "remaining_calls": tools.remaining_calls(),
                        "remaining_evidence_tokens": tools.ledger.remaining(),
                    }
                except ToolError as exc:
                    payload = {"ok": False, "message": str(exc)}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(payload),
                    }
                )
            if stop_reason in {"call_limit_reached", "evidence_budget_exhausted"}:
                break
            continue

        # No tool calls — check finalize
        finalize = _parse_finalize(response.content)
        if finalize:
            reason = str(finalize.get("reason") or "evidence_sufficient")
            if reason not in {"evidence_sufficient", "no_new_relevant_evidence"}:
                reason = "evidence_sufficient"
            stop_reason = reason
            raw_ids = finalize.get("evidence_ids") or []
            if isinstance(raw_ids, list):
                selected_ids = [str(x) for x in raw_ids]
            break

        # Model returned prose without tools/finalize — ask once more via message
        messages.append({"role": "assistant", "content": response.content or ""})
        messages.append(
            {
                "role": "user",
                "content": (
                    "Respond with either tool calls or a finalize JSON object using only "
                    "evidence_ids you have received from tools."
                ),
            }
        )
    else:
        if stop_reason == "tool_or_model_error":
            stop_reason = (
                "call_limit_reached"
                if tools.remaining_calls() <= 0
                else "no_new_relevant_evidence"
            )

    # Build final pack from validated evidence only
    pack_items: list[EvidenceItem] = []
    if selected_ids:
        for eid in selected_ids:
            item = tools.known_evidence.get(eid)
            if item is not None:
                pack_items.append(item)
    if not pack_items:
        # Fallback: use all charged excerpts (still verified tool output)
        pack_items = list(tools.ledger.excerpts)

    # Deduplicate by evidence_id while preserving order for final pack
    seen: set[str] = set()
    deduped: list[EvidenceItem] = []
    for item in pack_items:
        if item.evidence_id in seen:
            continue
        seen.add(item.evidence_id)
        deduped.append(item)

    pack = pack_from_items(deduped, max_tokens=tools.ledger.evidence_budget)
    if stop_reason not in STOP_REASONS:
        stop_reason = "tool_or_model_error"

    return MethodBResult(
        evidence_pack=pack,
        stop_reason=stop_reason,
        tool_call_count=tools.tool_call_count,
        llm_call_count=llm_calls,
        initial_query=task_prompt,
        latency_ms=(time.perf_counter() - t0) * 1000,
        ledger=tools.ledger,
        tool_trace=[h.to_dict() for h in tools.history],
        llm_trace=llm_trace,
        planning_tokens=planning_tokens,
        completion_tokens=completion_tokens,
        requested_model=requested_model if isinstance(requested_model, str) else None,
        returned_model=returned_model,
        system_prompt_meta=prompt_meta,
        errors=errors,
    )
