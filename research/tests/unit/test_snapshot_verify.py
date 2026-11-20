"""Unit tests for SHA / parent-prefix verification using a synthetic git repo."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from repo_search.snapshot_verify import verify_candidate


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


@pytest.fixture()
def synthetic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")

    (repo / "a.txt").write_text("parent\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-m", "parent commit")
    parent = _git(repo, "rev-parse", "HEAD")

    (repo / "a.txt").write_text("child\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-m", "child commit")
    child = _git(repo, "rev-parse", "HEAD")

    # stash ids for tests
    (repo / ".ids").write_text(f"{parent}\n{child}\n", encoding="utf-8")
    return repo


def test_verify_candidate_success(synthetic_repo: Path) -> None:
    parent, child = (synthetic_repo / ".ids").read_text(encoding="utf-8").splitlines()
    result = verify_candidate(
        synthetic_repo,
        letter_id="T",
        task_id="synthetic_task",
        target_commit=child[:7],
        expected_parent_prefix=parent[:7],
        pilot_status="pilot",
    )
    assert result.verification_status == "verified"
    assert result.target_sha == child
    assert result.parent_sha == parent
    assert result.parent_prefix_verified is True
    assert result.error is None
    assert result.target_tree_sha
    assert result.parent_tree_sha
    assert result.target_subject == "child commit"


def test_verify_candidate_missing_target(synthetic_repo: Path) -> None:
    result = verify_candidate(
        synthetic_repo,
        letter_id="X",
        task_id="missing",
        target_commit="deadbeef",
        expected_parent_prefix="0000000",
    )
    assert result.verification_status == "verification_failed"
    assert result.target_sha is None
    assert "not found" in (result.error or "")


def test_verify_candidate_parent_prefix_mismatch(synthetic_repo: Path) -> None:
    _parent, child = (synthetic_repo / ".ids").read_text(encoding="utf-8").splitlines()
    result = verify_candidate(
        synthetic_repo,
        letter_id="M",
        task_id="mismatch",
        target_commit=child,
        expected_parent_prefix="ffffff",
    )
    assert result.verification_status == "verification_failed"
    assert result.parent_prefix_verified is False
    assert result.target_sha == child
    assert "prefix mismatch" in (result.error or "")
