"""Benchmark loading with evaluator/agent data isolation.

Agent-visible task payloads expose only:
  task_id, task_prompt, context_budget, agent_call_limit

Ground truth and commit metadata are evaluator-only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

AGENT_VISIBLE_TASK_FIELDS = frozenset(
    {"task_id", "task_prompt", "context_budget", "agent_call_limit"}
)

FORBIDDEN_AGENT_KEYS = frozenset(
    {
        "target_sha",
        "parent_sha",
        "snapshot_sha",
        "ground_truth",
        "changed_files",
        "commit_message",
        "target_subject",
        "diff",
        "annotation_notes",
        "relevant_spans",
        "required_files",
    }
)


class BenchmarkLoadError(ValueError):
    """Invalid benchmark artifact."""


def _research_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_tasks_document(path: Path | None = None) -> dict[str, Any]:
    tasks_path = path or (_research_root() / "benchmark" / "tasks.json")
    return json.loads(tasks_path.read_text(encoding="utf-8"))


def iter_agent_tasks(tasks_doc: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return agent-visible task dicts (exactly the permitted fields)."""
    doc = tasks_doc if tasks_doc is not None else load_tasks_document()
    out: list[dict[str, Any]] = []
    for raw in doc.get("tasks", []):
        missing = AGENT_VISIBLE_TASK_FIELDS - set(raw)
        if missing:
            raise BenchmarkLoadError(f"task missing fields {sorted(missing)}: {raw.get('task_id')}")
        agent_task = {k: raw[k] for k in sorted(AGENT_VISIBLE_TASK_FIELDS)}
        extra = set(agent_task) - AGENT_VISIBLE_TASK_FIELDS
        if extra:
            raise BenchmarkLoadError(f"unexpected agent fields: {extra}")
        for bad in FORBIDDEN_AGENT_KEYS:
            if bad in raw:
                # Present in source file is a schema violation for Stage 3 tasks.json
                raise BenchmarkLoadError(
                    f"evaluator-only key {bad!r} must not appear on task {raw.get('task_id')}"
                )
        out.append(agent_task)
    return out


def load_agent_task(task_id: str, tasks_doc: dict[str, Any] | None = None) -> dict[str, Any]:
    for task in iter_agent_tasks(tasks_doc):
        if task["task_id"] == task_id:
            return task
    raise BenchmarkLoadError(f"unknown task_id: {task_id}")


def load_ground_truth(task_id: str, path: Path | None = None) -> dict[str, Any]:
    """Evaluator-only loader. Must not be called from Method A/B input paths."""
    gt_path = path or (_research_root() / "benchmark" / "ground_truth" / f"{task_id}.json")
    if not gt_path.is_file():
        raise BenchmarkLoadError(f"ground truth missing: {gt_path}")
    data = json.loads(gt_path.read_text(encoding="utf-8"))
    if data.get("task_id") != task_id:
        raise BenchmarkLoadError("ground truth task_id mismatch")
    return data


def method_input_bundle(task_id: str, tasks_doc: dict[str, Any] | None = None) -> dict[str, Any]:
    """Payload that future Method A/B runners may receive."""
    task = load_agent_task(task_id, tasks_doc)
    # Explicitly omit ground truth
    return {"task": task}


def assert_no_evaluator_leakage(payload: dict[str, Any]) -> None:
    blob = json.dumps(payload)
    for key in FORBIDDEN_AGENT_KEYS:
        if key in payload.get("task", {}):
            raise BenchmarkLoadError(f"leakage: {key} in task payload")
    # Stronger: raw SHA-looking leakage from known pilots should not appear in prompt
    prompt = payload.get("task", {}).get("task_prompt", "")
    for needle in (
        "40c256c",
        "bfa6862",
        "ef1fc31",
        "dd838d0",
        "ground_truth",
        "CHANGELOG",
    ):
        if needle in prompt:
            raise BenchmarkLoadError(f"leakage marker {needle!r} in task_prompt")
    if "snapshot_sha" in blob and "snapshot_sha" in payload:
        raise BenchmarkLoadError("snapshot_sha must not be in method input bundle")
