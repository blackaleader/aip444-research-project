# Snapshot Verification Report (Stage 2)

## Repository identity

| Field | Value |
|---|---|
| Upstream URL | `https://github.com/earendil-works/pi` |
| Local clone | `C:\Users\froze\Desktop\pi-upstream` |
| Origin (verified) | `https://github.com/earendil-works/pi.git` |
| Shallow? | `false` |
| Group research path | `C:\Users\froze\Desktop\AIP Research Project\research` |
| Teammate 2 validation artifacts received? | **No** (none present under `benchmark/` beyond Stage 1 schemas) |

Git history in the local clone is authoritative for commit identity.

---

## Verification procedure

1. Clone (or locate) Pi outside the group research tree.  
2. `git fetch --all --tags`  
3. For each candidate in `benchmark/candidates.json`:  
   - `git rev-parse <target>^{commit}`  
   - `git rev-parse <target>^1`  
   - Compare parent to `known_parent_prefix`  
   - Record trees, date, subject via `git show -s --format=...`  
4. Create detached worktrees at **full parent SHAs** for pilots A and B.  
5. Persist results with `python scripts/verify_benchmark.py --repo-path <PI_REPO_PATH>`.

Reproduce:

```bash
cd research
python scripts/verify_benchmark.py --repo-path C:\Users\froze\Desktop\pi-upstream
python -m pytest tests/unit/test_snapshot_verify.py -v
```

Expected: **7/8 verified**; exit code `1` while candidate E remains unresolved (script correctly fails closed).

---

## Eight candidate SHA records

| ID | Task | Target (full) | Parent (full) | Prefix OK | Status |
|---|---|---|---|---|---|
| A | `pi_lazy_extension_loading` | `40c256cccbce062f6af5f2cacb85d0ce1ab4224d` | `bfa6862400d0aaa3ebf3c09a44a2479487f470f1` | yes (`bfa6862`) | **verified** |
| B | `pi_package_filtering` | `ef1fc3103ee869244800f301993bd4952125db78` | `dd838d0fe09db079dcf2f57bab1d79d4df5a0e4c` | yes (`dd838d0`) | **verified** |
| C | `pi_package_progress_conflicts` | `4058680d225535d25705aaf02644957c0ed7a096` | `b846a4bfcf168ae218dbeb0fecc24a98c0b3e332` | yes (`b846a4b`) | **verified** |
| D | `pi_package_dedup_collisions` | `50c83235904bb24e8d634cc25f7f761ec1324e98` | `c5c515f56096f212e0ad1e7f5c3c9b115908d37c` | yes (`c5c515f`) | **verified** |
| E | `pi_network_retry` | *(unresolved)* `37067e0` | *(unresolved)* expected `4860665` | n/a | **verification_failed** |
| F | `pi_rpc_context_statistics` | `835296b1d7d999100ee1c465b4958031d0bb5adc` | `9a0be024a6ff381362e04b19dd1c155c44675f4a` | yes (`9a0be02`) | **verified** |
| G | `pi_session_directory_config` | `8191d59c170c9bb336a82771e1826d25bb7ec1e0` | `8632e1b9484b9be62e8fc9b31757176f7c560313` | yes (`8632e1b`) | **verified** |
| H | `pi_cli_mode_validation` | `e40126f578ccc0a4a21f8d30cd8e96c8ecfe1722` | `1a584a7a56eb5e7b4ff8ccbd46430f1533282eed` | yes (`1a584a7`) | **verified** |

Additional metadata (trees, dates, subjects) is in `benchmark/manifests/snapshots.json`.

### Target subjects (evaluator-side only)

| ID | Date | Subject |
|---|---|---|
| A | 2026-09-19 | feat(coding-agent): defer extension loader dependencies |
| B | 2026-01-23 | feat(coding-agent): add packages array with filtering support |
| C | 2026-01-22 | feat(coding-agent): progress callbacks, conflict detection, URL parsing, tests (#645) |
| D | 2026-01-24 | feat(coding-agent): package deduplication and collision detection |
| F | 2026-03-24 | fix(coding-agent): expose rpc context usage closes #2550 |
| G | 2026-04-30 | feat(coding-agent): support session dir env |
| H | 2026-09-22 | fix(coding-agent): reject invalid --mode values |

---

## Parent-prefix verification

For A–D and F–H, `parent_sha.startswith(expected_parent_prefix)` held.  
No silent substitutions were made.

---

## Pilot worktrees

| Task | Path | HEAD | Detached | Clean | Common git dir |
|---|---|---|---|---|---|
| A | `C:\Users\froze\Desktop\pi-task-lazy` | `bfa6862400d0aaa3ebf3c09a44a2479487f470f1` | yes | yes | `pi-upstream/.git` |
| B | `C:\Users\froze\Desktop\pi-task-packages` | `dd838d0fe09db079dcf2f57bab1d79d4df5a0e4c` | yes | yes | `pi-upstream/.git` |

Parent tree SHAs match:

- Lazy: `98dcdb6be9679f1d7dadadf71f3072cdecdc32df`
- Packages: `a2dc723fd071c917d6e6878dc4722aef5f0abd8e`

Commands used:

```bash
git -C C:\Users\froze\Desktop\pi-upstream worktree add --detach C:\Users\froze\Desktop\pi-task-lazy bfa6862400d0aaa3ebf3c09a44a2479487f470f1
git -C C:\Users\froze\Desktop\pi-upstream worktree add --detach C:\Users\froze\Desktop\pi-task-packages dd838d0fe09db079dcf2f57bab1d79d4df5a0e4c
git -C <worktree> rev-parse HEAD
git -C <worktree> status --short
```

Treat worktrees as read-only benchmark inputs.

---

## Commands actually executed (Stage 2)

- `git clone https://github.com/earendil-works/pi.git C:\Users\froze\Desktop\pi-upstream`
- `git fetch --all --tags`
- `git rev-parse --is-shallow-repository` → `false`
- Per-candidate `cat-file` / `rev-parse` / `show -s`
- Investigation of missing `37067e0` / `4860665` (not in object DB; still missing after optional PR-ref fetch attempt)
- Pilot `worktree add --detach` + HEAD/status checks
- `python scripts/verify_benchmark.py --repo-path C:\Users\froze\Desktop\pi-upstream` (exit 1 due to E)
- `python -m pytest tests/unit/test_snapshot_verify.py -v` (3 passed)

---

## Verification failures / discrepancies

### Candidate E — `pi_network_retry`

- Input target prefix: `37067e0`
- Expected parent prefix: `4860665`
- **Neither object resolves** in the non-shallow clone of `earendil-works/pi` (including after fetching pull-request heads).
- Status recorded: `verification_failed` (not verified).
- No alternate commit was substituted.
- **Outstanding:** Teammate 2 / group must supply a resolvable SHA or retire/replace this candidate before using it in later stages.

### Other discrepancies

- None for A–D, F–H parent prefixes.
- No Teammate 2 SHA handoff file was available to compare; when delivered, compare against `snapshots.json` without silently editing their annotations (Stage 3 for gold review).

---

## Manifest

Updated: `benchmark/manifests/snapshots.json`  
Status field: `verified_partial` (7 verified, 1 failed).
