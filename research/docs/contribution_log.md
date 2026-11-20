# Contribution Log

**Purpose:** Track real work for Appendix C and group coordination.  
**Rule:** Do not invent teammate participation. Update when work is actually done.

---

## Workstream legend

| Code | Workstream |
|---|---|
| EXP | Experimental design, implementation, results analysis (this owner) |
| T1 | Semantic Code Retrieval (RAG) |
| T2 | Repository Context Engineering and Validation |
| T3 | Synthesis, comparative evaluation extras, presentation & documentation |

---

## Entries

| Date | Workstream | Member (name) | Activity | Artifacts | Hours (approx.) |
|---|---|---|---|---|---|
| 2026-11-18 | EXP | *(fill name)* | Stage 1: create `research/` foundation, configs, docs | `research/**` scaffolding | *(fill)* |
| 2026-11-18 | EXP | *(fill name)* | Stage 1.5: ownership matrix, handoff contracts, schemas, metric ownership alignment | `docs/ownership_matrix.md`, `docs/handoff_contract.md`, `schemas/**`, aligned docs/config | *(fill)* |
| 2026-11-18 | EXP | *(fill name)* | Stage 2: Pi clone, SHA verification, pilot worktrees, verify script + tests + docs | `snapshots.json`, `scripts/verify_benchmark.py`, `docs/snapshot_verification.md`, `docs/pi_repository_notes.md` | *(fill)* |
| 2026-11-18 | EXP | *(fill name)* | Stage 3: pilot prompts + preliminary GT, loader isolation, Stage 3 tests | `tasks.json`, `ground_truth/*.json`, `benchmark_loader.py`, `docs/benchmark_validation.md` | *(fill)* |
| 2026-11-18 | EXP | *(fill name)* | Stage 4: freeze pilot-v1.0 protocol, accounting, metrics, config tests | `config/experiment.yaml`, `docs/protocol_freeze.md`, `protocol_config.py`, Stage 4 tests | *(fill)* |
| 2026-11-19 | EXP | *(fill name)* | Stage 5: corpus scan/chunking, OpenRouter embeddings, NumPy indexes, shared retriever | `src/repo_search/{corpus_*,chunking,embeddings,vector_index,retriever}.py`, `docs/corpus_and_retrieval.md`, Stage 5 tests | *(fill)* |
| 2026-11-19 | EXP | *(fill name)* | Stage 6: Method A/B, tools, OpenRouter chat, orchestration, traces | `method_a/b.py`, `repo_tools.py`, `chat_client.py`, `orchestrator.py`, `docs/methods_stage6.md` | *(fill)* |

---

## Teammate receipt tracker

| Deliverable | Expected from | Received? | Location | Notes |
|---|---|---|---|---|
| Retrieval API + index README | T1 | No | — | Contract in handoff/schemas; delivery pending |
| Snapshot verification + ground truth | T2 | No | — | EXP performed Stage 2 Git verification; T2 gold/task validation still pending |
| Commit identity cross-check vs T2 handoff | T2 | No | — | No T2 SHA artifact present to compare |
| Synthesis / charts / presentation | T3 | No | — | Needs Stage 9–10 EXP outputs |

---

## Notes

- Stage 1 establishes EXP scaffolding only.  
- Mark fallbacks clearly if EXP substitutes for T1/T2 later.
