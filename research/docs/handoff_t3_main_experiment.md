# T3 Handoff — Main Experiment Status

**Author:** Arman Ataeipour · **Date:** 2026-11-24 · **Branch:** `t3/experiment-integration`

## Status: BLOCKED on team decisions — not executed, nothing fabricated

No main-experiment runs exist. The pilot is now **complete** (12/12 runs,
2026-11-24 — see `docs/handoff_t3_pilot.md` §4), so the machinery blocker is
cleared; the pilot surfaced no protocol defects requiring a new version.
What remains is decisions, not infrastructure.

## Remaining blockers

1. **Task-set selection and freeze (team decision):** choose ≥4 of the 8
   verified tasks, resolve the C/D overlap question, and version-label the
   selection (e.g. `main-v1.0`).
2. **Ground-truth status decision:** all 8 tasks' GT is structurally valid but
   `pending_student_and_peer_review`. Either T1 reviews before main runs, or
   the team explicitly agrees to run against a frozen, labeled
   not-yet-reviewed GT version (results would then be re-evaluable after
   review; versions must never be mixed).
3. **Worktrees + indexes for the selected non-pilot tasks** (mechanical,
   ~minutes of setup + ~$0.10–0.30 embedding cost per snapshot;
   `prepare_worktrees.py --all` is validated, `build_corpus_indexes.py`
   needs its documented small extension to build non-pilot candidates).

## Benchmark readiness (verified 2026-11-24, this machine)

- **8/8 snapshots verified** against a fresh Pi clone
  (`verify_benchmark.py --dry-run`, exit 0) — exceeds the ≥4-task minimum.
- Structural GT validation passed for all 8 tasks
  (`validate_benchmark.py`: 34 file judgments, 49 spans).
- Candidate E (`pi_network_retry`) requires `git fetch origin <target-sha>`
  on fresh clones (commits unreachable from branch heads) — setup caveat only.
- Candidate C/D overlap watch (progress-conflicts vs dedup-collisions) remains
  an open task-independence question for T1's selection.
- Worktrees for the 6 non-pilot candidates are **not yet created**;
  `scripts/prepare_worktrees.py --all --repo-path <pi-clone> --worktree-root
  <root>` creates and verifies them (validated end-to-end for the 2 pilots).

## Frozen plan (to be recorded as config when runs start)

- **Task set:** ≥4 of the 8 verified tasks, selected and version-labeled
  (e.g. `main-v1.0`), with C/D overlap decision documented.
- **Repetitions:** 3 per method per task (per project protocol).
- **Planned run count:** `tasks × 3 repetitions × 2 methods`
  (e.g. 6 tasks → 36 runs / 18 matched pairs).
- **Everything else inherits `pilot-v1.0` pins** unless a new protocol version
  is documented and agreed: same retriever/indexes per snapshot for both
  methods, 6,000-token evidence budget, top-k 10, Method B limit 5,
  temperature 0, `openai/gpt-6-luna`, no GT exposure.
- Per-snapshot indexes must be built for every selected task before runs
  (`build_corpus_indexes.py` currently builds pilots only; extending it to
  `--all` candidates is a small, non-protocol change to make when main runs
  are approved).
- A run manifest (run → task, snapshot, repetition, method, config hash,
  trace path, status: planned/completed/failed/incomplete/invalid) must be
  maintained under `results/` from the first run.

## What would make this claimable

Main-experiment results may only be reported once: the pilot is complete and
reviewed, the task set + GT version are frozen and labeled, runs are executed
under the recorded config, and failures are documented rather than discarded.
