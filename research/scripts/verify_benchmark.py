#!/usr/bin/env python3
"""Verify Pi benchmark candidate commits and update snapshots.json.

Read-only against the Pi clone: resolves SHAs, checks parent prefixes, writes
the evaluator-side snapshot manifest. Does not checkout, reset, rebase, or
delete worktrees.

Usage:
  python scripts/verify_benchmark.py --repo-path /path/to/pi-upstream
  python scripts/verify_benchmark.py   # uses PI_REPO_PATH or ../pi-upstream

Exit codes:
  0 — all primary candidates verified
  1 — one or more verification failures / unresolved commits
  2 — usage / configuration error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from repo_search.snapshot_verify import verify_candidate  # noqa: E402

DEFAULT_CANDIDATES = ROOT / "benchmark" / "candidates.json"
DEFAULT_MANIFEST = ROOT / "benchmark" / "manifests" / "snapshots.json"
DEFAULT_REPO_URL = "https://github.com/earendil-works/pi"


def load_dotenv_pi_path(research_root: Path) -> str | None:
    env_file = research_root / ".env"
    if not env_file.is_file():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() == "PI_REPO_PATH":
            value = value.strip().strip('"').strip("'")
            return value or None
    return None


def resolve_repo_path(cli_path: str | None) -> Path:
    candidates: list[Path] = []
    if cli_path:
        candidates.append(Path(cli_path))
    env = os.environ.get("PI_REPO_PATH")
    if env:
        candidates.append(Path(env))
    dotenv = load_dotenv_pi_path(ROOT)
    if dotenv:
        candidates.append(Path(dotenv))
    # Preferred Stage 2 location: sibling of the group project folder.
    candidates.append(ROOT.parents[1] / "pi-upstream")
    candidates.append(Path.cwd() / "pi-upstream")

    for path in candidates:
        if path.is_dir() and (path / ".git").exists():
            return path.resolve()
        # worktree .git may be a file
        if path.is_dir() and (path / ".git").is_file():
            return path.resolve()
    searched = ", ".join(str(p) for p in candidates)
    raise FileNotFoundError(
        "Pi repository not found. Pass --repo-path or set PI_REPO_PATH. "
        f"Searched: {searched}"
    )


def detect_origin_url(repo: Path) -> str:
    from repo_search.snapshot_verify import GitCommandError, run_git

    try:
        return run_git(repo, "remote", "get-url", "origin")
    except GitCommandError:
        return DEFAULT_REPO_URL


def verify_origin(repo: Path) -> tuple[bool, str]:
    url = detect_origin_url(repo)
    ok = "earendil-works/pi" in url.replace(".git", "")
    return ok, url


def default_worktree_map() -> dict[str, str]:
    desktop = Path.home() / "Desktop"
    # Also support the path layout used in this workspace.
    lazy = Path(r"C:\Users\froze\Desktop\pi-task-lazy")
    packages = Path(r"C:\Users\froze\Desktop\pi-task-packages")
    mapping: dict[str, str] = {}
    if lazy.is_dir():
        mapping["pi_lazy_extension_loading"] = str(lazy)
    elif (desktop / "pi-task-lazy").is_dir():
        mapping["pi_lazy_extension_loading"] = str(desktop / "pi-task-lazy")
    if packages.is_dir():
        mapping["pi_package_filtering"] = str(packages)
    elif (desktop / "pi-task-packages").is_dir():
        mapping["pi_package_filtering"] = str(desktop / "pi-task-packages")
    return mapping


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-path",
        default=None,
        help="Path to local Pi clone (default: PI_REPO_PATH or ../pi-upstream)",
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=DEFAULT_CANDIDATES,
        help="Path to candidates.json",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Output snapshot manifest path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print results without writing the manifest",
    )
    args = parser.parse_args(argv)

    try:
        repo = resolve_repo_path(args.repo_path)
    except FileNotFoundError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2

    origin_ok, origin_url = verify_origin(repo)
    print(f"Pi repo: {repo}")
    print(f"Origin:  {origin_url} ({'OK' if origin_ok else 'UNEXPECTED'})")
    if not origin_ok:
        print(
            "CONFIG ERROR: origin does not look like earendil-works/pi",
            file=sys.stderr,
        )
        return 2

    candidates_doc = json.loads(args.candidates.read_text(encoding="utf-8"))
    primary = candidates_doc.get("primary_candidates", [])
    worktrees = default_worktree_map()

    results = []
    verified = []
    failed = []

    print("\n=== Candidate verification ===")
    for item in primary:
        task_id = item["task_id"]
        result = verify_candidate(
            repo,
            letter_id=item.get("letter_id", ""),
            task_id=task_id,
            target_commit=item["target_commit"],
            expected_parent_prefix=item["known_parent_prefix"],
            pilot_status=item.get("status", "candidate"),
            worktree_path=worktrees.get(task_id),
        )
        results.append(result)
        status = result.verification_status
        mark = "OK" if status == "verified" else "FAIL"
        print(
            f"[{mark}] {result.letter_id} {task_id}: {status}"
            + (f" — {result.error}" if result.error else "")
        )
        if result.target_sha:
            print(f"      target={result.target_sha}")
            print(f"      parent={result.parent_sha}")
        if status == "verified":
            verified.append(result)
        else:
            failed.append(result)

    repository_url = candidates_doc.get("repository", {}).get("url", DEFAULT_REPO_URL)
    manifest = {
        "schema_version": "1.1",
        "status": "verified_partial" if failed else "verified",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pi_repo_path": str(repo),
        "origin_url": origin_url,
        "notes": [
            "Evaluator-side snapshot metadata only. Do not place target/parent SHAs in agent-visible task prompts.",
            "Git history is authoritative for commit identity.",
            "Candidate E (pi_network_retry / 37067e0) could not be resolved in the fetched upstream history as of Stage 2.",
            "Pilot worktrees are detached checkouts of verified parent SHAs.",
        ],
        "summary": {
            "primary_total": len(results),
            "verified": len(verified),
            "failed": len(failed),
            "failed_task_ids": [r.task_id for r in failed],
        },
        "snapshots": [r.to_manifest_entry(repository_url) for r in results],
    }

    print("\n=== Summary ===")
    print(f"Verified: {len(verified)}/{len(results)}")
    if failed:
        print("Failed:")
        for r in failed:
            print(f"  - {r.task_id}: {r.error}")

    if not args.dry_run:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"\nWrote manifest: {args.manifest}")

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
