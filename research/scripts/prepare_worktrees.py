#!/usr/bin/env python3
"""Create or check detached, clean Pi parents without changing existing worktrees."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from repo_search.snapshot_paths import resolve_worktree_path, verify_worktree
from repo_search.snapshot_verify import GitCommandError, run_git


def prepare(repo: Path, root: Path, snapshots: list[dict], *, check_only: bool = False) -> list[dict]:
    repo, root = repo.resolve(), root.resolve()
    if root == ROOT or ROOT in root.parents or root == repo or repo in root.parents:
        raise ValueError("worktree root must be outside the research package and source clone")
    results = []
    for snap in snapshots:
        if snap["verification_status"] != "verified":
            raise ValueError(f"unverified snapshot: {snap['task_id']}")
        path = resolve_worktree_path(snap, root)
        parent = snap["parent_sha"]
        if run_git(repo, "rev-parse", snap["target_sha"] + "^1") != parent:
            raise ValueError("manifest parent differs from Git")
        created = False
        if not path.exists():
            if check_only:
                raise ValueError(f"missing worktree: {path}")
            root.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "-c", "core.autocrlf=false", "-C", str(repo),
                            "worktree", "add", "--detach", str(path), parent], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            created = True
        checks = verify_worktree(path, parent, source_repo=repo)
        results.append({"task_id": snap["task_id"], "created": created, **checks})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-path", required=True, type=Path)
    parser.add_argument("--worktree-root", required=True, type=Path)
    parser.add_argument("--task-id", action="append")
    parser.add_argument("--all", action="store_true", help="Prepare all candidates, rather than pilots only")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--manifest", type=Path, default=ROOT / "benchmark/manifests/snapshots.json")
    parser.add_argument("--write-paths", action="store_true", help="Record verified local paths in the selected manifest")
    args = parser.parse_args()
    document = json.loads(args.manifest.read_text())
    snaps = document["snapshots"]
    if args.task_id:
        if set(args.task_id) - {s["task_id"] for s in snaps}:
            parser.error("unknown task ID")
        snaps = [s for s in snaps if s["task_id"] in args.task_id]
    elif not args.all:
        snaps = [s for s in snaps if s["pilot_status"] == "pilot"]
    try:
        result = prepare(args.repo_path, args.worktree_root, snaps, check_only=args.check_only)
        if args.write_paths:
            for snap in snaps:
                snap["worktree_path"] = str(resolve_worktree_path(snap, args.worktree_root))
            args.manifest.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    except (ValueError, OSError, KeyError, GitCommandError, subprocess.CalledProcessError) as error:
        print(f"WORKTREE ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "worktrees": result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
