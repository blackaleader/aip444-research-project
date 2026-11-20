"""OpenRouter chat-completions client for Method B (no silent model substitution)."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Sequence

import httpx

from repo_search.embeddings import resolve_base_url, resolve_openrouter_api_key

DEFAULT_PRIMARY_CHAT_MODEL = "openai/gpt-6-luna"
DEFAULT_MAX_COMPLETION_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.0
DEFAULT_TIMEOUT_S = 90.0
DEFAULT_MAX_RETRIES = 2


class ChatError(RuntimeError):
    pass


@dataclass
class ChatUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0
    cost: float | None = None

    def add(self, other: "ChatUsage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.requests += other.requests
        if other.cost is not None:
            self.cost = (self.cost or 0.0) + other.cost


@dataclass
class ChatToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResponse:
    message: dict[str, Any]
    tool_calls: list[ChatToolCall]
    content: str | None
    model: str
    requested_model: str
    usage: ChatUsage
    latency_ms: float
    finish_reason: str | None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "model": self.model,
            "requested_model": self.requested_model,
            "finish_reason": self.finish_reason,
            "latency_ms": self.latency_ms,
            "usage": asdict(self.usage),
            "tool_calls": [
                {"id": t.id, "name": t.name, "arguments": t.arguments} for t in self.tool_calls
            ],
        }


def resolve_primary_chat_model() -> str:
    return (
        os.environ.get("OPENROUTER_PRIMARY_CHAT_MODEL")
        or os.environ.get("LLM_MODEL")
        or DEFAULT_PRIMARY_CHAT_MODEL
    )


class OpenRouterChatClient:
    """Chat client pinned to a requested model; never silently substitutes."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
        client: httpx.Client | None = None,
        allow_model_mismatch: bool = False,
    ) -> None:
        self.api_key = (api_key or resolve_openrouter_api_key() or "").strip()
        self.base_url = (base_url or resolve_base_url()).rstrip("/")
        self.model = model or resolve_primary_chat_model()
        self.temperature = temperature
        self.max_completion_tokens = max_completion_tokens
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.allow_model_mismatch = allow_model_mismatch
        self._client = client
        self._owns_client = client is None
        self.total_usage = ChatUsage()

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "OpenRouterChatClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout_s)
        return self._client

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ChatError("OPENROUTER_API_KEY is not set")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/local/aip-research",
            "X-Title": "AIP Research Stage 6 Agent",
        }

    def complete(
        self,
        messages: Sequence[dict[str, Any]],
        *,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = "auto",
    ) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": self.temperature,
            "max_tokens": self.max_completion_tokens,
        }
        if tools:
            payload["tools"] = list(tools)
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice

        url = f"{self.base_url}/chat/completions"
        last_err: Exception | None = None
        t0 = time.perf_counter()
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._get_client().post(url, headers=self._headers(), json=payload)
                if resp.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                if resp.status_code >= 400:
                    raise ChatError(f"Chat API error {resp.status_code}: {resp.text[:500]}")
                data = resp.json()
                parsed = self._parse(data, latency_ms=(time.perf_counter() - t0) * 1000)
                self.total_usage.add(parsed.usage)
                return parsed
            except (httpx.HTTPError, ChatError, json.JSONDecodeError, KeyError, TypeError) as exc:
                last_err = exc
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                break
        raise ChatError(f"Chat completion failed after retries: {last_err}")

    def _parse(self, data: dict[str, Any], *, latency_ms: float) -> ChatResponse:
        returned_model = str(data.get("model") or self.model)
        if (
            not self.allow_model_mismatch
            and returned_model
            and returned_model != self.model
            and not returned_model.startswith(self.model.split("/")[-1])
        ):
            # Record mismatch; do not silently continue as if substitution was intended
            # OpenRouter may echo provider-specific aliases — accept only if requested model
            # appears in the returned string.
            if self.model not in returned_model and returned_model not in self.model:
                raise ChatError(
                    f"model mismatch: requested {self.model!r}, got {returned_model!r}; "
                    "refusing silent substitution"
                )

        choices = data.get("choices") or []
        if not choices:
            raise ChatError("chat response missing choices")
        choice = choices[0]
        message = choice.get("message") or {}
        tool_calls_raw = message.get("tool_calls") or []
        tool_calls: list[ChatToolCall] = []
        for tc in tool_calls_raw:
            fn = tc.get("function") or {}
            name = str(fn.get("name") or "")
            raw_args = fn.get("arguments") or "{}"
            if isinstance(raw_args, dict):
                args = raw_args
            else:
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError as exc:
                    raise ChatError(f"malformed tool arguments for {name}: {exc}") from exc
            if not isinstance(args, dict):
                raise ChatError(f"tool arguments must be object for {name}")
            tool_calls.append(
                ChatToolCall(id=str(tc.get("id") or f"call_{len(tool_calls)}"), name=name, arguments=args)
            )

        usage_raw = data.get("usage") or {}
        cost = None
        if "cost" in usage_raw:
            try:
                cost = float(usage_raw["cost"])
            except (TypeError, ValueError):
                cost = None
        usage = ChatUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens") or 0),
            completion_tokens=int(usage_raw.get("completion_tokens") or 0),
            total_tokens=int(usage_raw.get("total_tokens") or 0),
            requests=1,
            cost=cost,
        )
        return ChatResponse(
            message=message,
            tool_calls=tool_calls,
            content=message.get("content"),
            model=returned_model,
            requested_model=self.model,
            usage=usage,
            latency_ms=latency_ms,
            finish_reason=choice.get("finish_reason"),
            raw={"id": data.get("id"), "usage": usage_raw},
        )
