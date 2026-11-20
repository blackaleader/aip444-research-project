# Repository-Level Context for Coding Agents

**Status:** Stages 1–6 complete — methods + orchestration implemented; **`pilot-v1.0`** unchanged.  
**Next:** Stage 7 (paired pilot method-run records) — not started.  
**Available now:** Shared Stage 5 indexes/retriever; Method A/B runners; OpenRouter chat client; traces (`docs/methods_stage6.md`).  
**Not yet done:** The 12 pilot experimental trial records / Stage 7+ analysis.

---

## Members

- Arman Ataeipour 
- Nirajan Bhandari 
- Rehat Preet Kaur
- Terry Kim 


## 1. Project overview

This directory (`research/`) holds the experimental framework for our researech group project. It compares two ways of gathering **repository-level code context** for coding agents on realistic software-engineering tasks drawn from the [Pi](https://github.com/earendil-works/pi) monorepo.

My part is **Experimental design, implementation, and results analysis**, which owns the integrated experiment: snapshot verification, preliminary prompts/GT, local semantic retrieval (code embeddings), Methods A/B, LLM env adapter, logging, core metrics, and primary analysis.

Teammate workstreams remain assigned (T1 semantic retrieval; T2 repository validation; T3 agent-directed search/synthesis/comparative evaluation), not prerequisites. Contracts: `docs/handoff_contract.md`, `docs/ownership_matrix.md`.

---

## 2. Research topic and fixed research question

**Topic:** Repository-Level Context for Coding Agents.

**Research question:**

> Does agent-directed code search outperform one-shot code RAG for repository-level software engineering tasks?

We investigate whether LLM-directed iterative repository search and source inspection can retrieve more useful context than conventional one-shot code RAG.

**Primary outcome:** retrieval quality (evidence pack vs evaluator-only ground truth).  
**Not the primary outcome:** whether generated code successfully implements the change.

---

## 3. Why repository-level context matters

Modern coding agents work in large repositories where behaviour is split across packages, configs, and tests. A single file rarely explains “how extensions load” or “how packages are filtered.” Useful context is **cross-file**. If retrieval misses those links, agents reason from incomplete or misleading evidence.

---

## 4. What repository-level RAG is

**RAG (Retrieval-Augmented Generation)** retrieves relevant text from a corpus, then (typically) supplies it to an LLM. **Repository-level RAG** indexes a whole repository snapshot—here, the Pi monorepo at a task-specific pre-change commit—so queries can surface chunks from anywhere in that tree, not just an open buffer.

In this project we emphasise the **retrieval** side: building a ranked **evidence pack** under a shared token budget.

---

## 5. Benchmark vs experiment

| | Benchmark | Experiment |
|---|---|---|
| **Role** | Tasks, snapshots, prompts, ground truth | Running Method A vs Method B and scoring packs |
| **Independent owner** | EXP (preliminary self-validated prompts/GT; Git-verified snapshots) | EXP (retriever, methods, logging, core evaluation) |
| **Optional enhancement** | T2 review / gold upgrade | T1 retriever upgrade; T3 extra metrics/viz |
| **Current** | Pilots A/B prompts + preliminary GT; E unresolved; other GT deferred | Shared semantic retriever ready; Method A/B runners not built |

The benchmark defines *what* is asked and *what counts as relevant*. The experiment measures *which search strategy* gathers better evidence under shared controls.

---

## 6. One-shot RAG vs agent-directed search

**Method A — One-shot code RAG**  
Receives a task, performs **exactly one** retrieval against a shared code index, returns a ranked evidence pack.

**Method B — Agent-directed code search**  
Receives the **same** task, searches, inspects files/symbols, identifies missing context, refines queries, and searches again within resource limits, then returns a ranked evidence pack.

**Shared (intended):** snapshots, corpus construction, chunking, embedding/index backend, task prompts, evidence budgets, evaluation criteria.  
**Difference:** search strategy.

Method B is inspired by iterative retrieval (e.g. RepoCoder) but is **not** an exact reproduction. RepoBench / Repoformer principles inform evaluation and caution about irrelevant context; they are **not** extra methods.

---

## 7. Why Pi was selected

[Pi](https://github.com/earendil-works/pi) is a real, evolving monorepo with cross-cutting concerns (extensions, packages, RPC, CLI, networking). That makes repository-level retrieval nontrivial and closer to agent workloads than toy single-file tasks. We use **task-specific pre-change snapshots** so methods search the tree as it existed before the target change.

**Pi clone (outside this research folder):** `C:\Users\froze\Desktop\pi-upstream`  
**Pilot worktrees (detached pre-change parents):**

| Task | Worktree | HEAD |
|---|---|---|
| `pi_lazy_extension_loading` | `C:\Users\froze\Desktop\pi-task-lazy` | `bfa6862400d0aaa3ebf3c09a44a2479487f470f1` |
| `pi_package_filtering` | `C:\Users\froze\Desktop\pi-task-packages` | `dd838d0fe09db079dcf2f57bab1d79d4df5a0e4c` |

Do not modify upstream Pi or mix experimental code into these trees. Details: `docs/snapshot_verification.md`, `docs/pi_repository_notes.md`.

---

## 8. Eight candidates and two pilots

| ID | Task ID | Target (preliminary) | Parent prefix | Focus | Status |
|---|---|---|---|---|---|
| A | `pi_lazy_extension_loading` | `40c256c` | `bfa6862` | Lazy extension loading | **pilot** |
| B | `pi_package_filtering` | `ef1fc31` | `dd838d0` | Package configuration and filtering | **pilot** |
| C | `pi_package_progress_conflicts` | `4058680` | `b846a4b` | Package progress and conflict detection | candidate (overlap watch with D) |
| D | `pi_package_dedup_collisions` | `50c8323` | `c5c515f` | Package deduplication and collisions | candidate (overlap watch with C) |
| E | `pi_network_retry` | `37067e0` | `4860665` | Network retry handling | candidate |
| F | `pi_rpc_context_statistics` | `835296b…` | `9a0be02` | RPC context statistics | candidate |
| G | `pi_session_directory_config` | `8191d59…` | `8632e1b` | Session directory configuration | candidate |
| H | `pi_cli_mode_validation` | `e40126f…` | `1a584a7` | CLI mode validation | candidate |

**Advanced reserve (not one of the eight):** `32bcdc9` — investigate reported CI issue before acceptance.

**Stage 2 verification:** A–D and F–H are **verified** (full target/parent SHAs in `benchmark/manifests/snapshots.json`).  
**Candidate E** (`pi_network_retry` / `37067e0`) is **verification_failed** — object not present in fetched upstream history. See `docs/snapshot_verification.md`.  
Agent-visible `benchmark/tasks.json` still omits SHAs (evaluator-side only).

---

## 9. Why pre-change snapshots are necessary

If methods search the commit that already contains the fix, they can “retrieve the answer” from the future. Pre-change (parent) snapshots force retrieval to find the **context needed to understand or solve the task**, matching a developer’s starting point. Stage 2 resolves full parent/target SHAs and pins pilot worktrees at the **parent** commits.

---

## 10. What ground truth means

Ground truth is the **evaluator-only** map of relevant files, essential vs supporting evidence, symbols, and line spans (plus test metadata). It scores evidence packs. It must **never** be fed into Method A or B. Schema notes: `benchmark/ground_truth/README.md`. **No fabricated gold annotations in Stage 1.**

---

## 11. Individual responsibilities (experimental design owner)

Independently owns and must be able to deliver alone:

- Experimental protocol and configuration  
- Integrated Python experiment architecture (`src/repo_search`)  
- Shared schemas/interfaces  
- Pi commit/snapshot verification and benchmark loader  
- Preliminary prompts and self-validated ground truth (from diffs vs parent snapshots)  
- Corpus preparation and **local code-embedding** semantic retrieval backend  
- One-shot RAG and agent-directed controller (same retriever)  
- LLM provider adapter via environment configuration  
- Experiment runner, logging, **core** metrics, paired comparisons, primary interpretation  
- Integration testing and technical methodology documentation  

**Fallback labels:** local embeddings = semantic path; BM25 = smoke-test only (not semantic RAG); GT = `preliminary`/`self_validated` until reviewed; agent dry-run = plumbing only (real LLM required for claimable Method B results).

---

## 12. Teammate workstreams 

| Teammate | Contribution | Integration rule |
|---|---|---|
| **1 — Semantic Code Retrieval** | Alternate embeddings/index/ranking | Same `search()` interface; test before replace; keep EXP backend |
| **2 — Repository Context Engineering & Validation** | Reviewed snapshots/prompts/gold/leakage | Schema-validate; do not invent; preserve EXP preliminary path |
| **3 — Synthesis, comparative evaluation, presentation** | MRR/nDCG, extra viz, synthesis, polish | Consume EXP JSONL/CSV; do not redefine core P/R/F1 |

No empty modules pretend teammate work exists.

---

## 13. Intended architecture

```text
EXP verified snapshots  (+ optional T2 review)
        ↓
EXP preliminary prompts + self-validated GT  (+ optional T2 gold)
        ↓
EXP corpus + local semantic index  (identical for A and B)
   optional T1 backend behind same search()
        ↓
        ├── EXP Method A — one-shot orchestration
        │
        └── EXP Method B — agent controller + LLM env adapter
                    ↓
             Evidence packs + traces
                    ↓
             EXP run logger (JSONL / CSV)
                    ↓
             EXP core evaluation + primary interpretation
                    ↓
             optional T3 extras / presentation
```

Hard rules: same retriever/index for both methods; no hidden gold; BM25 ≠ semantic RAG; dry-run ≠ LLM experiment. Stage 5 implements the shared retriever; Method A/B orchestration starts at Stage 6.

---

## 14. Project structure

```text
research/
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── config/experiment.yaml
├── schemas/          # integration JSON Schemas (contracts only)
├── benchmark/
│   ├── tasks.json
│   ├── candidates.json
│   ├── manifests/snapshots.json
│   └── ground_truth/README.md
├── src/repo_search/  # scan, chunk, embeddings, index, retriever, loaders
├── scripts/          # verify_benchmark, build_corpus_indexes, probes
├── tests/unit/       # Stage 2–5 unit tests (mocked embeddings)
├── artifacts/        # chunk manifests + indexes (gitignored)
├── results/          # raw JSONL / processed CSV / charts + findings.md
└── docs/             # methodology, corpus_and_retrieval, protocol_freeze, …
```

---

## 15. Planned setup and dependencies

**Executable now (lightweight):**

```bash
cd research
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Dependencies: `pyyaml`, `numpy`, `tiktoken`, `httpx` (+ optional `pytest`, `mypy`). Embeddings via OpenRouter HTTP — no local GPU stack.

Copy `.env.example` → `.env` and set `PI_REPO_PATH`, `OPENROUTER_API_KEY`, and related OpenRouter fields. Never commit secrets.

---

## 16. Future execution workflow

See `docs/EXECUTION_CHECKLIST.md`. **Stage 5 corpus/retrieval is complete; Stage 6 is next.**

```bash
cd research
pip install -e ".[dev]"

# Stage 2 verification (exits 1 while candidate E unresolved)
python scripts/verify_benchmark.py --repo-path C:\Users\froze\Desktop\pi-upstream

# Stage 5 — chunk both pilots; embed+index when OPENROUTER_API_KEY is set
python scripts/build_corpus_indexes.py --chunks-only
python scripts/probe_openrouter_embeddings.py
python scripts/build_corpus_indexes.py

python -m pytest tests/unit -q
```

**Planned** (Stage 6+ — independent path):

```bash
# PLANNED — Stage 6+
# python scripts/run_method_a.py --task ... --rep 1
# python scripts/run_method_b.py --task ... --rep 1  # needs OPENROUTER chat model
# python scripts/evaluate.py --run-id ...
```

---

## 17. Evaluation metrics

See `config/experiment.yaml` and `docs/methodology.md`.

**Primary (EXP, required):** **file-level F1** (primary metric); also report precision/recall, essential-file recall; evidence vs planning token accounting; tool-call counts; latency; paired comparisons. Final evidence pack is the primary outcome object; cumulative unique exposure is supplementary.

**Secondary (T3, optional, same relevance labels):** MRR; nDCG; additional statistics; advanced visualizations; broader synthesis. Stage 10 can finish without T3.

Also track cumulative unique evidence exposure and newly discovered relevant files per iteration. Do not assume Method B is superior; report improvements and regressions; avoid overstated significance with few tasks/reps.

---

## 18. Reproducibility requirements

- Follow frozen `pilot-v1.0` design; new protocol version required for budget/rule changes  
- Bind every run to snapshot ID, index ID, method, repetition, `paired_trial_id`  
- Log Method B iterations  
- Keep ground truth out of method inputs  
- Prefer tested teammate upgrades when available, but **never block** on them; keep the independent path  
- Label BM25, preliminary GT, dry-runs, and `implementation_origin` honestly  
- Do not commit indexes, raw dumps, or `.env`  

---

## 19. Research limitations

Summary: candidate E unresolved; A/B GT preliminary only; Method A/B not run; live OpenRouter embeddings pending without API key; two-task pilot limits generalization; C/D overlap risk; retrieval quality ≠ implementation success. Full list: `docs/limitations.md`.

---

## Status board (honest)

| Item | State |
|---|---|
| Scaffolding & docs | **Created (Stage 1)** |
| Ownership / integration alignment | **Documented (Stage 1.5)** |
| Pi clone + pilot worktrees | **Prepared (Stage 2)** |
| Snapshot verification | **7/8 verified**; E failed (`verified_partial`) |
| Protocol freeze `pilot-v1.0` | **Design frozen (Stage 4)**; technical pins **configured (Stage 5)** |
| Integration schemas & contracts | **Documented** (`schemas/`, handoff) |
| Ground-truth annotations | **A/B preliminary_self_validated** (Stage 3); others deferred |
| Semantic retriever / index | **Verified** — OpenRouter `text-embedding-3-small` + NumPy cosine indexes for both pilots |
| Method A / Method B / chat adapter / runner | **Implemented (Stage 6)** — plumbing verified; pilot batch not run |
| Experiments & findings | Not started (Stage 7+) |
| Optional T1/T2/T3 upgrades | None received (not required) |

---

## Documentation index

| Doc | Purpose |
|---|---|
| [BEGINNER_GUIDE.md](docs/BEGINNER_GUIDE.md) | Concepts from scratch |
| [EXECUTION_CHECKLIST.md](docs/EXECUTION_CHECKLIST.md) | Ten-stage roadmap (+ 1.5) |
| [methodology.md](docs/methodology.md) | Controlled design |
| [literature_review.md](docs/literature_review.md) | RepoBench, RepoCoder, Repoformer |
| [snapshot_verification.md](docs/snapshot_verification.md) | Stage 2 SHA / worktree report |
| [benchmark_validation.md](docs/benchmark_validation.md) | Stage 3 prompts / GT / isolation |
| [protocol_freeze.md](docs/protocol_freeze.md) | Stage 4 frozen pilot protocol |
| [corpus_and_retrieval.md](docs/corpus_and_retrieval.md) | Stage 5 corpus, embeddings, index, retriever |
| [methods_stage6.md](docs/methods_stage6.md) | Stage 6 Method A/B, chat client, traces |
| [pi_repository_notes.md](docs/pi_repository_notes.md) | Pinned AGENTS.md / toolchain notes |
| [task_cards.md](docs/task_cards.md) | Human-readable tasks |
| [limitations.md](docs/limitations.md) | Threats to validity |
| [report_plan.md](docs/report_plan.md) | ~1,500-word APA plan |
| [ai_use_log.md](docs/ai_use_log.md) | AI interaction log |
| [contribution_log.md](docs/contribution_log.md) | Contribution tracker |
| [appendix_templates.md](docs/appendix_templates.md) | Appendices A–D |
| [schemas/README.md](schemas/README.md) | JSON Schema contracts |

---

## Literature links

- RepoBench (2024): https://proceedings.iclr.cc/paper_files/paper/2024/file/d191ba4c8923ed8fd8935b7c98658b5f-Paper-Conference.pdf  
- RepoCoder (2023): https://aclanthology.org/2023.emnlp-main.151/  
- Repoformer (2024): https://proceedings.mlr.press/v235/wu24a.html  
