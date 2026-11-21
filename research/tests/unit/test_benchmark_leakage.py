"""T2 regression tests for agent-visible benchmark input isolation."""

from __future__ import annotations


import pytest

import repo_search.benchmark_loader as loader


def task():
    return {"task_id": "pi_fixture", "task_prompt": "Find repository context for a fictional behavior change.",
            "context_budget": 6000, "agent_call_limit": 5}


@pytest.mark.parametrize("key", ["ground_truth", "snapshot_sha", "target_sha", "files", "relevant_spans", "metadata"])
def test_task_and_bundle_reject_extra_fields(key):
    raw = {**task(), key: {"nested": {"required_files": ["secret.ts"]}}}
    with pytest.raises(loader.BenchmarkLoadError): loader.iter_agent_tasks({"tasks": [raw]})
    with pytest.raises(loader.BenchmarkLoadError): loader.assert_no_evaluator_leakage({"task": task(), key: raw[key]})


@pytest.mark.parametrize("text", [
    "37067e0", "E40126F", "835296b1d7d999100ee1c465b4958031d0bb5adc",
    "bfa6862400d0aaa3ebf3c09a44a2479487f470f1", "diff --git a/x b/x", "@@ -1 +2 @@",
    "https://github.com/x/y/commit/answer", "Ground_Truth", "read the ground truth", "CHANGELOG.md",
])
def test_hash_patch_and_evaluator_markers_are_not_prompts(text):
    with pytest.raises(loader.BenchmarkLoadError):
        loader.method_input_bundle("pi_fixture", {"tasks": [{**task(), "task_prompt": text}]})


@pytest.mark.parametrize("field,value", [
    ("task_prompt", {"ground_truth": "answer"}), ("task_prompt", []),
    ("context_budget", True), ("context_budget", -1), ("context_budget", "6000"),
    ("agent_call_limit", 5.0), ("agent_call_limit", {"files": []}), ("task_id", "../answer"),
])
def test_nested_or_malformed_allowed_values_are_rejected(field, value):
    with pytest.raises(loader.BenchmarkLoadError):
        loader.iter_agent_tasks({"tasks": [{**task(), field: value}]})


def test_duplicate_task_ids_rejected():
    with pytest.raises(loader.BenchmarkLoadError): loader.iter_agent_tasks({"tasks": [task(), task()]})


def test_method_input_construction_never_loads_ground_truth(monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("evaluator loader called by method path")
    monkeypatch.setattr(loader, "load_ground_truth", forbidden)
    bundle = loader.method_input_bundle("pi_fixture", {"tasks": [task()]})
    assert bundle == {"task": task()}
