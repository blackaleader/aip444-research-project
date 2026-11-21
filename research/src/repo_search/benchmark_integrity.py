"""Offline T2 annotation validation against schemas and immutable Git objects.

Never import this evaluator module into a method/controller or agent tool.
Source checks establish provenance, not human agreement about relevance.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

from repo_search.benchmark_loader import iter_agent_tasks
from repo_search.corpus_scan import MAX_FILE_BYTES, should_exclude_dir, should_include_file

ANNOTATION_SET = "t2_context_v1"
GRADES = {"essential": 2, "supporting": 1, "irrelevant": 0}


class AnnotationError(ValueError):
    """A benchmark artifact cannot be trusted for offline scoring."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def checked_sha(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
        raise AnnotationError("expected a complete lowercase commit identifier")
    return value


def checked_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise AnnotationError("expected a canonical relative source path")
    p = PurePosixPath(value)
    if p.is_absolute() or ".." in p.parts or str(p) != value or value == "." or any(c in value for c in "\0\r\n"):
        raise AnnotationError("path is not canonical and relative")
    return value


def span_bytes(data: bytes, start: Any, end: Any) -> bytes:
    lines = data.splitlines(keepends=True)
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        raise AnnotationError("invalid inclusive source line range")
    return b"".join(lines[start - 1:end])


class GitSource:
    """Read Git objects without checking out, changing files or following links."""

    def __init__(self, path: Path):
        self.path = path.resolve()
        self.run("rev-parse", "--git-dir")

    def run(self, *args: str) -> bytes:
        result = subprocess.run(["git", "--no-pager", "-C", str(self.path), *args],
                                capture_output=True, check=False)
        if result.returncode:
            raise AnnotationError(result.stderr.decode("utf-8", errors="replace").strip())
        return result.stdout

    @lru_cache(maxsize=32)
    def tree(self, sha: str) -> dict[str, dict[str, str]]:
        result = {}
        for row in self.run("ls-tree", "-r", "-z", checked_sha(sha)).split(b"\0"):
            if row:
                meta, path = row.split(b"\t", 1)
                mode, kind, oid = meta.decode("ascii").split()
                result[path.decode("utf-8")] = {"mode": mode, "kind": kind, "blob_sha": oid}
        return result

    @lru_cache(maxsize=256)
    def blob(self, sha: str, path: str) -> bytes:
        entry = self.tree(sha).get(checked_path(path))
        if not entry or entry["kind"] != "blob" or entry["mode"] not in {"100644", "100755"}:
            raise AnnotationError(f"not a regular snapshot file: {path}")
        return self.run("cat-file", "blob", entry["blob_sha"])

    def parents(self, sha: str) -> list[str]:
        headers = self.run("cat-file", "commit", checked_sha(sha)).split(b"\n\n", 1)[0]
        return [line[7:].decode("ascii") for line in headers.splitlines() if line.startswith(b"parent ")]

    def changes(self, parent: str, target: str) -> dict[str, str]:
        parts = self.run("diff", "--no-renames", "--name-status", "-z", checked_sha(parent), checked_sha(target)).split(b"\0")
        parts = parts[:-1] if parts and not parts[-1] else parts
        if len(parts) % 2:
            raise AnnotationError("unexpected Git changed-file inventory")
        return {parts[i + 1].decode("utf-8"): parts[i].decode("ascii") for i in range(0, len(parts), 2)}


def validate_schema(document: Any, schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda e: str(list(e.path)))
    if errors:
        error = errors[0]
        raise AnnotationError(f"{schema_path.name} at {list(error.path)}: {error.message}")


def _eligible(path: str, data: bytes) -> bool:
    return (not any(should_exclude_dir(part) for part in PurePosixPath(path).parts)
            and should_include_file(Path(path)) and 0 < len(data) <= MAX_FILE_BYTES)


def validate_annotation(
    repo: GitSource, annotation: dict[str, Any], snapshot: dict[str, Any], schema: Path,
) -> dict[str, Any]:
    validate_schema(annotation, schema)
    parent, target = checked_sha(snapshot["parent_sha"]), checked_sha(snapshot["target_sha"])
    if snapshot["verification_status"] != "verified" or repo.parents(target) != [parent]:
        raise AnnotationError("target does not have exactly the recorded parent")
    if annotation["task_id"] != snapshot["task_id"] or annotation["snapshot_sha"] != parent:
        raise AnnotationError("annotation task/snapshot mismatch")
    for key, commit in (("parent_tree_sha", parent), ("target_tree_sha", target)):
        expected = repo.run("rev-parse", commit + "^{tree}").decode().strip()
        if snapshot.get(key) != expected:
            raise AnnotationError(f"manifest {key} differs from Git")
    if not parent.startswith(snapshot["expected_parent_prefix"]):
        raise AnnotationError("parent prefix differs from candidate definition")

    strict_proof = annotation.get("annotation_set") == ANNOTATION_SET
    paths: set[str] = set()
    essentials: set[str] = set()
    spans: list[tuple[str, int, int, str]] = []
    symbols: set[tuple[str, str, str]] = set()
    for item in annotation["files"]:
        path = checked_path(item["path"])
        if path in paths:
            raise AnnotationError("duplicate file judgment")
        paths.add(path)
        data = repo.blob(parent, path)
        data.decode("utf-8")
        if not _eligible(path, data):
            raise AnnotationError(f"annotated path outside Stage 5 source policy: {path}")
        if GRADES[item["relevance"]] != item["relevance_score"]:
            raise AnnotationError("relevance label/score mismatch")
        if not item["rationale"].strip() or not item["symbols"] or not item["line_spans"]:
            raise AnnotationError("file judgment missing rationale, symbols or spans")
        if item["relevance"] == "essential":
            essentials.add(path)
        if strict_proof or "content_sha256" in item:
            if item.get("content_sha256") != sha256(data) or item.get("blob_sha") != repo.tree(parent)[path]["blob_sha"]:
                raise AnnotationError("stale file content proof")
        for span in item["line_spans"]:
            part = span_bytes(data, span["start_line"], span["end_line"])
            if strict_proof or "content_sha256" in span:
                if span.get("content_sha256") != sha256(part):
                    raise AnnotationError("stale span content proof")
            if span.get("anchor") and span["anchor"] not in part.decode("utf-8"):
                raise AnnotationError("source symbol anchor absent from span")
            if span.get("symbol") and span["symbol"] not in item["symbols"]:
                raise AnnotationError("span symbol not listed on file")
            spans.append((path, span["start_line"], span["end_line"], item["relevance"]))
        symbols.update((path, symbol, item["relevance"]) for symbol in item["symbols"])
    if not essentials or set(annotation["required_files"]) != essentials or len(set(annotation["required_files"])) != len(annotation["required_files"]):
        raise AnnotationError("required_files must equal the unique essential-file set")
    if strict_proof:
        top_spans = [(s["path"], s["start_line"], s["end_line"], s["relevance"]) for s in annotation["relevant_spans"]]
        if sorted(spans) != sorted(top_spans):
            raise AnnotationError("top-level relevant_spans disagree with file judgments")
        top_symbols = {(s["path"], s["symbol"], s["relevance"]) for s in annotation["relevant_symbols"]}
        if symbols != top_symbols:
            raise AnnotationError("top-level relevant_symbols disagree with file judgments")

    changes = repo.changes(parent, target)
    future = {path for path, status in changes.items() if status == "A"}
    if paths & future:
        raise AnnotationError("future file included as pre-change evidence")
    recorded_future = annotation.get("target_added_files_not_retrievable", [])
    if strict_proof and set(recorded_future) != future:
        raise AnnotationError("target-added file inventory differs from Git")
    for path in recorded_future:
        if path in repo.tree(parent) or path not in future:
            raise AnnotationError("incorrect target-added file inventory")
    for path in annotation["existing_tests"]:
        repo.blob(parent, checked_path(path))
    for reference in annotation["target_added_tests"]:
        path, _, case = reference.partition("::")
        repo.blob(target, checked_path(path))
        if case:
            if changes.get(path) != "M":
                raise AnnotationError("new test-case reference must name a modified test file")
        elif path not in future:
            raise AnnotationError("new test file already exists in the parent")
    for path in annotation.get("tests_modified_by_target", []):
        repo.blob(parent, checked_path(path))
        if changes.get(path) != "M":
            raise AnnotationError("modified test inventory differs from Git")
    return {"task_id": annotation["task_id"], "files": len(paths), "essential_files": len(essentials),
            "spans": len(spans), "structural_validation": "passed",
            "human_review_status": annotation.get("human_review_status", "not_recorded")}


def validate_benchmark(root: Path, repo: GitSource, annotation_set: str = ANNOTATION_SET) -> dict[str, Any]:
    if annotation_set not in {"independent", ANNOTATION_SET}:
        raise AnnotationError("unknown annotation set")
    manifest = json.loads((root / "benchmark/manifests/snapshots.json").read_text())
    validate_schema(manifest, root / "schemas/snapshots.schema.json")
    snapshots = {s["task_id"]: s for s in manifest["snapshots"]}
    if len(snapshots) != len(manifest["snapshots"]):
        raise AnnotationError("duplicate manifest task identifiers")
    path = root / "benchmark/tasks.json" if annotation_set == "independent" else root / f"benchmark/task_sets/{annotation_set}.json"
    task_doc = json.loads(path.read_text())
    validate_schema(task_doc, root / "schemas/tasks.schema.json")
    tasks = iter_agent_tasks(task_doc)
    # The independent pilot must not require unused candidate history.
    for task in tasks:
        snap = snapshots[task["task_id"]]
        if snap["verification_status"] != "verified" or repo.parents(checked_sha(snap["target_sha"])) != [checked_sha(snap["parent_sha"])]:
            raise AnnotationError("unverified or mismatched selected snapshot")
    directory = root / "benchmark/ground_truth"
    if annotation_set != "independent":
        directory /= annotation_set
    files = sorted(directory.glob("*.json"))
    by_task = {}
    for path in files:
        doc = json.loads(path.read_text())
        if doc["task_id"] in by_task or path.stem != doc["task_id"]:
            raise AnnotationError("annotation filename/task identity mismatch")
        by_task[doc["task_id"]] = doc
    if set(by_task) != {t["task_id"] for t in tasks}:
        raise AnnotationError("task set and annotation coverage disagree")
    rows = [validate_annotation(repo, by_task[t["task_id"]], snapshots[t["task_id"]],
                                root / "schemas/ground_truth.schema.json") for t in tasks]
    return {"annotation_set": annotation_set, "status": "passed", "tasks": rows,
            "task_count": len(rows), "file_judgments": sum(r["files"] for r in rows),
            "source_spans": sum(r["spans"] for r in rows),
            "scope": "source/schema integrity only; human relevance agreement and experiment results are not established"}


def overlap_rows(repo: GitSource, annotations: list[dict[str, Any]], snapshots: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for a, b in itertools.combinations(sorted(annotations, key=lambda a: a["task_id"]), 2):
        aid, bid = a["task_id"], b["task_id"]
        essential_a, essential_b = set(a["required_files"]), set(b["required_files"])
        all_a, all_b = {f["path"] for f in a["files"]}, {f["path"] for f in b["files"]}
        def ancestor(left: str, right: str) -> bool:
            result = subprocess.run(["git", "-C", str(repo.path), "merge-base", "--is-ancestor", left, right], capture_output=True)
            if result.returncode not in (0, 1):
                raise AnnotationError("cannot determine historical task overlap")
            return result.returncode == 0
        rows.append({"task_a": aid, "task_b": bid,
                     "essential_file_jaccard": round(len(essential_a & essential_b) / len(essential_a | essential_b), 4),
                     "all_relevant_file_jaccard": round(len(all_a & all_b) / len(all_a | all_b), 4),
                     "shared_essential_files": ";".join(sorted(essential_a & essential_b)),
                     "a_target_in_b_parent": ancestor(snapshots[aid]["target_sha"], snapshots[bid]["parent_sha"]),
                     "b_target_in_a_parent": ancestor(snapshots[bid]["target_sha"], snapshots[aid]["parent_sha"])})
    return rows


def validate_recorded_evidence(repo: GitSource, record: dict[str, Any], expected_sha: str) -> None:
    """Check Stage 5/6 displayed text, whose hash differs from raw-byte span hashes.

    The frozen chunker normalizes CRLF/CR and joins inclusive lines with LF.
    Its terminal empty line is valid; no source code is returned by this checker.
    """
    checked_sha(expected_sha)
    if record.get("snapshot_sha", expected_sha) != expected_sha:
        raise AnnotationError("evidence snapshot differs from trial snapshot")
    path = checked_path(record.get("path"))
    data = repo.blob(expected_sha, path)
    if not _eligible(path, data):
        raise AnnotationError("evidence is outside the Stage 5 source policy")
    text = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    start, end = record.get("start_line"), record.get("end_line")
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= len(lines):
        raise AnnotationError("invalid displayed evidence line bounds")
    expected = "\n".join(lines[start - 1:end])
    if record.get("text") != expected:
        raise AnnotationError("evidence text differs from the pinned source span")
    if record.get("content_hash") is not None and record["content_hash"] != sha256(expected.encode("utf-8")):
        raise AnnotationError("evidence displayed-text hash is stale")
