"""Load and validate the Stage 4/5 pilot protocol configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REQUIRED_STOPPING_REASONS = frozenset(
    {
        "evidence_sufficient",
        "no_new_relevant_evidence",
        "call_limit_reached",
        "evidence_budget_exhausted",
        "tool_or_model_error",
    }
)

COUNTED_AGENT_TOOLS = frozenset(
    {"semantic_search", "read_file", "find_symbol", "grep"}
)

EXPECTED_EMBEDDING_MODEL = "openai/text-embedding-3-small"
EXPECTED_TOKENIZER = "cl100k_base"
EXPECTED_CHUNKER_VERSION = "pilot-v1.0-chunker-1"


def research_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_experiment_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or (research_root() / "config" / "experiment.yaml")
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("experiment.yaml must parse to a mapping")
    return data


def validate_protocol_config(cfg: dict[str, Any]) -> list[str]:
    """Return a list of validation errors (empty if valid)."""
    errors: list[str] = []

    meta = cfg.get("meta") or {}
    if meta.get("protocol_version") != "pilot-v1.0":
        errors.append("meta.protocol_version must be pilot-v1.0")
    if meta.get("design_frozen") is not True:
        errors.append("meta.design_frozen must be true")
    tech = meta.get("technical_configuration_status")
    if tech not in {"pending_stage_5", "configured_stage_5"}:
        errors.append(
            "technical_configuration_status must be pending_stage_5 or configured_stage_5"
        )

    research = cfg.get("research") or {}
    q = " ".join(str(research.get("question", "")).split())
    if "agent-directed code search outperform one-shot code RAG" not in q:
        errors.append("research question altered")
    if research.get("primary_metric") != "file_f1":
        errors.append("primary_metric must be file_f1")
    if research.get("primary_outcome_object") != "final_evidence_pack":
        errors.append("primary_outcome_object must be final_evidence_pack")

    pilot = cfg.get("pilot") or {}
    task_ids = list(pilot.get("task_ids") or [])
    if len(task_ids) != 2:
        errors.append("pilot must list exactly 2 tasks")
    if set(task_ids) != {
        "pi_lazy_extension_loading",
        "pi_package_filtering",
    }:
        errors.append("unexpected pilot task_ids")
    if pilot.get("total_pilot_records") != 12:
        errors.append("total_pilot_records must be 12")

    budgets = cfg.get("budgets") or {}
    if budgets.get("evidence_token_budget") != 6000:
        errors.append("evidence_token_budget must be 6000")
    if budgets.get("evidence_token_budget", 0) <= 0:
        errors.append("evidence_token_budget must be positive")
    if budgets.get("agent_tool_call_limit") != 5:
        errors.append("agent_tool_call_limit must be 5")
    if budgets.get("agent_tool_call_limit", 0) <= 0:
        errors.append("agent_tool_call_limit must be positive")
    accounting = budgets.get("evidence_accounting") or {}
    if accounting.get("separate_planning_tokens") is not True:
        errors.append("planning tokens must be separated from evidence")
    if accounting.get("count_repeated_excerpts") is not True:
        errors.append("repeated excerpts must count toward evidence budget")

    tracked = set(budgets.get("tracked_token_fields") or [])
    for field in (
        "cumulative_evidence_tokens",
        "unique_evidence_tokens",
        "final_evidence_pack_tokens",
        "agent_planning_input_tokens",
        "agent_output_tokens",
    ):
        if field not in tracked:
            errors.append(f"missing tracked token field: {field}")

    execution = cfg.get("execution") or {}
    if execution.get("mode") != "paired_trials":
        errors.append("execution.mode must be paired_trials")
    if execution.get("repetitions") != 3:
        errors.append("repetitions must be 3")
    if execution.get("temperature") != 0:
        errors.append("temperature must be 0")
    if execution.get("expected_records") != 12:
        errors.append("expected_records must be 12")
    if execution.get("run_one_shot_even_if_deterministic") is not True:
        errors.append("one-shot must run in every paired trial")

    retrieval = cfg.get("retrieval") or {}
    if retrieval.get("top_k") != 10:
        errors.append("retrieval.top_k must be 10")
    if retrieval.get("shared_by_methods") is not True:
        errors.append("retrieval backend must be shared by methods")
    if retrieval.get("initial_query_policy") != "exact_task_prompt":
        errors.append("initial_query_policy must be exact_task_prompt")

    if tech == "pending_stage_5":
        for pending_key in (
            "embedding_model",
            "embedding_model_revision",
            "tokenizer",
            "index_build_id",
        ):
            if retrieval.get(pending_key) != "pending_configuration":
                errors.append(f"retrieval.{pending_key} must remain pending_configuration")
    else:
        if retrieval.get("embedding_model") != EXPECTED_EMBEDDING_MODEL:
            errors.append(
                f"retrieval.embedding_model must be {EXPECTED_EMBEDDING_MODEL}"
            )
        if retrieval.get("tokenizer") != EXPECTED_TOKENIZER:
            errors.append(f"retrieval.tokenizer must be {EXPECTED_TOKENIZER}")
        if retrieval.get("backend") != "local_numpy_cosine":
            errors.append("retrieval.backend must be local_numpy_cosine")
        if retrieval.get("max_tokens_per_search") != 6000:
            errors.append("retrieval.max_tokens_per_search must be 6000")
        chunking = cfg.get("chunking") or {}
        if chunking.get("max_chunk_tokens") != 800:
            errors.append("chunking.max_chunk_tokens must be 800")
        if chunking.get("overlap_tokens") != 100:
            errors.append("chunking.overlap_tokens must be 100")
        if chunking.get("tokenizer") != EXPECTED_TOKENIZER:
            errors.append("chunking.tokenizer must be cl100k_base")
        if chunking.get("strategy") != "symbol_aware_with_line_fallback":
            errors.append("chunking.strategy mismatch")
        if chunking.get("version") != EXPECTED_CHUNKER_VERSION:
            errors.append("chunking.version mismatch")
        emb = (cfg.get("models") or {}).get("embedding") or {}
        if emb.get("identifier") != EXPECTED_EMBEDDING_MODEL:
            errors.append("models.embedding.identifier mismatch")
        agent = (cfg.get("models") or {}).get("agent_llm") or {}
        agent_status = agent.get("status")
        if agent_status not in {
            "reserved_stage_6_not_used_in_stage_5",
            "configured_stage_6",
        }:
            errors.append("models.agent_llm.status invalid for current stage")
        if agent_status == "configured_stage_6":
            if agent.get("model") != "openai/gpt-6-luna":
                errors.append("primary agent model must be openai/gpt-6-luna")
            if agent.get("temperature") != 0:
                errors.append("agent temperature must remain 0")
            if not agent.get("max_output_tokens"):
                errors.append("max_output_tokens must be set for Stage 6")
            if not agent.get("system_prompt_version"):
                errors.append("system_prompt_version must be set for Stage 6")
        secondary = (cfg.get("models") or {}).get("secondary_llm") or {}
        if secondary.get("model") == "openrouter/free":
            if "not" not in str(secondary.get("notes", "")).lower() and secondary.get(
                "status"
            ) not in {
                "reserved_stage_6_not_used_in_stage_5",
                "exploratory_only_not_primary",
            }:
                errors.append("openrouter/free must remain non-primary")


    method_a = (cfg.get("methods") or {}).get("method_a") or {}
    method_b = (cfg.get("methods") or {}).get("method_b") or {}
    if method_a.get("max_semantic_search_calls") != 1:
        errors.append("Method A must allow exactly one semantic search")
    if method_a.get("allow_llm_query_rewrite") is not False:
        errors.append("Method A must not LLM-rewrite queries")
    if method_b.get("max_total_repository_tool_calls") != 5:
        errors.append("Method B must allow at most 5 tool calls")
    tools = set(method_b.get("counted_tools") or [])
    if tools != COUNTED_AGENT_TOOLS:
        errors.append(f"Method B counted_tools mismatch: {tools}")
    reasons = set(method_b.get("stopping_reasons") or [])
    if reasons != REQUIRED_STOPPING_REASONS:
        errors.append(f"stopping_reasons mismatch: {reasons}")

    evaluation = cfg.get("evaluation") or {}
    if evaluation.get("primary_metric") != "file_f1":
        errors.append("evaluation.primary_metric must be file_f1")
    if evaluation.get("ground_truth_access") != "evaluator_only":
        errors.append("ground truth must remain evaluator_only")
    if evaluation.get("same_annotations_for_both_methods") is not True:
        errors.append("both methods must share annotations")
    if evaluation.get("primary_outcome_object") != "final_evidence_pack":
        errors.append("primary outcome object must be final evidence pack")
    if evaluation.get("secondary_outcome_object") != "cumulative_unique_evidence_exposure":
        errors.append("secondary outcome object must be cumulative unique exposure")

    if (cfg.get("budgets") or {}).get("evidence_token_budget") != 6000:
        errors.append("shared evidence budget inconsistency")

    return errors


def assert_valid_protocol(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    data = cfg if cfg is not None else load_experiment_config()
    errors = validate_protocol_config(data)
    if errors:
        raise ValueError("protocol config invalid:\n- " + "\n- ".join(errors))
    return data
