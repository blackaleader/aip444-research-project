# Corpus Preparation and Semantic Retrieval (Stage 5)

**Protocol:** `pilot-v1.0` (design frozen at Stage 4; technical pins resolved here)  
**Scope:** Snapshot scan → deterministic chunking → OpenRouter embeddings → NumPy cosine indexes → shared `search()`  
**Not in scope:** Method A/B orchestration, chat completions, experimental runs (Stage 6+)

---

## 1. Snapshots indexed

Separate corpora and indexes for both verified pilot **pre-change** worktrees:

| Task | Worktree | Snapshot SHA (parent) |
|---|---|---|
| `pi_lazy_extension_loading` | `C:\Users\froze\Desktop\pi-task-lazy` | `bfa6862400d0aaa3ebf3c09a44a2479487f470f1` |
| `pi_package_filtering` | `C:\Users\froze\Desktop\pi-task-packages` | `dd838d0fe09db079dcf2f57bab1d79d4df5a0e4c` |

Indexes live under `artifacts/indexes/<sha12>/` and must not be mixed across snapshots.

---

## 2. Scanning and exclusions

`repo_search.corpus_scan.scan_repository` walks the worktree with **deterministic** sorted directory/file order and POSIX repo-relative paths.

**Included:** source (`.ts`/`.tsx`/`.js`/…), tests, docs (`.md`/`.mdx`), configs, package manifests, `AGENTS.md`, and similar text artifacts.

**Excluded directories:** `.git`, `node_modules`, `dist`, `build`, caches (`.turbo`, `.next`, `.cache`, coverage, `__pycache__`, venvs), `vendor`, IDE folders, temps.

**Excluded files:** binaries, media, minified bundles, lockfiles, oversized files (>1.5 MB), empty files.

`.github` and other non-listed dot-directories remain eligible when contents match include rules.

---

## 3. Chunking configuration

Initial configuration (validated against Pi sources before full indexing; **not** tuned to Method A/B scores):

```yaml
chunking:
  max_chunk_tokens: 800
  overlap_tokens: 100
  tokenizer: cl100k_base
  strategy: symbol_aware_with_line_fallback
```

- **Tokenizer:** `tiktoken` encoding `cl100k_base` for consistent token accounting with the evidence budget.
- **TypeScript/JavaScript:** symbol-aware breakpoints (functions/classes/interfaces/types/enums/exported arrow consts); oversized symbols split with line fallback + overlap.
- **Other text:** line-based windows with the same max/overlap.
- **Chunker version:** `pilot-v1.0-chunker-1`

### Pre-index validation notes

Validation on real Pi files confirmed:

- `cl100k_base` loads via tiktoken and yields stable counts for identical text.
- 800 / 100 token windows keep typical TS modules as one or few chunks; large generated-looking or dense files fall back to line splits without empty spans.
- No adjustment to max/overlap was required for correctness; settings remain as specified.

Every chunk records: `chunk_id`, `snapshot_sha`, `path`, `symbol`, `start_line`, `end_line`, `text`, `token_count`, `content_hash`, `chunker_version`.  
`chunk_id` is deterministic from snapshot + path + line span + text hash.

---

## 4. OpenRouter embeddings

| Setting | Value |
|---|---|
| Model | `openai/text-embedding-3-small` (no silent substitution) |
| Endpoint | `POST https://openrouter.ai/api/v1/embeddings` |
| Auth | `OPENROUTER_API_KEY` (optional fallback: `LLM_API_KEY` if set) |
| Expected dimensions | 1536 (validated from live response when key available) |

Adapter features (`repo_search.embeddings.OpenRouterEmbedder`):

- Batching, index-ordered response mapping, dimension/usage validation
- Bounded retries on transient HTTP failures
- Filesystem cache keyed by `snapshot_sha` + `content_hash` + model + preprocess id

Stage 5 uses **embeddings only**. Chat models reserved for Stage 6:

- Primary: `openai/gpt-6-luna`
- Secondary exploratory: `openrouter/free` (record actual served model; never auto-replace primary)

---

## 5. Local NumPy vector index

`repo_search.vector_index.NumpyVectorIndex`:

- L2-normalized float32 vectors; cosine similarity = dot product
- Persist: `vectors.npy`, `chunks.json`, `meta.json`
- Meta includes snapshot SHA, embedding model/dims, tokenizer, chunking config, `index_build_id`, chunker version
- Separate directory per snapshot under `artifacts/indexes/`

No Chroma, Cohere rerank, or hosted vector DB.

---

## 6. Shared semantic retriever

```python
from repo_search import SemanticRetriever
hits = retriever.search(query, top_k=10, max_tokens=6000)
```

Behaviour:

1. Embed query with the same OpenRouter model  
2. Cosine search on the snapshot index  
3. Deterministic tie-break (score ↓, path, start_line, chunk_id)  
4. Deduplicate by `chunk_id` and path/line span  
5. Enforce `top_k=10` and evidence-token budget (`6000`)  
6. Preserve path, symbol, lines, chunk IDs, scores  

**Method A** must call `search` exactly once. Internal embedding HTTP calls are **not** additional semantic-search invocations.

---

## 7. Usage accounting

| Phase | Meaning |
|---|---|
| Corpus indexing | Shared preparation cost; **not** assigned exclusively to Method A or B |
| Query-time | Per `search()` embedding usage |

Artifacts: `artifacts/indexes/<sha12>/embedding_usage.json`, `artifacts/corpus_build_summary.json`, optional `usage_accounting` ledger.

---

## 8. Reproduction commands

```powershell
cd "C:\Users\froze\Desktop\AIP Research Project\research"
python -m pip install -e ".[dev]"

# Optional: set OPENROUTER_API_KEY in .env (see .env.example)

# Chunk both pilots without calling the API
python scripts/build_corpus_indexes.py --chunks-only

# Live embedding connectivity probe (requires API key)
python scripts/probe_openrouter_embeddings.py

# Full index build for both pilots (requires API key; uses cache)
python scripts/build_corpus_indexes.py

# Unit tests (mocked API — do not interpret as live connectivity)
python -m pytest tests/unit -q
```

---

## 9. Corpus statistics (chunks-only build)

Measured on the verified pilot worktrees with `pilot-v1.0-chunker-1` (no embedding API calls):

| Snapshot | Task | Files chunked | Exclusion notes | Chunks | Chunk tokens (cl100k) |
|---|---|---|---|---|---|
| `bfa6862400d0…` | `pi_lazy_extension_loading` | 1787 | 27 | 14964 | 4,681,325 |
| `dd838d0fe09d…` | `pi_package_filtering` | 564 | 9 | 3992 | 1,524,923 |

Chunk manifests: `artifacts/indexes/<sha12>/chunks_manifest.jsonl`.  
Full `vectors.npy` indexes are produced by `python scripts/build_corpus_indexes.py` when `OPENROUTER_API_KEY` is set (shared indexing cost; not assigned to Method A or B).

---

## 10. Live API and index status

**Live API:** verified (`scripts/probe_openrouter_embeddings.py` → `live_api_verified: true`).  
Model `openai/text-embedding-3-small`, dimensions **1536**. Credentials are not logged.

**Indexes built** under `artifacts/indexes/<sha12>/` (vectors.npy + chunks.json + meta.json):

| Snapshot | Files | Chunks | Index size | Embedding tokens | Requests |
|---|---:|---:|---:|---:|---:|
| `bfa6862400d0…` (lazy) | 1787 | 14964 | ~114 MB | 4,681,325 | 234 |
| `dd838d0fe09d…` (packages) | 564 | 3992 | ~31 MB | 1,524,923 | 63 |

Shared corpus indexing cost is recorded in each `embedding_usage.json` and is **not** assigned to Method A or B.  
Filesystem embedding cache: `artifacts/embedding_cache/` (safe resume on re-run).  
Functional smoke validation: `python scripts/validate_stage5_indexes.py`.  
Mocked unit tests still do not claim live connectivity by themselves.
