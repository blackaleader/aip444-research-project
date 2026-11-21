"""T2 evaluator checks on a fictional Git history; no Pi clone or API needed."""

from __future__ import annotations

import copy
import json
import subprocess
import shutil
from pathlib import Path

import pytest

from repo_search.benchmark_integrity import (
    AnnotationError, GitSource, sha256, validate_annotation, validate_schema,
    validate_recorded_evidence,
    validate_benchmark,
)
from repo_search.benchmark_loader import iter_agent_tasks, load_ground_truth

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/ground_truth.schema.json"


@pytest.fixture()
def source_case(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE).decode().strip()
    git("init", "--quiet")
    git("config", "user.name", "Fictional fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "commit.gpgsign", "false")
    git("config", "core.autocrlf", "false")
    (root / "src").mkdir()
    (root / "test").mkdir()
    data = b"export function example() {\n  return 1;\n}\n"
    (root / "src/example.ts").write_bytes(data)
    (root / "test/existing.test.ts").write_bytes(b"// existing test\n")
    git("add", ".")
    git("commit", "--quiet", "-m", "fictional parent")
    parent = git("rev-parse", "HEAD")
    (root / "src/example.ts").write_bytes(data.replace(b"1", b"2"))
    (root / "src/future.ts").write_bytes(b"export const future = 2;\n")
    (root / "test/future.test.ts").write_bytes(b"// future test\n")
    git("add", ".")
    git("commit", "--quiet", "-m", "fictional target")
    target = git("rev-parse", "HEAD")
    repo = GitSource(root)
    snapshot = {"task_id": "pi_fixture", "parent_sha": parent, "target_sha": target,
                "parent_tree_sha": git("rev-parse", parent + "^{tree}"),
                "target_tree_sha": git("rev-parse", target + "^{tree}"),
                "expected_parent_prefix": parent[:7], "verification_status": "verified"}
    annotation = {
        "task_id": "pi_fixture", "snapshot_sha": parent, "annotation_version": "t2-1.0",
        "annotation_set": "t2_context_v1", "review_status": "preliminary_self_validated",
        "human_review_status": "pending_student_and_peer_review", "required_files": ["src/example.ts"],
        "files": [{"path": "src/example.ts", "relevance": "essential", "relevance_score": 2,
                   "rationale": "Contains the fictional behavior", "symbols": ["example"],
                   "content_sha256": sha256(data), "blob_sha": repo.tree(parent)["src/example.ts"]["blob_sha"],
                   "line_spans": [{"start_line": 1, "end_line": 3, "symbol": "example",
                                   "anchor": "function example", "content_sha256": sha256(data)}]}],
        "relevant_symbols": [{"path": "src/example.ts", "symbol": "example", "relevance": "essential"}],
        "relevant_spans": [{"path": "src/example.ts", "start_line": 1, "end_line": 3, "relevance": "essential"}],
        "existing_tests": ["test/existing.test.ts"], "target_added_tests": ["test/future.test.ts"],
        "target_added_files_not_retrievable": ["src/future.ts", "test/future.test.ts"],
        "annotation_notes": ["Fictional integrity fixture; not experimental evidence."],
    }
    return root, repo, snapshot, annotation


def test_valid_fictional_annotation(source_case):
    _, repo, snapshot, annotation = source_case
    report = validate_annotation(repo, annotation, snapshot, SCHEMA)
    assert report["files"] == report["essential_files"] == report["spans"] == 1
    assert report["human_review_status"] == "pending_student_and_peer_review"


@pytest.mark.parametrize("change", [
    "wrong_snapshot", "short_sha", "wrong_grade", "required_missing", "duplicate_file",
    "stale_file_hash", "stale_span_hash", "missing_proof", "wrong_anchor", "future_file",
    "out_of_range", "boolean_line", "top_spans_disagree", "symbols_disagree",
    "future_inventory_incomplete", "existing_test_missing", "future_test_is_existing", "path_escape",
])
def test_invalid_judgments_fail_closed(source_case, change):
    _, repo, snapshot, annotation = source_case
    ann = copy.deepcopy(annotation)
    f = ann["files"][0]
    if change == "wrong_snapshot": ann["snapshot_sha"] = snapshot["target_sha"]
    elif change == "short_sha": ann["snapshot_sha"] = snapshot["parent_sha"][:7]
    elif change == "wrong_grade": f["relevance_score"] = 1
    elif change == "required_missing": ann["required_files"] = []
    elif change == "duplicate_file": ann["files"].append(copy.deepcopy(f))
    elif change == "stale_file_hash": f["content_sha256"] = "0" * 64
    elif change == "stale_span_hash": f["line_spans"][0]["content_sha256"] = "0" * 64
    elif change == "missing_proof": f.pop("blob_sha")
    elif change == "wrong_anchor": f["line_spans"][0]["anchor"] = "not present"
    elif change == "future_file": f["path"] = "src/future.ts"
    elif change == "out_of_range": f["line_spans"][0]["end_line"] = 500
    elif change == "boolean_line": f["line_spans"][0]["start_line"] = True
    elif change == "top_spans_disagree": ann["relevant_spans"] = []
    elif change == "symbols_disagree": ann["relevant_symbols"] = []
    elif change == "future_inventory_incomplete": ann["target_added_files_not_retrievable"] = []
    elif change == "existing_test_missing": ann["existing_tests"] = ["test/no.test.ts"]
    elif change == "future_test_is_existing": ann["target_added_tests"] = ["test/existing.test.ts"]
    elif change == "path_escape": f["path"] = "../example.ts"
    with pytest.raises(AnnotationError):
        validate_annotation(repo, ann, snapshot, SCHEMA)


def test_target_parent_and_tree_must_match(source_case):
    _, repo, snapshot, annotation = source_case
    for changes in [{"parent_sha": snapshot["target_sha"]}, {"parent_tree_sha": "0" * 40},
                    {"target_tree_sha": "0" * 40}, {"verification_status": "verification_failed"}]:
        with pytest.raises(AnnotationError):
            validate_annotation(repo, annotation, {**snapshot, **changes}, SCHEMA)


def test_t2_set_uses_existing_contract_and_preserves_baseline():
    doc = json.loads((ROOT / "benchmark/task_sets/t2_context_v1.json").read_text())
    validate_schema(doc, ROOT / "schemas/tasks.schema.json")
    tasks = iter_agent_tasks(doc)
    assert len(tasks) == 8
    for task in tasks:
        proposal = load_ground_truth(task["task_id"], annotation_set="t2_context_v1")
        validate_schema(proposal, SCHEMA)
        assert proposal["implementation_origin"] == "teammate_2"
        assert proposal["human_review_status"] == "pending_student_and_peer_review"
        assert proposal["review_status"] != "validated"
    baseline = load_ground_truth("pi_package_filtering")
    assert baseline["annotation_version"] == "1.0"
    assert baseline["review_status"] == "preliminary_self_validated"


def test_unknown_annotation_set_and_path_task_are_rejected():
    with pytest.raises(ValueError): load_ground_truth("pi_fixture", annotation_set="../outside")
    with pytest.raises(ValueError): load_ground_truth("../outside")




def test_terminal_newline_matches_existing_chunker_representation(source_case):
    _, repo, snapshot, _ = source_case
    data = repo.blob(snapshot["parent_sha"], "src/example.ts")
    validate_recorded_evidence(repo, {"path": "src/example.ts", "start_line": 1, "end_line": 4,
                                     "text": data.decode()}, snapshot["parent_sha"])




def test_independent_pilot_validation_does_not_require_unused_candidate_history(source_case, tmp_path):
    _, repo, snap, ann = source_case
    root = tmp_path / "bundle"
    (root / "schemas").mkdir(parents=True)
    for name in ["tasks.schema.json", "snapshots.schema.json", "ground_truth.schema.json"]:
        shutil.copyfile(ROOT / "schemas" / name, root / "schemas" / name)
    def write(relative, data):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    selected = {**snap, "repository_url": "https://example.invalid/fictional",
                "parent_prefix_verified": True, "pilot_status": "pilot", "parent_list": [snap["parent_sha"]]}
    unused = {"task_id": "pi_unused", "repository_url": "https://example.invalid/fictional",
              "expected_parent_prefix": "aaaaaaa", "parent_prefix_verified": False,
              "pilot_status": "candidate", "verification_status": "verification_failed",
              "parent_sha": None, "target_sha": None}
    write("benchmark/manifests/snapshots.json", {"schema_version": "1.2", "status": "verified_partial",
                                              "snapshots": [selected, unused]})
    write("benchmark/tasks.json", {"schema_version": "2.0", "tasks": [{"task_id": "pi_fixture",
          "task_prompt": "Find context for the fictional example behavior.", "context_budget": 6000, "agent_call_limit": 5}]})
    write("benchmark/ground_truth/pi_fixture.json", ann)
    assert validate_benchmark(root, repo, "independent")["task_count"] == 1


def test_recorded_evidence_provenance_is_checked_without_relevance_scoring(source_case):
    _, repo, snapshot, _ = source_case
    text = "export function example() {\n  return 1;\n}"
    item = {"path": "src/example.ts", "start_line": 1, "end_line": 3,
            "text": text, "content_hash": sha256(text.encode())}
    validate_recorded_evidence(repo, item, snapshot["parent_sha"])
    for patch in [{"text": "invented"}, {"content_hash": "0" * 64},
                  {"snapshot_sha": snapshot["target_sha"]}, {"path": "src/future.ts"}]:
        with pytest.raises(AnnotationError):
            validate_recorded_evidence(repo, {**item, **patch}, snapshot["parent_sha"])
