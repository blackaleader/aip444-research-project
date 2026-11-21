"""Portable detached-parent worktrees with refusal to overwrite existing work."""

from pathlib import Path
import subprocess

import pytest

from repo_search.snapshot_paths import resolve_worktree_path, verify_worktree
from scripts.prepare_worktrees import prepare


@pytest.fixture()
def repo(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(source), *args], stderr=subprocess.PIPE).decode().strip()
    git("init", "--quiet")
    git("config", "user.name", "Worktree fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "commit.gpgsign", "false")
    (source / "a.ts").write_text("export const a = 1;\n")
    git("add", "a.ts")
    git("commit", "--quiet", "-m", "parent")
    parent = git("rev-parse", "HEAD")
    (source / "a.ts").write_text("export const a = 2;\n")
    git("add", "a.ts")
    git("commit", "--quiet", "-m", "target")
    return source, {"task_id": "pi_fixture", "parent_sha": parent,
                    "target_sha": git("rev-parse", "HEAD"), "verification_status": "verified"}


def test_portable_root_overrides_historical_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PI_WORKTREE_ROOT", str(tmp_path))
    assert resolve_worktree_path({"task_id": "pi_fixture", "worktree_path": "C:\\old\\path"}) == tmp_path / "pi_fixture"
    with pytest.raises(ValueError): resolve_worktree_path({"task_id": "../outside"})


def test_prepare_creates_and_rechecks_real_detached_worktree(repo, tmp_path):
    source, snap = repo
    root = tmp_path / "parents"
    first = prepare(source, root, [snap])
    assert first[0]["created"] and first[0]["common_git_directory_matches"]
    second = prepare(source, root, [snap], check_only=True)
    assert not second[0]["created"]
    assert (root / "pi_fixture/a.ts").read_text() == "export const a = 1;\n"


def test_existing_dirty_worktree_is_preserved_and_rejected(repo, tmp_path):
    source, snap = repo
    root = tmp_path / "parents"
    prepare(source, root, [snap])
    file = root / "pi_fixture/a.ts"
    file.write_text("keep my local work\n")
    with pytest.raises(ValueError, match="changes"):
        prepare(source, root, [snap])
    assert file.read_text() == "keep my local work\n"


def test_wrong_head_and_attached_checkout_rejected(repo, tmp_path):
    source, snap = repo
    with pytest.raises(ValueError): verify_worktree(source, snap["parent_sha"])
    with pytest.raises(ValueError, match="detached"):
        verify_worktree(source, snap["target_sha"])
    with pytest.raises(ValueError): prepare(source, source / "nested", [snap])
    with pytest.raises(ValueError): prepare(source, tmp_path / "missing", [snap], check_only=True)


def test_ignored_untracked_source_cannot_bypass_clean_parent_check(repo, tmp_path):
    source, snap = repo
    root = tmp_path / "parents"
    prepare(source, root, [snap])
    # Configure an ignore rule outside the worktree; leave the source tree itself unchanged.
    exclude = source / ".git/info/exclude"
    exclude.write_text("ignored-answer.ts\n")
    (root / "pi_fixture/ignored-answer.ts").write_text("future answer\n")
    with pytest.raises(ValueError, match="changes"):
        verify_worktree(root / "pi_fixture", snap["parent_sha"])
