#!/usr/bin/env python3
"""Deterministically build the proposed T2 set from reviewed decision inputs.

This never replaces the frozen pilot prompts or independent annotations.
Decision inputs are AI-assisted drafts; human relevance review is still required.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from repo_search.benchmark_integrity import (
    ANNOTATION_SET, AnnotationError, GitSource, overlap_rows, sha256, span_bytes, validate_annotation,
)


def encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def generated_files(root: Path, repo: GitSource) -> dict[str, bytes]:
    decisions = json.loads((root / f"benchmark/reviews/{ANNOTATION_SET}/annotation_decisions.json").read_text())
    manifest = json.loads((root / "benchmark/manifests/snapshots.json").read_text())
    snapshots = {s["task_id"]: s for s in manifest["snapshots"]}
    tasks, annotations, output = [], [], {}
    if len({d["task_id"] for d in decisions["tasks"]}) != len(decisions["tasks"]):
        raise AnnotationError("duplicate decision task IDs")
    for decision in decisions["tasks"]:
        tid = decision["task_id"]
        snap = snapshots[tid]
        parent, target = snap["parent_sha"], snap["target_sha"]
        if repo.parents(target) != [parent]:
            raise AnnotationError("decision refers to a mismatched target/parent")
        files, relevant_symbols, relevant_spans = [], [], []
        for item in decision["files"]:
            path = item["path"]
            data = repo.blob(parent, path)
            symbols = list(dict.fromkeys(span["symbol"] for span in item["spans"]))
            line_spans = []
            for span in item["spans"]:
                part = span_bytes(data, span["start_line"], span["end_line"])
                if span["anchor"] not in part.decode("utf-8"):
                    raise AnnotationError(f"symbol anchor does not match parent: {tid}:{path}")
                line_spans.append({**span, "content_sha256": sha256(part)})
                relevant_spans.append({"path": path, "start_line": span["start_line"],
                                       "end_line": span["end_line"], "relevance": item["relevance"]})
            relevant_symbols.extend({"path": path, "symbol": s, "relevance": item["relevance"]} for s in symbols)
            files.append({"path": path, "relevance": item["relevance"],
                          "relevance_score": 2 if item["relevance"] == "essential" else 1,
                          "rationale": item["rationale"], "symbols": symbols, "line_spans": line_spans,
                          "blob_sha": repo.tree(parent)[path]["blob_sha"], "content_sha256": sha256(data)})
        changes = repo.changes(parent, target)
        added = sorted(p for p, status in changes.items() if status == "A")
        new_tests = [p for p in added if "/test/" in p and p.endswith((".test.ts", ".test.js"))]
        modified_tests = sorted(p for p, status in changes.items()
                                if status == "M" and "/test/" in p and p.endswith((".test.ts", ".test.js")))
        annotation = {
            "task_id": tid, "snapshot_sha": parent, "annotation_version": "t2-1.0",
            "annotation_set": ANNOTATION_SET, "implementation_origin": "teammate_2",
            "review_status": "preliminary_self_validated", "human_review_status": "pending_student_and_peer_review",
            "required_files": [f["path"] for f in files if f["relevance"] == "essential"],
            "files": files, "relevant_symbols": relevant_symbols, "relevant_spans": relevant_spans,
            "existing_tests": [t["path"] for t in decision["existing_tests"]],
            "target_added_tests": new_tests, "tests_modified_by_target": modified_tests,
            "target_added_files_not_retrievable": added,
            "test_availability": {"execution_status": "not_executed",
                                  "pre_existing": decision["existing_tests"],
                                  "target_modified_test_files_note": "Only parent contents are retrieval eligible; later-added test cases are future evidence."},
            "annotation_notes": [decision["annotation_notes"],
                                 "AI-assisted T2 proposal. Structural checks are separate from pending human relevance review.",
                                 "This annotation is tied to the T2 task prompt; do not silently mix it into pilot-v1.0 scoring."],
            "unjudged_policy": "Unlisted files are unjudged; disclose any closed-world scoring convention and review additional useful evidence without method identity before freezing.",
        }
        validate_annotation(repo, annotation, snap, root / "schemas/ground_truth.schema.json")
        annotations.append(annotation)
        output[f"benchmark/ground_truth/{ANNOTATION_SET}/{tid}.json"] = encoded(annotation)
        tasks.append({"task_id": tid, "task_prompt": decision["task_prompt"],
                      "context_budget": 6000, "agent_call_limit": 5})
    task_doc = {"schema_version": "2.0", "task_set_id": ANNOTATION_SET,
                "status": "proposed_not_activated_in_frozen_pilot", "tasks": tasks}
    output[f"benchmark/task_sets/{ANNOTATION_SET}.json"] = encoded(task_doc)
    cards = ["# T2 proposed task cards", "",
             "Version: t2_context_v1. Human relevance review and main inclusion are pending.",
             "These behavior-focused cards disclose no solution paths or commit identifiers.",
             "The frozen pilot keeps its original prompts. Evaluator annotations are stored separately.", ""]
    for task in tasks:
        cards.extend([f"## {task['task_id']}", "", task["task_prompt"], ""])
    output["docs/t2_task_cards.md"] = ("\n".join(cards).rstrip() + "\n").encode()
    overlap = overlap_rows(repo, annotations, snapshots)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(overlap[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(overlap)
    output[f"benchmark/reviews/{ANNOTATION_SET}/overlap.csv"] = buffer.getvalue().encode()
    qrels = io.StringIO(newline="")
    writer_qrels = csv.writer(qrels, delimiter="\t", lineterminator="\n")
    writer_qrels.writerow(["query-id", "corpus-id", "score"])
    for ann in sorted(annotations, key=lambda a: a["task_id"]):
        for item in sorted(ann["files"], key=lambda f: f["path"]):
            writer_qrels.writerow([ann["task_id"], f"{ann['snapshot_sha']}:{item['path']}", item["relevance_score"]])
    output[f"benchmark/reviews/{ANNOTATION_SET}/qrels.tsv"] = qrels.getvalue().encode()
    baseline_tasks = json.loads((root / "benchmark/tasks.json").read_text())["tasks"]
    proposals = {a["task_id"]: a for a in annotations}
    comparisons = []
    for task in baseline_tasks:
        tid = task["task_id"]
        original = json.loads((root / f"benchmark/ground_truth/{tid}.json").read_text())
        proposed = proposals[tid]
        old = {f["path"]: f["relevance"] for f in original["files"]}
        new = {f["path"]: f["relevance"] for f in proposed["files"]}
        comparisons.append({"task_id": tid, "baseline_preserved": True,
                            "proposed_prompt_differs": next(t["task_prompt"] for t in tasks if t["task_id"] == tid) != task["task_prompt"],
                            "added_judgments": sorted(set(new) - set(old)),
                            "omitted_judgments": sorted(set(old) - set(new)),
                            "label_changes": [{"path": p, "baseline": old[p], "proposal": new[p]}
                                              for p in sorted(set(old) & set(new)) if old[p] != new[p]],
                            "decision": "pending blinded human review; no automatic overwrite"})
    output[f"benchmark/reviews/{ANNOTATION_SET}/pilot_comparison.json"] = encoded(comparisons)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-path", required=True, type=Path)
    parser.add_argument("--check", action="store_true", help="Compare regenerated bytes; write nothing")
    args = parser.parse_args()
    try:
        output = generated_files(ROOT, GitSource(args.repo_path))
        differences = []
        for relative, data in output.items():
            path = ROOT / relative
            if args.check:
                if not path.is_file() or path.read_bytes() != data:
                    differences.append(relative)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        if differences:
            raise AnnotationError("regeneration differs: " + ", ".join(differences))
    except (AnnotationError, ValueError, KeyError, OSError, UnicodeError) as error:
        print(f"BUILD ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "passed", "generated_artifacts": len(output),
                      "mode": "check_only" if args.check else "written", "annotation_set": ANNOTATION_SET}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
