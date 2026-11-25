# T3 Handoff — Integration, Validation, and Pilot Status

**Workstream:** T3 — Integration, Validation, and Experiment Execution
**Author:** Arman Ataeipour
**Date:** 2026-11-24
**Branch:** `t3/experiment-integration` (based on central `main` @ `54de01a`)
**Protocol:** `pilot-v1.0` (frozen; nothing in this delivery changes it)

This document records what was independently verified on a second machine, the
disposition of prior contributions, and the exact state of the pilot. Nothing
below is claimed beyond what was actually executed.

---

## 1. Repository findings (verified against the repo, not logs)

| Claim | Verified? | Evidence |
|---|---|---|
| T0 core implementation complete through Stage 6 | **Yes** | All Stage 1–6 modules present (`src/repo_search/`: methods, orchestrator, retriever, embeddings, index, tools, traces); unit suite passes (§4) |
| T2 context-engineering contribution present | **Yes** | Merged via PR #1 (`t2/context-engineering`): 8-task set `benchmark/task_sets/t2_context_v1.json`, ground truth `benchmark/ground_truth/t2_context_v1/`, reviews under `benchmark/reviews/t2_context_v1/`, `scripts/prepare_worktrees.py`, `scripts/validate_benchmark.py` |
| T2's separate RAG implementation | **Not present** (consistent with "will not be delivered") — Stage 5 retriever is the only retrieval backend in the repo |
| T0 Stage 5 retrieval is the canonical baseline | **Yes** | `retriever.py` / `embeddings.py` / `vector_index.py` unchanged on `main`; no competing implementation exists |
| Experiment runs exist | **No** | `results/raw/` empty; `results/findings.md` has no results — no pilot or main runs have ever been executed |
| Evaluator (file-level P/R/F1) exists | **No** | No `scripts/evaluate.py` or equivalent; evaluation tooling was planned for Stage 7+ and has not been built. Noted for T1's evaluation work (§8) |

### Method compliance (code inspection)

- **Method A** (`method_a.py`): exactly one `retriever.search()` call, query is the
  exact task prompt (`query_unchanged: true` recorded in trace), zero LLM calls.
- **Method B** (`method_b.py`): tool-call limit enforced with
  `call_limit_reached` stop reason; the initial `semantic_search` counts toward
  the limit of 5; evidence budget tracked cumulatively.
- **Ground-truth isolation** (`benchmark_loader.py`): GT loads through a separate
  evaluator-only function; `method_input_bundle` content is screened for
  leakage markers (diff headers, commit URLs, "ground truth").

---

## 2. Arman's prior contribution (PR #2) — audit and disposition

**What it is:** branch `t1/semantic-retrieval` → PR #2
(https://github.com/terrykim109/aip444-research-project/pull/2), commit
`dea0d1f`. Adds `scripts/search_index.py` (search CLI),
`src/repo_search/search_cli.py` (helpers + embedder/index model-mismatch
guard), `tests/unit/test_retrieval_t1.py` (7 smoke tests),
`docs/retrieval_backend_notes.md`, and log updates.

**Audit performed:**

- Confirmed the branch touches **zero lines** of the Stage 5 retrieval stack or
  frozen protocol — it only adds parallel modules, tests, and docs.
- Test verification: on that branch, `python -m pytest tests/unit -q` →
  **106 passed, 2 skipped** (reproduced in-session). On `main` (without it):
  **99 passed, 2 skipped** — so the 7 added tests account exactly for the delta.
- The claim "no live API calls" is accurate: its tests use fake embedders; the
  CLI requires a key only at runtime.

**Disposition: KEEP, pending review as its own PR.** It is compatible with this
branch (no file conflicts in code; the two log files will append-merge
trivially). It is *not* duplicated or rolled into `t3/experiment-integration`,
so reviewers can evaluate each contribution separately. Nothing in the T3 work
depends on it.

---

## 3. Operational validation performed on this machine (2026-11-24)

Environment: Windows 11, Python 3.14, fresh venv, `pip install -e ".[dev]"`.
Pi upstream cloned from `https://github.com/earendil-works/pi` to a local path
(`--no-checkout`), worktrees under a separate local root.

| Check | Command | Result |
|---|---|---|
| Snapshot SHA verification, all 8 candidates | `scripts/verify_benchmark.py --repo-path <pi-clone> --dry-run` | **8/8 verified**, exit 0 (A–H incl. resolved Candidate E) |
| Pilot worktrees at pinned parents | `scripts/prepare_worktrees.py --repo-path <pi-clone> --worktree-root <root>` | **passed** — both pilots created detached + clean; HEAD == parent SHA; same Git object store |
| Offline benchmark/GT structural validation | `scripts/validate_benchmark.py --repo-path <pi-clone>` | **passed** — 8 tasks, 34 file judgments, 49 source spans, all `structural_validation: passed`; human relevance review `pending_student_and_peer_review` |
| Deterministic corpus reproduction | `scripts/build_corpus_indexes.py --chunks-only` | **Exact match** with Stage 5 record: lazy 1,787 files / 14,964 chunks; packages 564 files / 3,992 chunks |
| Unit tests (this branch / `main`) | `python -m pytest tests/unit -q` | **99 passed, 2 skipped** (2 skips pre-existing, unrelated) |

### Finding: Candidate E requires fetch-by-SHA

`pi_network_retry` target `37067e0…` and parent `4860665…` are **not reachable
from any upstream branch/tag** — a fresh clone does not contain them, and
`validate_benchmark.py` fails with `git cat-file … bad file` until you run:

```powershell
git -C <pi-clone> fetch origin 37067e0166dbbcd9362797d84ab44c6f98e6cc40
```

After that explicit fetch, both objects exist and all validation passes. This
confirms T2's "resolved without substitution" claim (the commits are genuine
GitHub objects in the Pi repository network) **but** reproduction on any new
machine needs this extra step. Recorded as a benchmark limitation; if Candidate
E is used in a main experiment, the fetch step must be part of the setup
procedure.

### Note: manifest `worktree_path` is machine-local

`benchmark/manifests/snapshots.json` records the original EXP machine's
worktree paths. `prepare_worktrees.py --write-paths` rewrites them to verified
local paths; this was done locally for the corpus build and then **reverted**
before commit so the committed manifest is unchanged. Every runner must
re-run `--write-paths` locally before building indexes or running methods.

---

## 4. Pilot status: **BLOCKED — one missing input (API key)**

Per the frozen protocol: 2 tasks × 2 methods × 3 repetitions = **12 runs / 6
matched pairs**, evidence budget 6,000 tokens, top-k 10, Method B limit 5 tool
calls, temperature 0, primary model `openai/gpt-6-luna`, prompt
`pilot-v1.0-agent-system-1`.

**Zero pilot runs have been executed. No run records exist.** Nothing was
fabricated.

Everything is staged except one item:

| Prerequisite | Status |
|---|---|
| Verified snapshots + worktrees | ✅ done (§3) |
| Deterministic chunk corpus | ✅ done (§3) |
| Method/orchestration code validated | ✅ done (§1, §3 tests) |
| Embedded NumPy indexes (`vectors.npy`) | ❌ **blocked** — embedding build requires `OPENROUTER_API_KEY`; no key exists on this machine (`research/.env` absent) |
| Method B chat runs | ❌ **blocked** — same missing key |

### Exact procedure to run the pilot once a key is available

```powershell
cd research
.\.venv\Scripts\activate
# 1. Create .env from .env.example; set OPENROUTER_API_KEY (+ PI_REPO_PATH)
# 2. Point the manifest at local worktrees (machine-local, do not commit):
python scripts/prepare_worktrees.py --repo-path <pi-clone> --worktree-root <root> --write-paths
# 3. Build embedded indexes (one-time; cached):
python scripts/probe_openrouter_embeddings.py
python scripts/build_corpus_indexes.py
python scripts/validate_stage5_indexes.py
# 4. The 12 pilot runs (order: per task, per repetition, A then B):
#    for task in pi_lazy_extension_loading, pi_package_filtering:
#      for rep in 1..3:
python scripts/run_method_a.py --task-id <task> --repetition <rep>
python scripts/run_method_b.py --task-id <task> --repetition <rep>
# Traces persist under results/raw/ (gitignored; preserve and share out-of-band)
```

Failed or incomplete runs must be kept and recorded, not silently retried.

---

## 5. Main experiment readiness

See `docs/handoff_t3_main_experiment.md`. Summary: **blocked** behind the pilot
(same key blocker), but the benchmark is closer to main-ready than older docs
state — 8/8 snapshots verified and structurally validated ground truth exists
for all 8 tasks. Human relevance review of T2's annotations is the open
validation item for T1.

---

## 6. Tests — commands and actual results

| Where | Command | Result |
|---|---|---|
| `t3/experiment-integration` (= `main` content) | `python -m pytest tests/unit -q` | 99 passed, 2 skipped |
| `t1/semantic-retrieval` (PR #2) | `python -m pytest tests/unit -q` | 106 passed, 2 skipped |

Mocked tests do not establish live API behavior; no live OpenRouter calls were
made at any point in this validation (no key available).

---

## 7. Artifact locations

| Artifact | Location | Committed? |
|---|---|---|
| Pi clone (objects incl. Candidate E after fetch) | local, outside repo | No (never commit Pi trees) |
| Pilot worktrees (detached, clean, pinned parents) | local `<worktree-root>/<task_id>` | No |
| Chunk manifests + scan reports | `research/artifacts/indexes/<sha12>/` | No (gitignored, reproducible) |
| Validation outputs (verify/validate/corpus) | summarized in this doc §3 | This doc |
| Run records / traces | none exist yet | — |

---

## 8. What T1 (Rehat) needs to resolve or complete

1. **Human relevance review** of T2's ground truth (all 8 tasks are
   `pending_student_and_peer_review`); any changes after runs begin require a
   new benchmark version, and results evaluated against different versions
   must not be combined.
2. **Evaluator implementation** — file-level TP/FP/FN, precision, recall, F1
   (+ essential-file recall, MRR/nDCG with essential=2/supporting=1 labels).
   No evaluator exists in the repo yet; traces and GT formats are stable inputs.
3. **Candidate E setup caveat** (§3) if E is included in the main task set.
4. Benchmark version labeling for the main experiment task selection (≥4 of
   the 8 verified tasks; do not present the selection as already T1-validated).
