# Experimental Protocol Freeze — `pilot-v1.0`

**Stage:** 4 (design) / 5 (technical pins)  
**Protocol version:** `pilot-v1.0`  
**Design frozen:** yes  
**Technical configuration:** configured in Stage 5 (`docs/corpus_and_retrieval.md`)  

This document freezes the **rules** of the controlled comparison. Embedding model, tokenizer, chunking, and index identity are pinned in Stage 5 without changing these design rules.

**Config source of truth:** `config/experiment.yaml`  
**Do not** retune budgets after seeing which method wins. Engineering fixes require a **new protocol version**.

---

## 1. Operational definitions

| Term | Definition |
|---|---|
| **Method A** | One-shot code RAG: exact task prompt → exactly one semantic retrieval → dedupe/rank → final evidence pack → stop. No LLM query rewrite. |
| **Method B** | Agent-directed search: identical prompt → initial semantic search with that exact prompt → LLM inspect/refine + read-only tools within limits → ranked pack + full trace. |
| **Evidence pack** | Final ranked repository excerpts returned as the method’s answer context. **Primary retrieval-quality outcome.** |
| **Cumulative unique evidence exposure** | Distinct repository context inspected during a run (supplementary). |
| **Retrieval quality** | Agreement with evaluator-only ground truth (file-level; essential vs supporting). |
| **Implementation success** | Out of scope as primary outcome. |

**Fixed research question:** Does agent-directed code search outperform one-shot code RAG for repository-level software engineering tasks?

---

## 2. Independent variable and primary outcome

- **Independent variable:** search strategy (one-shot vs agent-directed).  
- **Primary outcome:** retrieval quality of the **final evidence pack**.  
- **Primary metric:** file-level **F1** on unique file paths.  

Literature alignment (not extra methods): RepoBench (retrieval vs completion; multi-file GT); RepoCoder (iteration, refinement, stopping); Repoformer (usefulness, noise, cost — more ≠ better).

---

## 3. Shared controls (identical for A and B)

- Repository snapshot (task-specific pre-change)  
- Indexed corpus + file exclusions  
- Chunking configuration / version  
- Embedding model + revision + dimension  
- Retrieval backend + index build ID  
- Tokenizer  
- Initial task prompt (exact string)  
- Evidence-token budget (6,000)  
- Ground-truth annotations  
- Evaluation procedure  

**Only intended difference:** search strategy.

---

## 4. Pilot controls (`pilot-v1.0`)

| Control | Setting |
|---|---|
| Pilot tasks | 2 (`pi_lazy_extension_loading`, `pi_package_filtering`) |
| Annotation status | `preliminary_self_validated` (Stage 3) |
| Evidence-token budget | 6,000 |
| Agent tool-call limit | 5 total repository-tool calls |
| Retrieval top-k | 10 per search |
| Repetitions | 3 per method per task |
| Temperature | 0 where supported |
| Repository scope | Full Pi monorepo |
| Execution mode | Paired trials |
| Total records | 12 (2 × 2 × 3) |

These are **predetermined pilot settings**, not optimized values.

**Prerequisites present:** Stage 2 verified parents/worktrees for A/B; Stage 3 prompts + GT files.  
**Not blocking Stage 4:** Candidate E unresolved; non-pilot GT deferred.

---

## 5. Evidence-token accounting

Use the **same pinned tokenizer** for both methods (`cl100k_base`, Stage 5).

### Method A
- Final evidence pack ≤ 6,000 tokens.

### Method B
- Every repository excerpt from `semantic_search`, `read_file`, `find_symbol`, and `grep` counts toward a **cumulative** 6,000-token budget.  
- **Repeated** excerpts count again toward actual consumption.  
- Final evidence pack must also remain ≤ 6,000 tokens.

### Track separately
1. Cumulative evidence tokens  
2. Unique evidence tokens  
3. Final evidence-pack tokens  
4. Agent planning/input tokens  
5. Agent output tokens  
6. Provider-reported usage (when available)  
7. API cost (when available)  

Task-prompt and other model overhead are **not** hidden inside evidence counts. Planning tokens are never mixed into the evidence budget.

---

## 6. Agent-call limits and stopping conditions

Maximum **five** total repository-tool calls per Method B run. Each invocation of the following counts as one call:

- `semantic_search`  
- `read_file`  
- `find_symbol`  
- `grep`  

### Stopping reasons (record exactly one primary reason)

| Reason | Meaning |
|---|---|
| `evidence_sufficient` | Agent judges pack adequate and stops early |
| `no_new_relevant_evidence` | Further search not expected to add relevant context |
| `call_limit_reached` | 5 tool calls exhausted |
| `evidence_budget_exhausted` | Cumulative evidence tokens hit 6,000 |
| `tool_or_model_error` | Unrecoverable tool/LLM failure |

Record complete tool trace.  

**Forbidden:** modify repo; unrestricted shell; Git history access; evaluator-only annotations.

Method A: exactly **one** `semantic_search`; no file/symbol/grep tools; no LLM query rewrite.

---

## 7. Model and index requirements

### Semantic retrieval (shared) — Stage 5 pins

| Field | `pilot-v1.0` value |
|---|---|
| Provider / endpoint | OpenRouter `POST /embeddings` |
| Embedding model | `openai/text-embedding-3-small` |
| Dimension | 1536 (validate on live response) |
| Tokenizer | `cl100k_base` (tiktoken) |
| Chunking | symbol-aware + line fallback; max 800 / overlap 100; version `pilot-v1.0-chunker-1` |
| Index | Local NumPy L2-normalized cosine; per-snapshot `index_build_id` under `artifacts/indexes/` |
| top-k | **10** (frozen) |
| Evidence tokens per search | **6000** (frozen) |

Within each task, A and B share the same pinned retriever/index. Details: `docs/corpus_and_retrieval.md`.

BM25 may be used only for pipeline smoke tests and must **not** be labelled semantic code RAG.

### Agent LLM — Stage 6 configured

| Field | Value |
|---|---|
| Primary model | `openai/gpt-6-luna` via OpenRouter (`OPENROUTER_*`) |
| Secondary exploratory | `openrouter/free` (record served model; never auto-replace primary) |
| Temperature | **0** (frozen) |
| Max output tokens | **4096** (technical; separate from 6000 evidence budget) |
| System prompt version | `pilot-v1.0-agent-system-1` |

Same agent model/config across tasks and repetitions for claimable runs.  
Deterministic mocked/dry-run paths = plumbing only — **not** valid LLM-directed search evidence.

Credentials: environment variables only (`OPENROUTER_API_KEY`; never commit secrets).

---

## 8. Repetitions and paired trials

- 3 repetitions × 2 methods × 2 tasks = **12** records.  
- `paired_trial_id = "{task_id}__r{repetition}"` pairs A and B.  
- Run Method A in every pair even if deterministic.  
- Predetermined balanced order: for each task, for `r` in 1..3, run A then B; **log actual order**, seed, and config hash every run.

---

## 9. Evaluation metrics (frozen definitions)

Same evaluator-only GT for both methods. Unique file paths only (multi-chunk ≠ multi-file).

| Role | Metric |
|---|---|
| **Primary** | File-level F1 |
| Secondary | File precision, file recall, essential-file recall, MRR, nDCG (essential=2, supporting=1) |

Evaluate separately:

1. **Final evidence pack** — primary quality outcome  
2. **Cumulative unique evidence exposure** — supplementary iterative-search analysis  

Efficiency: evidence tokens, planning tokens, tool calls, latency, API cost, new relevant files from extra searches, diminishing returns.

Report task-level and aggregate comparisons + repetition variance.  

**Do not:** claim statistical significance or broad generalization from this two-task pilot; equate more material with better quality.

---

## 10. Execution-order procedure (when Stage 9 runs)

1. Confirm `protocol_version: pilot-v1.0` and matching index/LLM pins from Stage 5+.  
2. Load agent-visible task via `benchmark_loader` (no GT leakage).  
3. For each task × repetition: execute A then B under shared `paired_trial_id`.  
4. Persist JSONL with budgets, traces, stop reasons, token fields, config hash.  
5. Evaluate offline against GT.

Stage 4 does **not** execute trials.

---

## 11. Known limitations

1. GT is `preliminary_self_validated`, not externally reviewed.  
2. Full embedding index builds require `OPENROUTER_API_KEY`; Stage 5 live probe and dual-index builds are verified when the key is present.  
3. Two-task pilot; Candidate E unresolved; C/D overlap risk if expanded.  
4. Temperature 0 does not guarantee full provider determinism.  
5. Design freeze ≠ completed experiment; Methods A/B not run until Stage 6+.

---

## Freeze statement

As of Stage 4, **design rules and pilot budgets for `pilot-v1.0` are frozen**.  
**Technical configuration** (exact model revisions, tokenizer, chunking parameters, index IDs) remains **pending** until verified in Stage 5.  

Any post-freeze rule or budget change requires a new protocol version (e.g. `pilot-v1.1`) documented before main experimental runs.
