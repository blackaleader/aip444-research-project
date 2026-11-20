"""Stage 6: Method A/B, tools, traces, and mocked end-to-end tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from repo_search.agent_prompts import SYSTEM_PROMPT_VERSION
from repo_search.chat_client import ChatError, ChatResponse, ChatToolCall, ChatUsage, OpenRouterChatClient
from repo_search.chunking import CHUNKER_VERSION, CodeChunk
from repo_search.embeddings import DEFAULT_EMBEDDING_MODEL
from repo_search.evidence import EvidenceLedger, EvidenceItem
from repo_search.method_a import run_method_a
from repo_search.method_b import run_method_b
from repo_search.repo_tools import SnapshotToolEnvironment, ToolError
from repo_search.retriever import SemanticRetriever
from repo_search.traces import scrub_secrets, write_trace
from repo_search.vector_index import NumpyVectorIndex

ROOT = Path(__file__).resolve().parents[2]


class FakeEmbedder:
    model = DEFAULT_EMBEDDING_MODEL

    def __init__(self, dim: int = 4) -> None:
        self.dim = dim
        self.query_count = 0

    def embed_query(self, query: str) -> list[float]:
        self.query_count += 1
        # Bias toward first vector for predictable ranking
        v = [0.0] * self.dim
        v[0] = 1.0
        return v


class ScriptedChat:
    """Deterministic chat completer for Method B tests."""

    def __init__(self, responses: list[ChatResponse]) -> None:
        self.responses = list(responses)
        self.calls = 0
        self.model = "openai/gpt-6-luna"
        self.messages_seen: list[list[dict]] = []

    def complete(self, messages, *, tools=None, tool_choice="auto") -> ChatResponse:
        self.messages_seen.append(list(messages))
        if self.calls >= len(self.responses):
            raise ChatError("unexpected extra LLM call")
        resp = self.responses[self.calls]
        self.calls += 1
        return resp


def _fixture_repo(tmp_path: Path) -> tuple[Path, SemanticRetriever, FakeEmbedder]:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "loader.ts").write_text(
        "export function loadExtensions() {\n  return true;\n}\n"
        "export function loadExtensionsCached() {\n  return loadExtensions();\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "packages.ts").write_text(
        "export class DefaultPackageManager {\n  filter() { return []; }\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("extension loading and packages\n", encoding="utf-8")

    chunks = [
        CodeChunk(
            chunk_id="c1",
            snapshot_sha="s" * 40,
            path="src/loader.ts",
            symbol="loadExtensions",
            start_line=1,
            end_line=3,
            text="export function loadExtensions() {\n  return true;\n}",
            token_count=12,
            content_hash="h1",
        ),
        CodeChunk(
            chunk_id="c2",
            snapshot_sha="s" * 40,
            path="src/packages.ts",
            symbol="DefaultPackageManager",
            start_line=1,
            end_line=3,
            text="export class DefaultPackageManager {\n  filter() { return []; }\n}",
            token_count=14,
            content_hash="h2",
        ),
        CodeChunk(
            chunk_id="c3",
            snapshot_sha="s" * 40,
            path="README.md",
            symbol=None,
            start_line=1,
            end_line=1,
            text="extension loading and packages",
            token_count=5,
            content_hash="h3",
        ),
    ]
    embeddings = [
        [1.0, 0.0, 0.0, 0.0],
        [0.2, 1.0, 0.0, 0.0],
        [0.5, 0.5, 0.0, 0.0],
    ]
    index = NumpyVectorIndex.build(
        chunk_objs=chunks,
        embeddings=embeddings,
        snapshot_sha="s" * 40,
        embedding_model=DEFAULT_EMBEDDING_MODEL,
        tokenizer="cl100k_base",
        chunking={},
        index_build_id="fixture-idx",
        chunker_version=CHUNKER_VERSION,
    )
    emb = FakeEmbedder()
    retriever = SemanticRetriever(index=index, embedder=emb, default_top_k=10, default_max_tokens=6000)
    return tmp_path, retriever, emb


def test_method_a_one_search_no_llm(tmp_path: Path) -> None:
    root, retriever, emb = _fixture_repo(tmp_path)
    prompt = "Improve extension loading so dependencies load lazily"
    result = run_method_a(task_prompt=prompt, retriever=retriever)
    assert result.semantic_search_count == 1
    assert result.tool_call_count == 1
    assert result.llm_call_count == 0
    assert result.query == prompt
    assert result.retrieval_trace["query_unchanged"] is True
    assert emb.query_count == 1
    assert result.evidence_pack.items
    assert result.evidence_pack.token_count <= 6000
    item = result.evidence_pack.items[0]
    assert item.path
    assert item.chunk_id
    assert item.source_tool == "one_shot_rag"
    assert "score" in item.to_dict()


def test_method_b_initial_search_counts_and_tools(tmp_path: Path) -> None:
    root, retriever, _ = _fixture_repo(tmp_path)
    ledger = EvidenceLedger(evidence_budget=6000)
    tools = SnapshotToolEnvironment(
        worktree=root,
        snapshot_sha="s" * 40,
        retriever=retriever,
        ledger=ledger,
        max_tool_calls=5,
    )
    # After initial search, model asks for read_file then finalizes
    read_resp = ChatResponse(
        message={},
        tool_calls=[
            ChatToolCall(
                id="1",
                name="read_file",
                arguments={"path": "src/loader.ts", "start_line": 1, "end_line": 4},
            )
        ],
        content=None,
        model="openai/gpt-6-luna",
        requested_model="openai/gpt-6-luna",
        usage=ChatUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15, requests=1),
        latency_ms=1.0,
        finish_reason="tool_calls",
    )
    # Capture evidence id after run via finalize using chunk from initial search
    finalize_resp = ChatResponse(
        message={"content": ""},
        tool_calls=[],
        content=json.dumps(
            {"action": "finalize", "evidence_ids": ["c1"], "reason": "evidence_sufficient"}
        ),
        model="openai/gpt-6-luna",
        requested_model="openai/gpt-6-luna",
        usage=ChatUsage(prompt_tokens=12, completion_tokens=8, total_tokens=20, requests=1),
        latency_ms=1.0,
        finish_reason="stop",
    )
    chat = ScriptedChat([read_resp, finalize_resp])
    prompt = "Improve extension loading"
    result = run_method_b(task_prompt=prompt, tools=tools, chat=chat)
    assert result.initial_query == prompt
    assert result.tool_call_count >= 2  # initial semantic + read_file
    assert result.tool_call_count <= 5
    assert tools.history[0].tool_name == "semantic_search"
    assert tools.history[0].arguments["query"] == prompt
    assert any(h.tool_name == "read_file" for h in tools.history)
    assert result.llm_call_count == 2
    assert result.stop_reason == "evidence_sufficient"
    assert result.planning_tokens > 0
    # evidence ids validated — c1 maps via known_evidence
    assert result.evidence_pack.items


def test_method_b_call_limit_enforced(tmp_path: Path) -> None:
    root, retriever, _ = _fixture_repo(tmp_path)
    tools = SnapshotToolEnvironment(
        worktree=root,
        snapshot_sha="s" * 40,
        retriever=retriever,
        ledger=EvidenceLedger(evidence_budget=6000),
        max_tool_calls=5,
    )
    # Initial search uses 1. Then request 5 more grep calls in one response — only 4 remain.
    multi = ChatResponse(
        message={},
        tool_calls=[
            ChatToolCall(id=str(i), name="grep", arguments={"pattern": "loadExtensions"})
            for i in range(5)
        ],
        content=None,
        model="openai/gpt-6-luna",
        requested_model="openai/gpt-6-luna",
        usage=ChatUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2, requests=1),
        latency_ms=1.0,
        finish_reason="tool_calls",
    )
    # After limit, model tries finalize
    fin = ChatResponse(
        message={},
        tool_calls=[],
        content=json.dumps(
            {"action": "finalize", "evidence_ids": [], "reason": "call_limit_reached"}
        ),
        model="openai/gpt-6-luna",
        requested_model="openai/gpt-6-luna",
        usage=ChatUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2, requests=1),
        latency_ms=1.0,
        finish_reason="stop",
    )
    # reason call_limit_reached is not in finalize allowlist; controller maps or uses budget reason
    chat = ScriptedChat([multi, fin])
    result = run_method_b(task_prompt="extension loading", tools=tools, chat=chat)
    assert result.tool_call_count == 5
    assert tools.remaining_calls() == 0


def test_all_four_tools_and_invalid_path(tmp_path: Path) -> None:
    root, retriever, _ = _fixture_repo(tmp_path)
    tools = SnapshotToolEnvironment(
        worktree=root,
        snapshot_sha="s" * 40,
        retriever=retriever,
        ledger=EvidenceLedger(evidence_budget=6000),
        max_tool_calls=5,
    )
    assert tools.execute("semantic_search", {"query": "extensions"}).ok
    assert tools.execute("read_file", {"path": "src/loader.ts"}).ok
    assert tools.execute("find_symbol", {"symbol": "loadExtensions"}).ok
    assert tools.execute("grep", {"pattern": "PackageManager"}).ok
    escaped = tools.execute("read_file", {"path": "../secret.txt"})
    assert escaped.ok is False
    assert "invalid path" in escaped.message or "escapes" in escaped.message
    assert tools.tool_call_count == 5
    with pytest.raises(ToolError, match="tool call limit"):
        tools.execute("read_file", {"path": "src/loader.ts"})


def test_evidence_budget_cannot_be_bypassed(tmp_path: Path) -> None:
    root, retriever, _ = _fixture_repo(tmp_path)
    tools = SnapshotToolEnvironment(
        worktree=root,
        snapshot_sha="s" * 40,
        retriever=retriever,
        ledger=EvidenceLedger(evidence_budget=20),
        max_tool_calls=5,
        max_read_tokens=50,
    )
    tools.execute("semantic_search", {"query": "extensions"})
    # Budget largely consumed; further reads may be truncated/rejected
    assert tools.ledger.cumulative_evidence_tokens <= 20


def test_shared_evidence_schema_and_trace_scrub(tmp_path: Path) -> None:
    root, retriever, _ = _fixture_repo(tmp_path)
    a = run_method_a(task_prompt="extensions", retriever=retriever)
    item = a.evidence_pack.items[0].to_dict()
    for key in (
        "evidence_id",
        "path",
        "symbol",
        "start_line",
        "end_line",
        "text",
        "token_count",
        "source_tool",
    ):
        assert key in item
    dirty = {
        "api_key": "sk-secretvalue1234567890",
        "note": "Bearer sk-abcdef1234567890xyz",
        "token_count": 3,
    }
    clean = scrub_secrets(dirty)
    assert "api_key" not in clean
    assert "sk-" not in json.dumps(clean)
    assert clean["token_count"] == 3
    path = write_trace(
        {"task_id": "t", "method": "one_shot_rag", "repetition": 1, "api_key": "sk-shouldgo"},
        directory=tmp_path / "traces",
        filename="t.json",
    )
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert "api_key" not in saved


def test_chat_client_refuses_model_substitution() -> None:
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "some-other-model",
                "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    client = OpenRouterChatClient(
        api_key="test",
        model="openai/gpt-6-luna",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        allow_model_mismatch=False,
    )
    with pytest.raises(ChatError, match="model mismatch"):
        client.complete([{"role": "user", "content": "hi"}], tools=None, tool_choice=None)
    client.close()


def test_ground_truth_not_in_method_a_path() -> None:
    from repo_search.benchmark_loader import method_input_bundle

    payload = method_input_bundle("pi_lazy_extension_loading")
    blob = json.dumps(payload)
    assert "ground_truth" not in blob
    assert "required_files" not in blob


def test_system_prompt_versioned() -> None:
    assert SYSTEM_PROMPT_VERSION.startswith("pilot-v1.0")
