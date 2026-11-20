"""Stage 4/5: frozen protocol configuration validation."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from repo_search.benchmark_loader import AGENT_VISIBLE_TASK_FIELDS, method_input_bundle
from repo_search.protocol_config import (
    COUNTED_AGENT_TOOLS,
    EXPECTED_EMBEDDING_MODEL,
    REQUIRED_STOPPING_REASONS,
    assert_valid_protocol,
    load_experiment_config,
    validate_protocol_config,
)

ROOT = Path(__file__).resolve().parents[2]


def test_experiment_yaml_parses_and_validates() -> None:
    cfg = load_experiment_config()
    errors = validate_protocol_config(cfg)
    assert errors == [], errors
    assert_valid_protocol(cfg)


def test_positive_budgets_and_shared_controls() -> None:
    cfg = load_experiment_config()
    assert cfg["budgets"]["evidence_token_budget"] == 6000
    assert cfg["budgets"]["agent_tool_call_limit"] == 5
    assert cfg["retrieval"]["top_k"] == 10
    assert cfg["retrieval"]["shared_by_methods"] is True
    assert cfg["execution"]["repetitions"] == 3
    assert cfg["pilot"]["total_pilot_records"] == 12
    assert cfg["execution"]["expected_records"] == 12


def test_method_a_exactly_one_retrieval() -> None:
    a = load_experiment_config()["methods"]["method_a"]
    assert a["max_semantic_search_calls"] == 1
    assert a["allow_llm_query_rewrite"] is False
    assert a["allow_file_inspection_tools"] is False


def test_method_b_five_call_max_and_tools() -> None:
    b = load_experiment_config()["methods"]["method_b"]
    assert b["max_total_repository_tool_calls"] == 5
    assert set(b["counted_tools"]) == COUNTED_AGENT_TOOLS
    assert set(b["stopping_reasons"]) == REQUIRED_STOPPING_REASONS


def test_paired_repetitions_design() -> None:
    cfg = load_experiment_config()
    assert cfg["execution"]["mode"] == "paired_trials"
    assert cfg["execution"]["run_one_shot_even_if_deterministic"] is True
    assert cfg["execution"]["paired_trial_id_template"] == "{task_id}__r{repetition}"
    tasks = cfg["pilot"]["task_ids"]
    reps = cfg["execution"]["repetitions"]
    assert len(tasks) * 2 * reps == 12


def test_evidence_vs_planning_token_separation() -> None:
    budgets = load_experiment_config()["budgets"]
    assert budgets["evidence_accounting"]["separate_planning_tokens"] is True
    tracked = budgets["tracked_token_fields"]
    assert "cumulative_evidence_tokens" in tracked
    assert "agent_planning_input_tokens" in tracked
    assert "final_evidence_pack_tokens" in tracked


def test_design_frozen_and_stage5_technical_pins() -> None:
    cfg = load_experiment_config()
    assert cfg["meta"]["design_frozen"] is True
    assert cfg["meta"]["protocol_version"] == "pilot-v1.0"
    assert cfg["meta"]["technical_configuration_status"] == "configured_stage_5"
    assert cfg["retrieval"]["embedding_model"] == EXPECTED_EMBEDDING_MODEL
    assert cfg["retrieval"]["tokenizer"] == "cl100k_base"
    assert cfg["retrieval"]["top_k"] == 10
    assert cfg["chunking"]["max_chunk_tokens"] == 800
    assert cfg["chunking"]["overlap_tokens"] == 100
    assert cfg["models"]["agent_llm"]["status"] == "configured_stage_6"
    assert cfg["models"]["agent_llm"]["model"] == "openai/gpt-6-luna"
    assert cfg["models"]["agent_llm"]["max_output_tokens"] == 4096
    assert cfg["models"]["agent_dry_run_is_plumbing_only"] is True
    assert cfg["methods"]["method_a"]["status"] == "implemented_stage_6"
    assert cfg["methods"]["method_b"]["status"] == "implemented_stage_6"


def test_protocol_freeze_doc_exists() -> None:
    path = ROOT / "docs" / "protocol_freeze.md"
    text = path.read_text(encoding="utf-8")
    assert "pilot-v1.0" in text
    assert "file-level **F1**" in text or "File-level **F1**" in text or "file-level F1" in text.lower()


def test_ground_truth_remains_evaluator_only() -> None:
    cfg = load_experiment_config()
    assert cfg["evaluation"]["ground_truth_access"] == "evaluator_only"
    for task_id in cfg["pilot"]["task_ids"]:
        payload = method_input_bundle(task_id)
        assert set(payload["task"].keys()) == AGENT_VISIBLE_TASK_FIELDS
        assert "ground_truth" not in payload
        assert "required_files" not in json.dumps(payload)


def test_invalid_config_detected() -> None:
    cfg = load_experiment_config()
    bad = yaml.safe_load(yaml.dump(cfg))
    bad["methods"]["method_a"]["max_semantic_search_calls"] = 3
    bad["budgets"]["agent_tool_call_limit"] = 0
    errors = validate_protocol_config(bad)
    assert any("exactly one" in e for e in errors)
    assert any("positive" in e or "must be 5" in e for e in errors)
