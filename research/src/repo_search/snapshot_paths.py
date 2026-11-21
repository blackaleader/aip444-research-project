"""Portable, evaluator-side worktree lookup and fail-closed source checks."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from repo_search.snapshot_verify import GitCommandError, run_git


def resolve_worktree_path(snapshot: dict[str, Any], root: Path | None = None) -> Path:
    """An explicit/env root overrides historical machine-specific manifest paths."""
    task_id = snapshot.get("task_id")
    if not isinstance(task_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", task_id):
        raise ValueError("invalid task_id in snapshot")
    configured = root or os.environ.get("PI_WORKTREE_ROOT")
    if configured:
        return (Path(configured).expanduser().resolve() / task_id)
    recorded = snapshot.get("worktree_path")
    if not recorded:
        raise ValueError("set PI_WORKTREE_ROOT or prepare an explicit worktree path")
    # A Windows path is not a relative directory name on POSIX.
    if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", recorded):
        raise ValueError("historical Windows worktree path; set PI_WORKTREE_ROOT")
    return Path(recorded).expanduser().resolve()


def verify_worktree(path: Path, expected_sha: str, *, source_repo: Path | None = None) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise ValueError("expected worktree SHA must be a complete commit identifier")
    path = path.resolve()
    if not path.is_dir():
        raise ValueError(f"missing worktree: {path}")
    if Path(run_git(path, "rev-parse", "--show-toplevel")).resolve() != path:
        raise ValueError("worktree must be its own Git root")
    if run_git(path, "rev-parse", "HEAD") != expected_sha:
        raise ValueError("worktree HEAD differs from pinned parent")
    try:
        run_git(path, "symbolic-ref", "-q", "HEAD")
    except GitCommandError:
        pass
    else:
        raise ValueError("benchmark worktree must have detached HEAD")
    if run_git(path, "status", "--porcelain=v1", "--untracked-files=all", "--ignored=matching"):
        raise ValueError("worktree has tracked or untracked changes")
    common = Path(run_git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
    if source_repo is not None:
        expected_common = Path(run_git(source_repo, "rev-parse", "--path-format=absolute", "--git-common-dir")).resolve()
        if common != expected_common:
            raise ValueError("worktree belongs to another Git repository")
    return {"head_matches_parent": True, "detached": True, "clean": True,
            "common_git_directory_matches": source_repo is not None}
