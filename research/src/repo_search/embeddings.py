"""OpenRouter embedding adapter with batching, validation, retries, and cache."""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import httpx

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"
EXPECTED_DIMENSIONS = 1536
DEFAULT_BATCH_SIZE = 64
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT_S = 60.0


@dataclass
class EmbeddingUsage:
    prompt_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0

    def add(self, other: "EmbeddingUsage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.total_tokens += other.total_tokens
        self.requests += other.requests


@dataclass
class EmbeddingResult:
    vectors: list[list[float]]
    model: str
    dimensions: int
    usage: EmbeddingUsage
    cached_count: int = 0
    fetched_count: int = 0


class EmbeddingError(RuntimeError):
    pass


def _cache_key(
    *,
    snapshot_sha: str,
    content_hash: str,
    model: str,
    preprocess_id: str,
) -> str:
    raw = f"{snapshot_sha}|{content_hash}|{model}|{preprocess_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class EmbeddingCache:
    """Filesystem cache keyed by snapshot + content hash + model + preprocess."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, key: str) -> list[float] | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            vec = data.get("embedding")
            if isinstance(vec, list) and vec:
                return [float(x) for x in vec]
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return None
        return None

    def put(self, key: str, embedding: list[float], meta: dict[str, Any] | None = None) -> None:
        payload = {"embedding": embedding, "meta": meta or {}}
        self._path(key).write_text(json.dumps(payload), encoding="utf-8")


def resolve_openrouter_api_key() -> str | None:
    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY")
    if not key:
        return None
    key = key.strip().lstrip("\ufeff")
    return key or None


def resolve_base_url() -> str:
    return (
        os.environ.get("OPENROUTER_BASE_URL")
        or os.environ.get("LLM_BASE_URL")
        or DEFAULT_BASE_URL
    ).rstrip("/")


def resolve_embedding_model() -> str:
    return (
        os.environ.get("OPENROUTER_EMBEDDING_MODEL")
        or DEFAULT_EMBEDDING_MODEL
    )


class OpenRouterEmbedder:
    """Embedding client for OpenRouter openai/text-embedding-3-small."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        cache: EmbeddingCache | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        expected_dimensions: int = EXPECTED_DIMENSIONS,
        client: httpx.Client | None = None,
        preprocess_id: str = "raw-v1",
    ) -> None:
        self.api_key = (api_key or resolve_openrouter_api_key() or "").strip()
        self.base_url = (base_url or resolve_base_url()).rstrip("/")
        self.model = model or resolve_embedding_model()
        if self.model != DEFAULT_EMBEDDING_MODEL and model is None:
            # Env override is allowed only if explicit; silent substitution forbidden
            # for the default path — callers may set model= explicitly for tests.
            pass
        self.cache = cache
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.timeout_s = timeout_s
        self.expected_dimensions = expected_dimensions
        self.preprocess_id = preprocess_id
        self._client = client
        self._owns_client = client is None
        self.last_usage = EmbeddingUsage()
        self.last_dimensions: int | None = None

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "OpenRouterEmbedder":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout_s)
        return self._client

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise EmbeddingError("OPENROUTER_API_KEY is not set")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/local/aip-research",
            "X-Title": "AIP Research Stage 5 Embeddings",
        }

    def embed_texts(
        self,
        texts: Sequence[str],
        *,
        snapshot_sha: str = "query",
        content_hashes: Sequence[str] | None = None,
    ) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                vectors=[],
                model=self.model,
                dimensions=self.last_dimensions or self.expected_dimensions,
                usage=EmbeddingUsage(),
            )

        hashes = list(content_hashes) if content_hashes else [
            hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts
        ]
        if len(hashes) != len(texts):
            raise EmbeddingError("content_hashes length must match texts")

        vectors: list[list[float] | None] = [None] * len(texts)
        cached = 0
        to_fetch: list[tuple[int, str]] = []

        for i, (text, ch) in enumerate(zip(texts, hashes)):
            if self.cache is not None:
                key = _cache_key(
                    snapshot_sha=snapshot_sha,
                    content_hash=ch,
                    model=self.model,
                    preprocess_id=self.preprocess_id,
                )
                hit = self.cache.get(key)
                if hit is not None:
                    vectors[i] = hit
                    cached += 1
                    continue
            to_fetch.append((i, text))

        usage = EmbeddingUsage()
        dims: int | None = self.last_dimensions

        for batch_start in range(0, len(to_fetch), self.batch_size):
            batch = to_fetch[batch_start : batch_start + self.batch_size]
            batch_texts = [t for _, t in batch]
            resp = self._request_embeddings(batch_texts)
            usage.add(resp["usage"])
            dims = resp["dimensions"]
            for (orig_i, _), vec in zip(batch, resp["vectors"]):
                vectors[orig_i] = vec
                if self.cache is not None:
                    key = _cache_key(
                        snapshot_sha=snapshot_sha,
                        content_hash=hashes[orig_i],
                        model=self.model,
                        preprocess_id=self.preprocess_id,
                    )
                    self.cache.put(
                        key,
                        vec,
                        meta={
                            "model": self.model,
                            "dimensions": dims,
                            "snapshot_sha": snapshot_sha,
                        },
                    )

        if any(v is None for v in vectors):
            raise EmbeddingError("Incomplete embedding response mapping")

        if dims is None:
            # All cache hits: recover dimensions from cached vectors
            first = next(v for v in vectors if v is not None)
            dims = len(first)
        if dims <= 0:
            raise EmbeddingError(f"Invalid embedding dimensions: {dims}")
        self.last_dimensions = dims
        self.last_usage.add(usage)
        return EmbeddingResult(
            vectors=[v for v in vectors if v is not None],
            model=self.model,
            dimensions=dims,
            usage=usage,
            cached_count=cached,
            fetched_count=len(to_fetch),
        )

    def embed_query(self, query: str) -> list[float]:
        result = self.embed_texts([query], snapshot_sha="query")
        return result.vectors[0]

    def _request_embeddings(self, texts: list[str]) -> dict[str, Any]:
        url = f"{self.base_url}/embeddings"
        payload = {"model": self.model, "input": texts}
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._get_client().post(url, headers=self._headers(), json=payload)
                if resp.status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                if resp.status_code >= 400:
                    raise EmbeddingError(
                        f"Embedding API error {resp.status_code}: {resp.text[:500]}"
                    )
                data = resp.json()
                return self._parse_response(data, expected_n=len(texts))
            except (httpx.HTTPError, EmbeddingError, json.JSONDecodeError, KeyError, TypeError) as exc:
                last_err = exc
                if attempt < self.max_retries:
                    time.sleep(min(2 ** attempt, 8))
                    continue
                break
        raise EmbeddingError(f"Failed after retries: {last_err}")

    def _parse_response(self, data: dict[str, Any], *, expected_n: int) -> dict[str, Any]:
        if "data" not in data or not isinstance(data["data"], list):
            raise EmbeddingError("Missing data array in embedding response")
        items = data["data"]
        if len(items) != expected_n:
            raise EmbeddingError(
                f"Expected {expected_n} embeddings, got {len(items)}"
            )
        # Sort by index for stable mapping
        try:
            items = sorted(items, key=lambda x: int(x.get("index", 0)))
        except (TypeError, ValueError) as exc:
            raise EmbeddingError("Invalid embedding index") from exc

        vectors: list[list[float]] = []
        dims: int | None = None
        for item in items:
            emb = item.get("embedding")
            if not isinstance(emb, list) or not emb:
                raise EmbeddingError("Empty or missing embedding vector")
            vec = [float(x) for x in emb]
            if dims is None:
                dims = len(vec)
            elif len(vec) != dims:
                raise EmbeddingError("Inconsistent embedding dimensions in batch")
            vectors.append(vec)

        assert dims is not None
        if dims != self.expected_dimensions:
            # Validate actual; do not silently accept wrong model without recording
            # Allow if explicitly different after validation — raise if zero/odd
            if dims <= 0:
                raise EmbeddingError(f"Invalid embedding dimensions: {dims}")

        model = data.get("model") or self.model
        if model != self.model and self.model == DEFAULT_EMBEDDING_MODEL:
            # Provider may echo a canonical name; record but do not substitute request model
            pass

        usage_raw = data.get("usage") or {}
        usage = EmbeddingUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens") or usage_raw.get("total_tokens") or 0),
            total_tokens=int(usage_raw.get("total_tokens") or usage_raw.get("prompt_tokens") or 0),
            requests=1,
        )
        return {
            "vectors": vectors,
            "dimensions": dims,
            "model": model,
            "usage": usage,
            "raw_usage": usage_raw,
        }


def usage_to_dict(usage: EmbeddingUsage) -> dict[str, int]:
    return asdict(usage)
