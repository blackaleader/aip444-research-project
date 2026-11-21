"""Git commit / parent-prefix verification helpers for Stage 2.

Uses subprocess with argument lists only (no shell interpolation).
Does not modify repository state (no checkout, reset, rebase, or worktree deletion).
"""

from __future__ import annotations

import subprocess
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class GitCommandError(RuntimeError):
    """Raised when a read-only git command fails."""


def run_git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return stdout (stripped)."""
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "").strip()
        raise GitCommandError(err or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def object_exists(repo: Path, rev: str) -> bool:
    try:
        run_git(repo, "cat-file", "-e", f"{rev}^{{commit}}")
        return True
    except GitCommandError:
        return False


def resolve_commit(repo: Path, rev: str) -> str:
    return run_git(repo, "rev-parse", f"{rev}^{{commit}}")


def resolve_first_parent(repo: Path, target_sha: str) -> str:
    return run_git(repo, "rev-parse", f"{target_sha}^1")


def resolve_tree(repo: Path, commit_sha: str) -> str:
    return run_git(repo, "rev-parse", f"{commit_sha}^{{tree}}")


@dataclass
class CommitVerification:
    letter_id: str
    task_id: str
    target_input: str
    expected_parent_prefix: str
    target_sha: str | None
    parent_sha: str | None
    parent_list: list[str]
    target_tree_sha: str | None
    parent_tree_sha: str | None
    target_commit_date: str | None
    target_subject: str | None
    parent_prefix_verified: bool
    verification_status: str
    pilot_status: str
    worktree_path: str | None
    error: str | None = None

    def to_manifest_entry(self, repository_url: str) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "letter_id": self.letter_id,
            "repository_url": repository_url,
            "target_sha": self.target_sha,
            "parent_sha": self.parent_sha,
            "target_tree_sha": self.target_tree_sha,
            "parent_tree_sha": self.parent_tree_sha,
            "target_commit_date": self.target_commit_date,
            "target_subject": self.target_subject,
            "expected_parent_prefix": self.expected_parent_prefix,
            "parent_prefix_verified": self.parent_prefix_verified,
            "parent_list": self.parent_list,
            "verification_status": self.verification_status,
            "pilot_status": self.pilot_status,
            "worktree_path": self.worktree_path,
            "error": self.error,
            "target_input": self.target_input,
        }


def verify_candidate(
    repo: Path,
    *,
    letter_id: str,
    task_id: str,
    target_commit: str,
    expected_parent_prefix: str,
    pilot_status: str = "candidate",
    worktree_path: str | None = None,
) -> CommitVerification:
    """Resolve target/parent SHAs and validate the expected parent prefix."""
    if not re.fullmatch(r"[0-9a-f]{7,40}", target_commit) or not re.fullmatch(r"[0-9a-f]{4,40}", expected_parent_prefix):
        raise ValueError("candidate target and parent prefix must be hexadecimal commit identifiers")
    if not object_exists(repo, target_commit):
        return CommitVerification(
            letter_id=letter_id,
            task_id=task_id,
            target_input=target_commit,
            expected_parent_prefix=expected_parent_prefix,
            target_sha=None,
            parent_sha=None,
            parent_list=[],
            target_tree_sha=None,
            parent_tree_sha=None,
            target_commit_date=None,
            target_subject=None,
            parent_prefix_verified=False,
            verification_status="verification_failed",
            pilot_status=pilot_status,
            worktree_path=worktree_path,
            error=f"target commit not found: {target_commit}",
        )

    try:
        target_sha = resolve_commit(repo, target_commit)
        if not object_exists(repo, f"{target_sha}^1"):
            return CommitVerification(
                letter_id=letter_id,
                task_id=task_id,
                target_input=target_commit,
                expected_parent_prefix=expected_parent_prefix,
                target_sha=target_sha,
                parent_sha=None,
                parent_list=[],
                target_tree_sha=resolve_tree(repo, target_sha),
                parent_tree_sha=None,
                target_commit_date=None,
                target_subject=None,
                parent_prefix_verified=False,
                verification_status="verification_failed",
                pilot_status=pilot_status,
                worktree_path=worktree_path,
                error=f"first parent missing for {target_sha}",
            )

        parent_sha = resolve_first_parent(repo, target_sha)
        meta = run_git(
            repo,
            "show",
            "-s",
            "--format=%H%n%P%n%T%n%cs%n%s",
            target_sha,
        ).splitlines()
        parent_list = meta[1].split() if len(meta) > 1 and meta[1] else []
        if parent_list != [parent_sha]:
            raise GitCommandError("benchmark target must have exactly one recorded parent")
        target_tree = meta[2] if len(meta) > 2 else resolve_tree(repo, target_sha)
        date = meta[3] if len(meta) > 3 else None
        subject = meta[4] if len(meta) > 4 else None
        parent_tree = resolve_tree(repo, parent_sha)
        prefix_ok = parent_sha.startswith(expected_parent_prefix)

        if not prefix_ok:
            return CommitVerification(
                letter_id=letter_id,
                task_id=task_id,
                target_input=target_commit,
                expected_parent_prefix=expected_parent_prefix,
                target_sha=target_sha,
                parent_sha=parent_sha,
                parent_list=parent_list,
                target_tree_sha=target_tree,
                parent_tree_sha=parent_tree,
                target_commit_date=date,
                target_subject=subject,
                parent_prefix_verified=False,
                verification_status="verification_failed",
                pilot_status=pilot_status,
                worktree_path=worktree_path,
                error=(
                    f"parent prefix mismatch: expected startswith "
                    f"{expected_parent_prefix!r}, got {parent_sha}"
                ),
            )

        return CommitVerification(
            letter_id=letter_id,
            task_id=task_id,
            target_input=target_commit,
            expected_parent_prefix=expected_parent_prefix,
            target_sha=target_sha,
            parent_sha=parent_sha,
            parent_list=parent_list,
            target_tree_sha=target_tree,
            parent_tree_sha=parent_tree,
            target_commit_date=date,
            target_subject=subject,
            parent_prefix_verified=True,
            verification_status="verified",
            pilot_status=pilot_status,
            worktree_path=worktree_path,
            error=None,
        )
    except GitCommandError as exc:
        return CommitVerification(
            letter_id=letter_id,
            task_id=task_id,
            target_input=target_commit,
            expected_parent_prefix=expected_parent_prefix,
            target_sha=None,
            parent_sha=None,
            parent_list=[],
            target_tree_sha=None,
            parent_tree_sha=None,
            target_commit_date=None,
            target_subject=None,
            parent_prefix_verified=False,
            verification_status="verification_failed",
            pilot_status=pilot_status,
            worktree_path=worktree_path,
            error=str(exc),
        )


def verification_to_dict(result: CommitVerification) -> dict[str, Any]:
    return asdict(result)
