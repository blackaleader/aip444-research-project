# Pi Repository Notes (Pinned Snapshot Instructions)

**Purpose:** Record development/test instructions from the **pre-change pilot snapshots** for later corpus preparation and testing.  
**Not agent-visible task payload content.** Target-commit metadata stays in evaluator-side manifests only.

Inspected Stage 2 worktrees:

| Worktree | HEAD (parent SHA) | Task |
|---|---|---|
| `C:\Users\froze\Desktop\pi-task-lazy` | `bfa6862400d0aaa3ebf3c09a44a2479487f470f1` | `pi_lazy_extension_loading` |
| `C:\Users\froze\Desktop\pi-task-packages` | `dd838d0fe09db079dcf2f57bab1d79d4df5a0e4c` | `pi_package_filtering` |

Upstream clone: `C:\Users\froze\Desktop\pi-upstream` → `https://github.com/earendil-works/pi.git`

---

## Repository identity

- Monorepo name: `pi-monorepo` (`package.json`)
- Coding-agent package: `@earendil-works/pi-coding-agent` under `packages/coding-agent`
- Root agent instructions: `AGENTS.md` (present on both pilot snapshots; content differs by age)
- Contributor gate: `CONTRIBUTING.md`

---

## Instructions at Pilot A snapshot (`pi-task-lazy`)

Source: root `AGENTS.md` at parent `bfa6862…`.

### Commands (research-relevant)

| Command | Role |
|---|---|
| `npm install --ignore-scripts` | Hydrate deps without lifecycle scripts |
| `npm ci --ignore-scripts` | Clean/CI-style install |
| `npm run check` | Lint/format/typecheck after code changes (full output) |
| `./test.sh` | Non-e2e tests from repo root |
| Package vitest | Specific tests via vitest CLI path documented in `AGENTS.md` |
| `npm run build` / `npm test` | **Do not run** unless explicitly requested (per `AGENTS.md`) |

### Runtime / package manager

- Package manager: **npm** workspaces
- Engine (lazy snapshot `package.json`): **Node `>=22.19.0`**
- Direct deps expected pinned; lockfile changes treated as reviewed code

### Coding-agent / corpus relevance

- Primary package of interest for these pilots: `packages/coding-agent`
- Nested docs/examples under `packages/coding-agent/` (extensions, suite harness)
- `packages/coding-agent/test/suite/` uses harness + faux provider — no real provider APIs
- Do not modify `packages/ai/src/models.generated.ts` directly (regenerate via scripts)

### File-selection / exclusion cues for later corpus stages

- Prefer source under `packages/*/src` and tests under `packages/*/test`
- Generated / lock / build artifacts likely low value for retrieval: `dist/`, `node_modules/`, lockfiles, `models.generated.ts` (unless a task specifically needs model metadata)
- Follow `AGENTS.md` security rules around install scripts and shrinkwrap allowlists when installing locally

---

## Instructions at Pilot B snapshot (`pi-task-packages`)

Older snapshot (2026-01 parent). Root `AGENTS.md` exists with an earlier “First Message” style preamble.

| Item | Observation |
|---|---|
| Package manager | npm workspaces |
| Engine | Node `>=20.0.0` (older than Pilot A) |
| Workspace layout | Fewer packages than the later lazy snapshot (e.g. includes `web-ui`, `mom`, `pods` era layout) |
| Check script | `biome check` + `tsgo --noEmit` (+ web-ui check) |

Corpus builders must **not** assume identical package graphs across pilots — each snapshot is its own corpus root.

---

## Rules affecting future experiment hygiene

1. Treat worktrees as **read-only** benchmark inputs.  
2. Do not mix experimental `research/` code into Pi.  
3. Do not expose target SHAs, commit subjects, or changed-file lists through Method A/B task prompts.  
4. When running Pi tests later, prefer snapshot-local commands from that checkout’s `AGENTS.md` / `package.json`, not necessarily `main`.

---

## Stage 2 inspection status

| Item | Status |
|---|---|
| Root `AGENTS.md` read on both pilots | Done |
| Root `package.json` / engines recorded | Done |
| `CONTRIBUTING.md` skimmed (lazy) | Done |
| Nested coding-agent README deep-dive | Deferred (not required to start Stage 3 annotations) |
| Historical feature implementation / Pi edits | **Not performed** |
