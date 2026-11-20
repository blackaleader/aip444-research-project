# Final Project Handoff — Onboarding and Coordination

**Audience:** Teammates cloning this repository to contribute code, tests, documentation, and commits.  
**Owner of this handoff:** Experimental design / methodology / core implementation through Stage 6 (EXP). Stage 7–8 integration and evaluation coordination: T3.  
**Repository scope:** Everything under `research/` unless noted.  
**Protocol:** `pilot-v1.0` (design frozen — do not retune budgets after seeing method scores).  

**Rule:** Do not invent completed work, fabricated results, or teammate contributions. Update `docs/contribution_log.md` when you actually deliver something.

---

## 1. Research objective and fixed question

**Topic:** Repository-Level Context for Coding Agents.

**Fixed research question (do not rename or reframe):**

> Does agent-directed code search outperform one-shot code RAG for repository-level software engineering tasks?

| Concept | Definition for this project |
|---|---|
| **Method A** | One-shot code RAG: exact task prompt → exactly one semantic search → final evidence pack |
| **Method B** | Agent-directed search: same prompt → iterative tools within limits → final evidence pack + trace |
| **Primary outcome** | Retrieval quality of the **final evidence pack** vs evaluator-only ground truth |
| **Primary metric** | File-level **F1** |
| **Not primary** | Whether generated code successfully implements the change |

Corpus and tasks come from the [Pi](https://github.com/earendil-works/pi) monorepo at **task-specific pre-change (parent) snapshots**.

---

## 2. Team roles

| Role | Responsibility |
|---|---|
| **EXP** | Experimental design, methodology and core implementation |
| **Teammate 1 (T1)** | Semantic Code Retrieval (RAG) — shared retrieval validation and improvements |
| **Teammate 2 (T2)** | Repository Context Engineering and Benchmark Validation |
| **Teammate 3 (T3)** | Agent-directed search analysis, experiment integration/coordination, comparative evaluation and research synthesis |

**Independence rule:** Teammate work is not yet included. Integrate only after schema/tests pass; record `implementation_origin`. T3 coordinates remaining Stage 7–8 integration and execution.

Contracts: `docs/handoff_contract.md`, `docs/ownership_matrix.md`, `schemas/`.

---

## 3. Completed Stages 1–6 (verified vs outstanding)

| Stage | Status | What was delivered | Verified? | Still outstanding |
|---|---|---|---|---|
| **1** | Complete | `research/` scaffold, README, configs, candidates | Docs/structure present | — |
| **1.5** | Complete | Ownership matrix, handoff contracts, JSON Schemas | Docs/schemas present | Some provenance rows in older docs are stale |
| **2** | Complete (partial) | Pi SHA verification, pilot worktrees, `snapshots.json` | **7/8** SHAs verified | Candidate **E** `pi_network_retry` / `37067e0` = `verification_failed` |
| **3** | Complete (pilot only) | Agent prompts + preliminary GT for A/B; loader isolation | GT files + Stage 3 tests | C–D/F–H GT deferred; GT is `preliminary_self_validated` only |
| **4** | Complete | `pilot-v1.0` design freeze | Config + Stage 4 tests | Do not change frozen budgets without a new protocol version |
| **5** | Complete | Corpus scan/chunking, OpenRouter embeddings, NumPy indexes, shared retriever | Live embedding probe + dual indexes + smoke validation documented | Indexes are **gitignored**; clones must rebuild or obtain artifacts offline |
| **6** | Complete | Method A/B, tools, chat client, orchestration, traces | Unit tests (**45 passed** on verification run); live chat probe succeeded in Stage 6 closeout | **No 12 method-run pilot batch**; no evaluation runner yet |

### Frozen pilot controls (`pilot-v1.0`) — do not change lightly

| Control | Value |
|---|---|
| Pilot tasks | `pi_lazy_extension_loading`, `pi_package_filtering` |
| Evidence budget | 6,000 tokens (`cl100k_base`) |
| Top-k | 10 |
| Method B tool calls | Max **5** (includes initial `semantic_search`) |
| Allowed tools | `semantic_search`, `read_file`, `find_symbol`, `grep` |
| Repetitions | 3 per method per task → **12** individual method-run records (**6** matched A/B pairs) |
| Temperature | 0 where supported |
| Primary metric | File-level F1 |

### Stage 5 technical pins (implemented)

| Item | Value |
|---|---|
| Embedding model | `openai/text-embedding-3-small` via OpenRouter |
| Dimensions | 1536 |
| Tokenizer / chunking | `cl100k_base`; max 800 / overlap 100; symbol-aware + line fallback |
| Index | Local NumPy L2-normalized cosine under `artifacts/indexes/<sha12>/` |

### Stage 6 technical settings (provisional, not design-frozen budgets)

| Item | Value |
|---|---|
| Primary chat model | `openai/gpt-6-luna` |
| Max completion tokens | **4096** (separate from evidence budget) |
| System prompt | `pilot-v1.0-agent-system-1` |
| Secondary model | `openrouter/free` — exploratory only; never auto-replace primary |

### Pilot snapshots (authoritative: `benchmark/manifests/snapshots.json`)

| Task | Parent SHA (index snapshot) | Local worktree (outside `research/`) |
|---|---|---|
| `pi_lazy_extension_loading` | `bfa6862400d0aaa3ebf3c09a44a2479487f470f1` | `C:\Users\froze\Desktop\pi-task-lazy` |
| `pi_package_filtering` | `dd838d0fe09db079dcf2f57bab1d79d4df5a0e4c` | `C:\Users\froze\Desktop\pi-task-packages` |

Corpus stats used for indexing (chunks-only / full index builds):

| Snapshot | Files | Chunks |
|---|---:|---:|
| Lazy | 1,787 | 14,964 |
| Packages | 564 | 3,992 |

**Do not modify** upstream Pi trees during experiments. Keep them read-only.

---

## 4. Architecture and directory map

```text
research/
├── README.md                 # Project overview
├── pyproject.toml            # Package repo-search v0.6.0
├── .env.example              # Credential placeholders (copy → .env; never commit .env)
├── config/experiment.yaml    # pilot-v1.0 + Stage 5/6 pins
├── schemas/                  # Integration JSON Schemas
├── benchmark/
│   ├── tasks.json            # Agent-visible prompts only
│   ├── candidates.json
│   ├── manifests/snapshots.json
│   └── ground_truth/         # Evaluator-only (A/B preliminary)
├── src/repo_search/          # Implementation package
├── scripts/                  # CLI entry points
├── tests/unit/               # Stage 2–6 unit tests
├── artifacts/                # Indexes, embedding cache (gitignored)
├── results/                  # Raw traces / processed / findings
└── docs/                     # Methodology, protocol, this handoff
```

### Core Python modules (`src/repo_search/`)

| Module | Role |
|---|---|
| `snapshot_verify.py` | Git SHA / parent verification helpers |
| `benchmark_loader.py` | Agent-visible task load; GT kept evaluator-only |
| `protocol_config.py` | Load/validate `experiment.yaml` |
| `corpus_scan.py` / `chunking.py` / `corpus_build.py` | Deterministic scan + chunk + index build |
| `embeddings.py` | OpenRouter embedding adapter + cache |
| `vector_index.py` | NumPy cosine index save/load/query |
| `retriever.py` | Shared `search(query, top_k, max_tokens)` |
| `evidence.py` | Normalized evidence pack + token ledger |
| `repo_tools.py` | Snapshot-bound Method B tools |
| `chat_client.py` | OpenRouter chat completions |
| `method_a.py` / `method_b.py` | Experimental methods |
| `orchestrator.py` | Single-run orchestration + trace write |
| `traces.py` | JSON/JSONL persistence; secret scrubbing |
| `agent_prompts.py` | Versioned Method B system prompt |

### Technologies

- Python ≥ 3.10  
- Dependencies: `pyyaml`, `numpy`, `tiktoken`, `httpx` (+ optional `pytest`, `mypy`)  
- OpenRouter: embeddings + chat  
- Local indexes only (no Chroma / hosted vector DB / Cohere rerank in the EXP path)

### Data flow

```text
Pi parent worktree → scan/chunk → OpenRouter embed → NumPy index
        ↓
Agent task prompt (no GT) → Method A or Method B (same retriever/index)
        ↓
Evidence pack + execution trace → (Stage 7+) evaluation vs GT → findings
```

---

## 5. Environment setup

### 5.1 Clone and install

```powershell
# From the research package root
cd research
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -e ".[dev]"
```

### 5.2 Secrets and paths

1. Copy `.env.example` → `.env` (gitignored).  
2. Set at least:

```env
PI_REPO_PATH=<absolute path to your Pi clone>
OPENROUTER_API_KEY=<your key>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-small
OPENROUTER_PRIMARY_CHAT_MODEL=openai/gpt-6-luna
OPENROUTER_SECONDARY_CHAT_MODEL=openrouter/free
```

3. **Never commit `.env`.** Never log API keys. Traces scrub common secret patterns (`src/repo_search/traces.py`).

### 5.3 External Pi worktrees

Pilot indexes and Method B file tools expect the worktree paths recorded in `benchmark/manifests/snapshots.json`. On a new machine you must either:

- Recreate detached worktrees at the same parent SHAs, **or**
- Update `worktree_path` entries locally (do not invent SHAs; verify with Git).

Upstream clone example (outside `research/`): see `docs/snapshot_verification.md` and `docs/pi_repository_notes.md`.

### 5.4 Rebuild Stage 5 artifacts (required after clean clone)

`artifacts/**` is gitignored. After clone:

```powershell
python scripts/probe_openrouter_embeddings.py
python scripts/build_corpus_indexes.py
python scripts/validate_stage5_indexes.py
```

Expect separate indexes under:

- `artifacts/indexes/bfa6862400d0/`
- `artifacts/indexes/dd838d0fe09d/`

Each should contain `vectors.npy`, `chunks.json`, `meta.json`, plus build/scan reports.

### 5.5 Execution commands (plumbing — not the 12 method-run pilot)

```powershell
# Connectivity (neutral prompts; not pilot trials)
python scripts/probe_openrouter_embeddings.py
python scripts/probe_openrouter_chat.py

# Single method runs
python scripts/run_method_a.py --task-id pi_lazy_extension_loading --repetition 1
python scripts/run_method_b.py --task-id pi_package_filtering --repetition 1

# Optional: skip writing traces
python scripts/run_method_a.py --task-id pi_lazy_extension_loading --repetition 1 --no-persist
```

Persisted traces: `results/raw/traces/` (and `runs.jsonl` when written).

### 5.6 Tests

```powershell
python -m pytest tests/unit -q
```

Test modules:

| File | Covers |
|---|---|
| `tests/unit/test_snapshot_verify.py` | Stage 2 verification helpers |
| `tests/unit/test_benchmark_stage3.py` | Tasks/GT isolation + parent checks |
| `tests/unit/test_protocol_stage4.py` | Frozen protocol config |
| `tests/unit/test_corpus_stage5.py` | Scan/chunk/embed/index/retriever (mocked API) |
| `tests/unit/test_methods_stage6.py` | Method A/B, tools, budgets, scrubbing (mocked LLM) |

Mocked tests **do not** prove live API connectivity. Live probes are separate scripts.

---

## 6. Individual responsibilities and actionable work

### 6.1 EXP (experimental design / implementation)

**Goal:** Establish the research methodology and core experimental framework through Stage 6.

**Completed contributions (Stages 1–6)** — historical record only; remaining Stage 7–8 integration, pilot/main execution and primary evaluation are owned by T3 (see §6.4 and §8).

| Area | Delivered work |
|---|---|
| Research foundation | Research question, workspace, methodology and project documentation |
| Repository preparation | Pi snapshot verification, parent commits and pilot worktrees |
| Benchmark preparation | A/B pilot tasks and preliminary ground-truth annotations |
| Experimental protocol | Frozen `pilot-v1.0` configuration |
| Corpus preparation | Deterministic scanning, symbol-aware chunking and line fallback |
| Semantic retrieval | OpenRouter embeddings, NumPy indexes and shared retriever |
| Method A | One-shot semantic RAG implementation |
| Method B | Agent-directed search controller and read-only repository tools |
| Experiment infrastructure | OpenRouter chat integration, orchestration, evidence packs, token accounting and execution traces |

**Key implementation locations**

`src/repo_search/`, `scripts/`, `schemas/`, `benchmark/`, `tests/unit/`, `config/` and `docs/`.

**Technical foundation**

- Embeddings: `openai/text-embedding-3-small`
- Primary agent model: `openai/gpt-6-luna`
- Shared NumPy cosine similarity indexes.
- Shared Method A/B retriever.
- Frozen `pilot-v1.0` protocol.

---

### 6.2 Teammate 1 — Semantic Code Retrieval (RAG)

**Goal:** Improve and validate the **shared** semantic retrieval stack without breaking Method A/B parity.

**Do start with**

| Path | Why |
|---|---|
| `src/repo_search/retriever.py` | Required `search(query, top_k, max_tokens)` contract |
| `src/repo_search/embeddings.py` | OpenRouter embedding adapter + cache |
| `src/repo_search/vector_index.py` | NumPy index |
| `src/repo_search/chunking.py` / `corpus_scan.py` | Deterministic corpus |
| `schemas/retrieved_chunk.schema.json` | Chunk schema |
| `docs/corpus_and_retrieval.md` | Reproduction notes |
| `tests/unit/test_corpus_stage5.py` | Regression harness |

**Suggested contributions (useful, non-duplicative)**

1. **Retriever quality analysis** — evaluate existing indexes using query diagnostics, retrieval relevance and failure cases.
2. **Retrieval improvements** — identify and implement justified improvements while preserving the shared `SemanticRetriever` interface.
3. **Hardening** — batch progress logging, resume metrics, caching and index integrity CLI improvements.
4. **Tests** — adapter conformance, deterministic retrieval and schema validation.
5. **Documentation** — `docs/retrieval_backend_notes.md` covering configuration, usage and reproduction.

**Expected deliverables**

- Validated shared semantic retriever.
- Retrieval diagnostics and quality observations.
- Code improvements and regression tests.
- Documentation and reproducible indexing/search commands.
- Explicit documentation of changes requiring a new protocol version.

**Must not**

- Give Method B a different index/embedder than Method A.
- Label BM25 or lexical-only runs as semantic code RAG.
- Silently substitute embedding models.
- Retune chunking based on which method performs better.

**Overlaps:** Frozen retrieval-parameter changes require a new documented protocol version and team agreement. T2 owns ground-truth and repository-path validity, not embedding selection. T3 coordinates Stage 7–8 integration of validated T1 work.

---

### 6.3 Teammate 2 — Repository Context Engineering and Benchmark Validation

**Goal:** Strengthen snapshot, task and ground-truth quality and leakage resistance.

**Do start with**

| Path | Why |
|---|---|
| `benchmark/manifests/snapshots.json` | Verified SHA / worktree registry |
| `benchmark/tasks.json` | Agent-visible prompts only |
| `benchmark/ground_truth/*.json` | Evaluator-only preliminary GT |
| `benchmark/candidates.json` | Eight candidates + statuses |
| `src/repo_search/benchmark_loader.py` | Isolation rules |
| `docs/benchmark_validation.md` | Stage 3 validation notes |
| `docs/snapshot_verification.md` | Stage 2 report |
| `schemas/ground_truth.schema.json` / `snapshots.schema.json` | Contracts |
| `tests/unit/test_benchmark_stage3.py` | Isolation + parent existence tests |

**Suggested contributions**

1. **Independent SHA/worktree cross-check** of pilots A/B; write `docs/t2_snapshot_review.md`.
2. **GT review / gold upgrade** for A/B using the existing schema; keep agent prompts free of answer leakage.
3. **Benchmark expansion** — prepare additional independently validated task cards and ground-truth annotations for C/D/F/G/H, subject to commit verification and task-independence review.
4. **Candidate E investigation** — locate a resolvable commit for `pi_network_retry` or document its exclusion.
5. **Leakage/tests** — verify that Method A/B input bundles never contain target SHAs, diffs or ground-truth information.
6. **Worktree setup guide** — reproducible detached checkout instructions for new environments.

**Expected deliverables**

- Reviewed and validated GT files.
- Additional task cards and relevance annotations.
- Snapshot verification documentation.
- Leakage-validation tests.
- Candidate independence assessment.
- Updated benchmark documentation.

**Must not**

- Put ground truth into agent-visible `tasks.json` or Method A/B inputs.
- Invent SHAs.
- Automatically classify every changed file as relevant.
- Modify Pi repositories' history or commit experimental code into Pi trees.

**Overlaps:** EXP established the experimental protocol through Stage 6. T3 uses validated benchmark annotations for comparative evaluation and coordinates Stage 7–8 integration of validated T2 work. Agree on essential versus supporting relevance labels before finalizing ranking metrics.

---

### 6.4 Teammate 3 — Agent-Directed Search Analysis, Experiment Integration and Research Synthesis

**Goal:** Investigate Method B behaviour; coordinate integration of validated T1/T2 contributions; complete the pilot; coordinate the main experiment; own primary evaluation, secondary metrics and final research synthesis.

**Do start with**

| Path | Why |
|---|---|
| `src/repo_search/method_b.py` | Agent loop, stop reasons, finalize rules |
| `src/repo_search/repo_tools.py` | Tool semantics and budget charging |
| `src/repo_search/agent_prompts.py` | System prompt version |
| `src/repo_search/orchestrator.py` | Experiment execution |
| `schemas/experiment_run.schema.json` | Run record contract |
| `docs/methods_stage6.md` / `docs/protocol_freeze.md` | Method rules |
| `results/raw/` / `results/findings.md` | Experimental outputs |
| `docs/report_plan.md` / `docs/literature_review.md` | Reporting scaffold |

**Suggested contributions**

1. **Method B trace analysis toolkit** — analyze tool-call sequences, query refinement, stopping reasons, newly discovered files, duplicate evidence and diminishing returns using execution JSON traces.
2. **Experiment integration (T3-coordinated)** — coordinate integration of validated T1/T2 contributions, resolve compatibility issues, validate shared schemas and ensure both methods use the same task prompts, snapshots and retrieval infrastructure.
3. **Pilot execution** — coordinate and complete the batch runner for 2 tasks × 2 methods × 3 repetitions = **12 individual method-run records**, organized into **6** matched A/B pairs.
4. **Primary evaluation** — implement or coordinate file-level precision, recall, F1, essential-file recall and resource-consumption analysis using execution traces and finalized GT.
5. **Secondary metrics** — MRR and nDCG using the same essential = 2 / supporting = 1 relevance labels.
6. **Main experiment** — coordinate the expanded benchmark and run the main comparison using at least four independently validated tasks, preferably six.
7. **Comparative synthesis** — interpret A/B results, identify task-level differences, investigate search efficiency and diminishing returns, and prepare report-ready findings.
8. **Presentation / documentation** — charts, research synthesis, report contributions and final presentation aligned with `docs/report_plan.md`.

**Expected deliverables**

- Integrated and tested experimental components (T1/T2 contributions coordinated by T3).
- Completed pilot method-run records and validation report.
- Main experiment execution records.
- Method B trace-analysis scripts and visualizations.
- Primary and secondary evaluation outputs.
- Paired comparative analysis and resource-consumption tables.
- Written research synthesis and final findings.
- Presentation materials and report contributions.

**Must not**

- Modify the frozen `pilot-v1.0` protocol silently (protocol changes require a new documented version and team agreement).
- Replace the project's primary file-F1 metric with another metric.
- Mix `openrouter/free` exploratory runs into primary GPT-6 Luna results.
- Claim statistical significance from the two-task pilot.
- Invent results before actual experimental records exist.
- Expose ground-truth annotations to either search method.
- Change shared retrieval infrastructure without coordinating with T1.

**Overlaps:** T1 owns semantic retrieval; T2 owns benchmark and ground-truth validation. T3 is the designated coordinator for remaining Stage 7–8 integration and execution: T3 integrates validated T1/T2 components, completes the pilot, coordinates the main experiment, owns primary evaluation / secondary metrics and final research synthesis.

---

### 6.5 Shared completion requirements

1. **Same snapshot index** for Method A and Method B within each paired trial.
2. **No ground truth** in method inputs (`benchmark_loader.method_input_bundle`).
3. **Record provenance:** `implementation_origin` ∈ {`independent`, `teammate_1`, `teammate_2`, `teammate_3`}.
4. **Preserve existing implementations** when introducing improvements; use feature flags or parallel modules where appropriate.
5. **Schema-first:** validate contributed components against `schemas/` before integration.
6. **Update** `docs/contribution_log.md` and `docs/ai_use_log.md` to reflect actual work.
7. **Git hygiene:** never commit `.env`, `artifacts/` or API keys. Prefer small, reviewable PRs/commits.
8. **Protocol changes:** changes to budgets, top-k, tool limits, chunking or embedding models require a new documented protocol version and team agreement; T3 coordinates Stage 7–8 integration afterward.
9. **Testing:** run relevant unit, integration and regression tests before considering a contribution complete.
10. **Documentation:** update setup, execution and reproduction instructions alongside implementation changes.

---

## 7. Integration requirements (all teammates)

**Coordinator for remaining Stage 7–8 integration and execution:** T3. Protocol changes remain subject to documented versioning and team agreement.

1. **Same snapshot index for Method A and Method B** on a paired trial.  
2. **No ground truth** in method inputs (`benchmark_loader.method_input_bundle`).  
3. **Record provenance:** `implementation_origin` ∈ {`independent`, `teammate_1`, `teammate_2`, `teammate_3`}.  
4. **Preserve EXP Stage 1–6 implementations** when swapping components (feature flag or parallel module).  
5. **Schema-first:** validate against `schemas/` before merging; T3 coordinates integration after validation.  
6. **Update** `docs/contribution_log.md` and `docs/ai_use_log.md` when you contribute.  
7. **Git hygiene:** never commit `.env`, `artifacts/`, or API keys. Prefer small reviewable PRs/commits.  
8. **Protocol changes** (budgets, top-k, tool limit, chunking, embedder for primary runs) require a **new protocol version** and team agreement, not silent edits to `pilot-v1.0`.

---

## 8. Remaining Stage 7–8 Work (Project Completion Path)

### Stage 7 — Integration, Validation and Pilot

**Integration and validation** *(T3 coordinates; T1/T2 supply their validated contributions)*
- Review and integrate teammate contributions (T3 coordinates; T1 retrieval / T2 benchmark contributions remain owned by those teammates).
- Validate shared interfaces, schemas and component compatibility.
- Finalize and review benchmark annotations and task cards.
- Complete integration and regression testing.
- Confirm ground-truth isolation, evidence provenance and protocol compliance.
- Establish the coordinated batch runner and pilot execution procedure.

**Pilot execution** *(T3 coordinates and completes)*
- Run 2 tasks × 2 methods × 3 repetitions = **12 individual method-run records**, organized into **6 matched A/B pairs**.
- Use paired IDs: `{task_id}__r{repetition}`.
- Method B must use the primary OpenRouter chat model (`openai/gpt-6-luna`) for primary experimental results.
- Persist execution traces under `results/raw/`.
- Record seeds, configuration hashes, model identifiers and `implementation_origin`.
- Preserve the frozen `pilot-v1.0` configuration throughout execution.
- Document failed, incomplete or invalid runs; do not silently substitute different models or indexes.

**Pilot review**
- Validate all expected method-run records and the **6** matched A/B paired comparisons.
- Review retrieval quality, budget compliance, execution failures and resource consumption.
- Identify methodological or implementation issues.
- Document any necessary protocol revisions under a new protocol version (with team agreement) before the main experiment.

### Stage 8 — Main Experiment, Comparative Analysis and Research Findings

**Main experiment** *(T3 coordinates; T1/T2 remain responsible for their respective retrieval and benchmark contributions)*
- Expand the benchmark to at least four independently validated tasks, preferably six.
- Confirm task independence and ground-truth quality.
- Freeze the approved main-experiment configuration.
- Execute the main comparison using both methods under consistent experimental conditions.
- Preserve raw traces, configuration details and implementation provenance.

**T3 — Primary evaluation and analysis**
- Calculate file-level precision, recall and **F1**.
- Calculate essential-file recall.
- Compare evidence tokens, planning tokens, tool calls, latency and API costs where available.
- Conduct paired Method A versus Method B comparisons.
- Analyze repeated-run variation and failure cases.
- Produce `results/findings.md` and document threats to validity in `docs/limitations.md`.

**T3 — Secondary metrics and research synthesis**
- Contribute MRR and nDCG where annotation granularity supports them.
- Analyze agent-directed search behaviour and diminishing returns.
- Develop comparative visualizations and research synthesis.
- Contribute presentation development and final report discussion.

**Final academic submission**
- Complete the approximately 1,500-word APA-format research paper.
- Include at least five credible sources.
- Complete appendices using `docs/appendix_templates.md`.
- Finalize contribution and AI-use logs.
- Complete individual reflections and group contribution breakdown.
- Incorporate AI presentation dry-run feedback and document improvements.

**Reporting requirements:** Clearly distinguish preliminary pilot observations from main-experiment findings. All conclusions must be supported by actual experimental data. Do not claim statistical significance or generalizability beyond what the study supports.

---

## 9. Quick “first day” checklist for a new teammate

1. Read this file + `README.md` + `docs/protocol_freeze.md`.  
2. Create venv; `pip install -e ".[dev]"`; copy `.env.example` → `.env`.  
3. Obtain Pi worktrees or recreate at parent SHAs; set `PI_REPO_PATH`.  
4. Rebuild indexes (`build_corpus_indexes.py`) or copy `artifacts/` privately from EXP.  
5. Run `pytest tests/unit -q` and the two probe scripts.  
6. Pick your workstream tasks in §6; open a branch; make a small first PR (docs or tests welcome).  
7. Route Stage 7–8 integration questions to T3. Protocol changes (frozen budgets, shared index identity, etc.) require a new documented protocol version and team agreement.

---

## 10. Key documentation index

| Doc | Use when |
|---|---|
| `docs/handoff_final.md` | **This file** — onboarding |
| `docs/EXECUTION_CHECKLIST.md` | Stage status board |
| `docs/protocol_freeze.md` | Frozen experimental rules |
| `docs/corpus_and_retrieval.md` | Stage 5 corpus/index |
| `docs/methods_stage6.md` | Method A/B how-to |
| `docs/benchmark_validation.md` | GT/prompt validation |
| `docs/snapshot_verification.md` | SHA verification report |
| `docs/limitations.md` | Threats to validity |
| `docs/report_plan.md` | Final write-up plan |
| `docs/contribution_log.md` | Who did what |

---

## 11. Honesty notes / verification limits for this handoff

**Verified from the repository at handoff authoring time:**

- Stage 1–6 code, docs, schemas, scripts, and unit tests are present as described.  
- `python -m pytest tests/unit -q` → **45 passed**.  
- Both index directories exist locally with `vectors.npy` / `meta.json` / chunk manifests.  
- Pilot snapshot manifest entries and worktree paths match the expected parent SHAs.  
- Candidate E remains `verification_failed`.  
- `results/findings.md` still has **no experimental results**.  
- Teammate receipt tracker shows **no T1/T2/T3 deliverables received**.

**Not re-verified in the same session as writing every claim (treat as last-reported):**

- Live OpenRouter embedding/chat probes from Stage 5/6 closeout (require each teammate’s own API key).  
- Exact wall-clock rebuild cost / provider billing for full re-indexing.  
- That teammate machines can reach the same Windows worktree paths without local adjustment.


---

*End of handoff. Questions about remaining Stage 7–8 integration, pilot/main execution or evaluation → T3. Protocol freezes and merging teammate backends: T3 coordinates; protocol changes require a new documented version and team agreement.*
