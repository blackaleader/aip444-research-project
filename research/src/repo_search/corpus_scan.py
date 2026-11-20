"""Deterministic repository scanning for Stage 5 corpus preparation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

EXCLUDE_DIR_NAMES = frozenset(
    {
        ".git",
        "node_modules",
        "dist",
        "build",
        ".turbo",
        ".next",
        ".cache",
        "coverage",
        ".nyc_output",
        "__pycache__",
        ".venv",
        "venv",
        "target",
        "vendor",
        ".idea",
        ".vscode",
        "tmp",
        "temp",
        ".artifacts",
    }
)

EXCLUDE_FILE_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tgz",
    ".7z",
    ".rar",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".wasm",
    ".bin",
    ".o",
    ".a",
    ".class",
    ".jar",
    ".map",
    ".min.js",
    ".min.css",
    ".lock",
    ".mp4",
    ".mp3",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
)

INCLUDE_SUFFIXES = (
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".json",
    ".md",
    ".mdx",
    ".txt",
    ".toml",
    ".yml",
    ".yaml",
    ".css",
    ".html",
    ".sh",
    ".bash",
    ".ps1",
    ".py",
    ".rs",
    ".go",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
)

INCLUDE_BASENAMES = frozenset(
    {
        "AGENTS.md",
        "README",
        "README.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "LICENSE.md",
        "Makefile",
        "Dockerfile",
        ".gitignore",
        ".npmrc",
        "package.json",
        "tsconfig.json",
        "jsconfig.json",
        "test.sh",
    }
)

MAX_FILE_BYTES = 1_500_000


@dataclass(frozen=True)
class ScannedFile:
    path: str  # repo-relative POSIX path
    abs_path: Path
    size_bytes: int


def _to_posix(rel: Path) -> str:
    return rel.as_posix()


def should_exclude_dir(name: str) -> bool:
    # Exclude known build/cache/VCS dirs. Keep other dot-dirs (e.g. .github) indexable.
    if name in EXCLUDE_DIR_NAMES:
        return True
    if name == ".git":
        return True
    return False


def should_include_file(path: Path) -> bool:
    name = path.name
    if name in INCLUDE_BASENAMES:
        return True
    lower = name.lower()
    if any(lower.endswith(suf) for suf in EXCLUDE_FILE_SUFFIXES):
        return False
    if any(lower.endswith(suf) for suf in INCLUDE_SUFFIXES):
        return True
    # Allow extensionless short config-like names already covered; default deny.
    return False


def scan_repository(root: Path) -> tuple[list[ScannedFile], list[str]]:
    """Return deterministically ordered included files and exclusion notes."""
    root = root.resolve()
    included: list[ScannedFile] = []
    excluded_notes: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded dirs in-place for os.walk; keep deterministic order.
        dirnames[:] = sorted(d for d in dirnames if not should_exclude_dir(d))
        rel_dir = Path(dirpath).relative_to(root)
        for name in sorted(filenames):
            abs_path = Path(dirpath) / name
            rel = rel_dir / name if str(rel_dir) != "." else Path(name)
            rel_posix = _to_posix(rel)
            if not should_include_file(abs_path):
                excluded_notes.append(f"suffix/policy:{rel_posix}")
                continue
            try:
                size = abs_path.stat().st_size
            except OSError:
                excluded_notes.append(f"unreadable:{rel_posix}")
                continue
            if size > MAX_FILE_BYTES:
                excluded_notes.append(f"too_large:{rel_posix}:{size}")
                continue
            if size == 0:
                excluded_notes.append(f"empty:{rel_posix}")
                continue
            included.append(ScannedFile(path=rel_posix, abs_path=abs_path, size_bytes=size))

    included.sort(key=lambda f: f.path)
    return included, excluded_notes
