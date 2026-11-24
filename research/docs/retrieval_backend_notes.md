# Retrieval Backend Notes (T1 — Semantic Code Retrieval)

**Workstream:** T1 — Semantic Code Retrieval (RAG)
**Author:** Arman Ataeipour
**implementation_origin:** `teammate_1`
**Protocol:** `pilot-v1.0` (frozen — no retrieval parameters were changed in this delivery)
**Scope:** Validation, search CLI, smoke tests, and documentation for the **shared** Stage 5 semantic retriever used identically by Method A and Method B.

---

## 1. What this delivery contains

| Item | Path |
|---|---|
| Search helpers (index resolution, payload building, schema validation) | `src/repo_search/search_cli.py` |
| Search CLI — `search(query, top_k, max_tokens)` from the command line | `scripts/search_index.py` |
| T1 smoke tests (schema conformance, determinism, dedupe, budgets) | `tests/unit/test_retrieval_t1.py` |
| This document | `docs/retrieval_backend_notes.md` |

The Stage 5 implementation (`retriever.py`, `embeddings.py`, `vector_index.py`,
`chunking.py`, `corpus_scan.py`, `corpus_build.py`) is **unchanged**. This
delivery wraps and validates it; it does not replace or fork it, so Method A/B
parity is preserved.

---

## 2. Shared interface contract

```python
search(query: str, top_k: int, max_tokens: int) -> list[RetrievedChunk]
```

- Implemented by `repo_search.retriever.SemanticRetriever` (Stage 5, unchanged).
- Both experimental methods use the **same** retriever, index, and embedder.
  The methods differ only in search strategy (one-shot vs iterative).
- Each `RetrievedChunk` carries stable metadata and validates against
  `schemas/retrieved_chunk.schema.json` (11 required fields): `chunk_id`,
  `snapshot_sha`, `path`, `symbol` (nullable), `start_line`, `end_line`,
  `text`, `token_count`, `content_hash`, `chunker_version`, `score`.
- Ranking: cosine similarity, descending; deterministic tie-break by
  `(path, start_line, chunk_id)`.
- Budget: results are deduplicated by chunk id and `(path, start_line,
  end_line)` span, then greedily selected under `max_tokens`
  (`cl100k_base` counts); a chunk that would exceed the remaining budget is
  skipped and later smaller chunks may still be selected. `top_k <= 0` or
  `max_tokens <= 0` returns `[]`.

---

## 3. Embedding model investigation

Pinned model: **`openai/text-embedding-3-small` via OpenRouter** (1536
dimensions, validated by the Stage 5 live probe). Alternatives considered for
repository-level code retrieval:

| Model | Type | Observations for this project |
|---|---|---|
| `openai/text-embedding-3-small` (pinned) | General text, strong on code | Already live-probed and indexed for both pilots; low cost; available through the project's single provider (OpenRouter); 1536-dim keeps NumPy indexes small |
| `openai/text-embedding-3-large` | General text | Higher general-benchmark quality; ~3072-dim doubles index size and raises embedding cost; same provider; would require full re-index of both snapshots |
| Voyage `voyage-code-3` | Code-specialized | Purpose-built for code retrieval; requires a **separate provider account and key** outside OpenRouter, adding a dependency the project avoided by design |
| Jina `jina-embeddings-v2-base-code` | Code-specialized | Available via Jina API or as open weights; local inference would add a GPU/torch stack that the project explicitly excludes (HTTP-only, no local GPU) |

**Recommendation: keep the pin for `pilot-v1.0`.** Rationale:

1. The protocol is frozen; swapping the embedder is a retrieval-parameter
   change that requires a new documented protocol version and team agreement
   (`handoff_final.md` §6.5/§7). Silent substitution is forbidden and is now
   also guarded in code (`search_cli.run_search` raises if the query embedder
   model differs from the index's embedding model).
2. Both pilot indexes were built and smoke-validated with the pinned model;
   re-indexing mid-pilot would break comparability of any runs already traced.
3. A code-specialized embedder (e.g. `voyage-code-3`) is the most promising
   upgrade candidate for a **future protocol version** (main experiment). It
   should be evaluated side-by-side behind the same `search()` interface on
   retrieval diagnostics (essential-file recall at k on the pilot ground
   truth), never swapped based on which *method* benefits.

No performance numbers for the alternatives are claimed here — none were
measured in this project. The comparison above is a qualitative integration
assessment.

---

## 4. Index configuration (Stage 5 pins, unchanged)

| Item | Value |
|---|---|
| Embedding model | `openai/text-embedding-3-small` (OpenRouter, 1536-dim) |
| Index | Local NumPy, L2-normalized vectors, cosine via dot product |
| Index location | `artifacts/indexes/<first 12 chars of snapshot SHA>/` (`vectors.npy`, `chunks.json`, `meta.json`, scan/build reports) |
| Tokenizer | `tiktoken` `cl100k_base` |
| Chunking | max 800 tokens, 100 overlap, symbol-aware with line fallback (`pilot-v1.0-chunker-1`) |
| Determinism | Sorted directory/file scan order; chunk ids derived from snapshot + path + span + text hash; identical rebuild from the same snapshot yields identical chunk ids |
| Snapshots | Pre-change parent SHAs pinned in `benchmark/manifests/snapshots.json` |
| Defaults | `top_k=10`, `max_tokens=6000` (frozen `pilot-v1.0`; overridable per call for diagnostics only) |

**Dependencies:** `numpy`, `tiktoken`, `httpx`, `pyyaml` (runtime);
`pytest`, `jsonschema`, `mypy` (dev). Install: `pip install -e ".[dev]"` from
`research/`. Embeddings require `OPENROUTER_API_KEY` in `research/.env`.

---

## 5. Reproducible commands

```powershell
# From research/ with the venv active and .env configured
# (PI worktrees must exist at the parent SHAs in benchmark/manifests/snapshots.json)

# 1. Verify connectivity (neutral probe; not a pilot trial)
python scripts/probe_openrouter_embeddings.py

# 2. Build/rebuild both pilot indexes (deterministic; cached embeddings reused)
python scripts/build_corpus_indexes.py
python scripts/validate_stage5_indexes.py

# 3. Search a built index by pilot task id (frozen defaults: top-k 10, 6000 tokens)
python scripts/search_index.py --task-id pi_lazy_extension_loading `
    --query "How are extensions loaded lazily?" --validate

# 3b. Or by explicit index directory, with diagnostic overrides and file output
python scripts/search_index.py --index-dir artifacts/indexes/dd838d0fe09d `
    --query "package filtering rules" --top-k 5 --max-tokens 2000 `
    --output results/raw/t1_search_sample.json

# 4. Smoke tests (mocked embeddings; no API key needed)
python -m pytest tests/unit/test_retrieval_t1.py -q
```

`--validate` checks every returned chunk against
`schemas/retrieved_chunk.schema.json` before printing.

---

## 6. Sample output

Generated with the real retrieval code path (`search_cli.run_search`) on a
**synthetic two-chunk fixture with mocked embeddings**, then validated against
the chunk schema. The structure is byte-identical to live output; scores,
paths, and texts below are fixture data, **not** live Pi retrieval results
(this machine has no API key or Pi worktrees).

```json
{
  "query": "How are extensions loaded?",
  "top_k": 2,
  "max_tokens": 6000,
  "index": {
    "snapshot_sha": "ffffffffffffffffffffffffffffffffffffffff",
    "embedding_model": "openai/text-embedding-3-small",
    "dimensions": 2,
    "index_build_id": "t1-doc-sample",
    "chunk_count": 2,
    "chunker_version": "pilot-v1.0-chunker-1"
  },
  "result_count": 2,
  "evidence_tokens_used": 32,
  "results": [
    {
      "chunk_id": "demo-0001",
      "snapshot_sha": "ffffffffffffffffffffffffffffffffffffffff",
      "path": "packages/core/src/extensions/loader.ts",
      "symbol": "loadExtension",
      "start_line": 12,
      "end_line": 24,
      "text": "export async function loadExtension(name: string) {\n  // ...\n}",
      "token_count": 18,
      "content_hash": "3f6e1a2b",
      "chunker_version": "pilot-v1.0-chunker-1",
      "score": 0.9952284693717957
    },
    {
      "chunk_id": "demo-0002",
      "snapshot_sha": "ffffffffffffffffffffffffffffffffffffffff",
      "path": "packages/core/src/extensions/registry.ts",
      "symbol": "ExtensionRegistry",
      "start_line": 5,
      "end_line": 31,
      "text": "export class ExtensionRegistry {\n  // ...\n}",
      "token_count": 14,
      "content_hash": "9c04d7aa",
      "chunker_version": "pilot-v1.0-chunker-1",
      "score": 0.577464759349823
    }
  ],
  "schema_validated": true
}
```

---

## 7. Smoke test coverage (`tests/unit/test_retrieval_t1.py`)

| Test | Verifies |
|---|---|
| `test_search_output_matches_retrieved_chunk_schema` | Every hit validates against `retrieved_chunk.schema.json` |
| `test_retrieval_is_deterministic_across_repeated_calls` | Identical query → identical ranked `(chunk_id, score)` sequence; scores descending |
| `test_equal_scores_break_ties_deterministically` | Equal-score hits ordered by path (stable tie-break) |
| `test_duplicate_spans_are_deduplicated` | Duplicate `(path, start, end)` spans collapse to one hit |
| `test_token_budget_edge_cases` | `top_k<=0` / `max_tokens<=0` → `[]`; oversized top hit skipped, smaller later hits still selected under budget |
| `test_run_search_payload_and_model_mismatch_guard` | CLI payload shape; embedder/index model mismatch raises instead of silently substituting |
| `test_resolve_index_dir_explicit_and_by_task` | Index resolution by task id and explicit dir; clear errors for missing/unknown targets |

All tests use mocked embeddings and **do not** prove live OpenRouter
connectivity; use `scripts/probe_openrouter_embeddings.py` for that.

---

## 8. Changes that would require a new protocol version

Per `handoff_final.md` §6.5/§7, the following must **not** be changed under
`pilot-v1.0` without a new documented protocol version and team agreement:

- Embedding model or provider (e.g. adopting `voyage-code-3`)
- Chunking parameters (800/100), tokenizer, or chunker strategy
- Frozen search defaults (`top_k=10`, `max_tokens=6000`)
- Index backend semantics (cosine ranking, dedupe, budget rules)
- Giving Method A and Method B different indexes or embedders

This delivery changes none of them.

---

## 9. Verification status (honest)

- `python -m pytest tests/unit -q` on this delivery: **106 passed, 2 skipped**
  (Python 3.14, Windows; the 2 skips are pre-existing and unrelated to T1).
- Live OpenRouter embedding calls were **not** re-run for this delivery (no
  API key on the authoring machine); the Stage 5 closeout probe remains the
  last live verification.
- `scripts/search_index.py` against a real pilot index was **not** executed on
  the authoring machine (indexes are gitignored and Pi worktrees are not
  present); the identical code path was exercised end-to-end on a synthetic
  index (§6) and by the smoke tests.
