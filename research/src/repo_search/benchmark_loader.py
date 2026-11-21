"""Benchmark loading with evaluator/agent data isolation.

Agent-visible task payloads expose only:
  task_id, task_prompt, context_budget, agent_call_limit

Ground truth and commit metadata are evaluator-only.
"""

from __future__ import annotations

import json
import re
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
        "files",
        "relevant_symbols",
        "relevance_score",
        "rationale",
        "existing_tests",
        "target_added_tests",
        "review_status",
    }
)


class BenchmarkLoadError(ValueError):
    """Invalid benchmark artifact."""


def _research_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_tasks_document(path: Path | None = None) -> dict[str, Any]:
    tasks_path = path or (_research_root() / "benchmark" / "tasks.json")
    data = json.loads(tasks_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BenchmarkLoadError("tasks document must be a JSON object")
    return data


def iter_agent_tasks(tasks_doc: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return agent-visible task dicts (exactly the permitted fields)."""
    doc = tasks_doc if tasks_doc is not None else load_tasks_document()
    if not isinstance(doc, dict) or not isinstance(doc.get("tasks"), list):
        raise BenchmarkLoadError("tasks document must contain a tasks array")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in doc["tasks"]:
        _validate_agent_task(raw)
        if raw["task_id"] in seen:
            raise BenchmarkLoadError(f"duplicate task_id: {raw['task_id']}")
        seen.add(raw["task_id"])
        agent_task = {k: raw[k] for k in sorted(AGENT_VISIBLE_TASK_FIELDS)}
        out.append(agent_task)
    return out


def load_agent_task(task_id: str, tasks_doc: dict[str, Any] | None = None) -> dict[str, Any]:
    for task in iter_agent_tasks(tasks_doc):
        if task["task_id"] == task_id:
            return task
    raise BenchmarkLoadError(f"unknown task_id: {task_id}")


def load_ground_truth(
    task_id: str, path: Path | None = None, *, annotation_set: str = "independent"
) -> dict[str, Any]:
    """Evaluator-only loader. Must not be called from Method A/B input paths."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", task_id):
        raise BenchmarkLoadError("invalid task_id")
    if annotation_set not in {"independent", "t2_context_v1"}:
        raise BenchmarkLoadError("unknown annotation set")
    directory = _research_root() / "benchmark" / "ground_truth"
    if annotation_set != "independent":
        directory /= annotation_set
    gt_path = path or (directory / f"{task_id}.json")
    if not gt_path.is_file():
        raise BenchmarkLoadError(f"ground truth missing: {gt_path}")
    data = json.loads(gt_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("task_id") != task_id:
        raise BenchmarkLoadError("ground truth task_id mismatch")
    return data


def method_input_bundle(task_id: str, tasks_doc: dict[str, Any] | None = None) -> dict[str, Any]:
    """Payload that future Method A/B runners may receive."""
    task = load_agent_task(task_id, tasks_doc)
    # Explicitly omit ground truth
    payload = {"task": task}
    assert_no_evaluator_leakage(payload)
    return payload


def assert_no_evaluator_leakage(payload: dict[str, Any]) -> None:
    """Fail closed on the complete bundle; never read annotations to filter it."""
    if not isinstance(payload, dict) or set(payload) != {"task"}:
        raise BenchmarkLoadError("method bundle must contain exactly task")
    _validate_agent_task(payload["task"])


def _validate_agent_task(raw: Any) -> None:
    if not isinstance(raw, dict) or set(raw) != AGENT_VISIBLE_TASK_FIELDS:
        raise BenchmarkLoadError("task must contain exactly the four agent-visible fields")
    task_id = raw["task_id"]
    if not isinstance(task_id, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", task_id):
        raise BenchmarkLoadError("invalid task_id")
    for key in ("context_budget", "agent_call_limit"):
        if type(raw[key]) is not int or raw[key] <= 0:
            raise BenchmarkLoadError(f"{key} must be a positive integer")
    prompt = raw["task_prompt"]
    if not isinstance(prompt, str) or not prompt.strip():
        raise BenchmarkLoadError("task_prompt must be non-empty text")
    normalized = prompt.casefold()
    if re.search(r"(?<![0-9a-z])[0-9a-f]{7,64}(?![0-9a-z])", normalized):
        raise BenchmarkLoadError("commit/hash identifier in task_prompt")
    if any(marker in normalized for marker in (
        "diff --git", "@@ -", "/commit/", "ground_truth", "ground truth",
        "annotation_notes", "relevant_spans", "required_files", "changelog",
    )):
        raise BenchmarkLoadError("evaluator or patch marker in task_prompt")
