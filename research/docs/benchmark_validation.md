# Benchmark Validation Report (Stage 3)

**Review status:** `preliminary_self_validated` (independent EXP annotation; not teammate-reviewed)  
**Pilots completed:** `pi_lazy_extension_loading`, `pi_package_filtering`  
**Primary outcome focus:** repository-context **retrieval quality** (not implementation success)

---

## Pilot input verification (re-checked)

| Task | Worktree | HEAD | Detached | Clean | Repo |
|---|---|---|---|---|---|
| A | `C:\Users\froze\Desktop\pi-task-lazy` | `bfa6862400d0aaa3ebf3c09a44a2479487f470f1` | yes | yes | `pi-upstream` |
| B | `C:\Users\froze\Desktop\pi-task-packages` | `dd838d0fe09db079dcf2f57bab1d79d4df5a0e4c` | yes | yes | `pi-upstream` |

Candidate **E** (`37067e0`) remains `verification_failed` and was not annotated.

---

## Agent-visible prompts

### `pi_lazy_extension_loading`

> Improve extension loading so compiler-related dependencies are loaded only when required for filesystem-backed extensions. Preserve compatibility across supported runtime environments, including standard Node, Bun, and standalone executable deployments.

Budgets: `context_budget=6000`, `agent_call_limit=5`.

### `pi_package_filtering`

> Introduce a dedicated package configuration for external npm and Git sources while preserving existing configuration behavior. Support selective loading of package-provided resources and maintain consistent package-management behavior.

Budgets: `context_budget=6000`, `agent_call_limit=5`.

Prompts contain no SHAs, commit messages, diffs, or gold labels. Both methods will receive identical prompts via `repo_search.benchmark_loader`.

---

## Annotation process

For each pilot:

1. Inspected target commit diff (`git show <target>`).  
2. Listed changed paths; checked existence on the **parent** worktree.  
3. Read pre-change file contents and traced loader/settings/package-manager relationships.  
4. Selected a **minimum sufficient** relevant set (not every changed file).  
5. Labelled essential (2) vs supporting (1); excluded irrelevant docs/changelog (0).  
6. Recorded symbols and parent-relative line spans.  
7. Separated existing parent tests from target-added tests/files.

Artifacts:

- `benchmark/ground_truth/pi_lazy_extension_loading.json`
- `benchmark/ground_truth/pi_package_filtering.json`

---

## Evidence selection summary

### Pilot A — Lazy extension loading

| Path | Label | Notes |
|---|---|---|
| `packages/coding-agent/src/core/extensions/loader.ts` | essential | Eager `jiti/static` + `VIRTUAL_MODULES` + `loadExtensionModule` |
| `packages/coding-agent/src/config.ts` | supporting | `isBunBinary` / `isBundledNode` runtime flags |
| `.../8237-node-sea-extension-loading.test.ts` | supporting | Existing SEA regression on parent |
| `jiti-loader.ts`, `jiti-static-loader.ts`, `virtual-modules.ts`, `9540-...test.ts` | target-added (not retrievable) | Absent on parent |
| `CHANGELOG.md` | irrelevant | Excluded |

### Pilot B — Package configuration / filtering

| Path | Label | Notes |
|---|---|---|
| `.../settings-manager.ts` | essential | extensions settings + migration surface |
| `.../package-manager.ts` | essential | resolve/install of npm/git sources |
| `.../main.ts` | supporting | package CLI mutates extensions today |
| `test/settings-manager.test.ts` | supporting | existing settings tests; migration cases added by target |
| `src/index.ts` | supporting | public exports |
| README / docs / CHANGELOG | irrelevant | Excluded from gold retrieval set |

---

## Evaluation rules (defined; not executed)

- **File precision** = unique relevant retrieved files / unique retrieved files  
- **File recall** = unique relevant retrieved files / unique gold relevant files  
- **F1** = harmonic mean of precision and recall  
- **Essential-file recall** = essential gold files retrieved / essential gold files  
- **MRR / nDCG** (optional T3): file-level ranks with essential=2, supporting=1  
- Multiple chunks from one file count as **one** file  
- Primary outcome object: **final evidence pack**  
- Cumulative unique evidence during Method B recorded separately later  

Same annotations apply to Methods A and B.

---

## Evaluator isolation

| Agent-visible | Evaluator-only |
|---|---|
| `task_id`, `task_prompt`, `context_budget`, `agent_call_limit` | GT JSON, SHAs, diffs, rationales, candidate verification records |

Enforced by `src/repo_search/benchmark_loader.py` and `tests/unit/test_benchmark_stage3.py`.

---

## Unresolved concerns

1. Annotations are **preliminary_self_validated** only.  
2. Candidate **E** still unresolved.  
3. Candidates **C/D** package-management overlap may reduce benchmark independence if both are later fully annotated.  
4. Pilot B migration tests live inside an existing test file — case-level `target_added_tests` are reference notes, not separate retrieval targets.  
5. Line spans are best-effort parent locations; symbol moves in later Pi history are out of scope for these pinned snapshots.

---

## Stage 3 status

Pilots A/B: prompts + GT complete under independent execution.  
No corpus/RAG/agent implementation in this stage.
