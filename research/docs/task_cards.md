# Task Cards

Sources of truth:

- Agent-visible prompts: `benchmark/tasks.json` (only `task_id`, `task_prompt`, `context_budget`, `agent_call_limit`)
- Snapshots: `benchmark/manifests/snapshots.json`
- Ground truth (evaluator-only): `benchmark/ground_truth/<task_id>.json`
- Status registry: `benchmark/candidates.json`

---

## Pilot A — `pi_lazy_extension_loading`

| Field | Value |
|---|---|
| Snapshot verification | verified |
| Task validation | `preliminary_self_validated` |
| Benchmark acceptance | `pilot_accepted_preliminary` |
| Parent worktree | `C:\Users\froze\Desktop\pi-task-lazy` |
| Context budget / call limit | 6000 / 5 |
| Prompt | Improve extension loading so compiler-related dependencies are loaded only when required for filesystem-backed extensions. Preserve compatibility across supported runtime environments, including standard Node, Bun, and standalone executable deployments. |
| Essential files | `packages/coding-agent/src/core/extensions/loader.ts` |
| Supporting | `config.ts`; `test/suite/regressions/8237-node-sea-extension-loading.test.ts` |
| Must not appear in prompt | SHAs, commit message, diffs, GT |

---

## Pilot B — `pi_package_filtering`

| Field | Value |
|---|---|
| Snapshot verification | verified |
| Task validation | `preliminary_self_validated` |
| Benchmark acceptance | `pilot_accepted_preliminary` |
| Parent worktree | `C:\Users\froze\Desktop\pi-task-packages` |
| Context budget / call limit | 6000 / 5 |
| Prompt | Introduce a dedicated package configuration for external npm and Git sources while preserving existing configuration behavior. Support selective loading of package-provided resources and maintain consistent package-management behavior. |
| Essential files | `settings-manager.ts`; `package-manager.ts` |
| Supporting | `main.ts`; `settings-manager.test.ts`; `index.ts` |
| Must not appear in prompt | SHAs, commit message, diffs, GT |

---

## Other candidates

| ID | Snapshot | Task validation | Notes |
|---|---|---|---|
| C | verified | not_started | Overlap watch with D; GT deferred |
| D | verified | not_started | Overlap watch with C; GT deferred |
| E | **verification_failed** | not_started | `37067e0` unresolved |
| F–H | verified | not_started | GT deferred |
| R1 `32bcdc9` | advanced_reserve | — | Not a primary candidate |

Details: `docs/benchmark_validation.md`.
