"""Stage 1.5 validation: ownership alignment, schemas, unchanged research identity."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_Q = (
    "Does agent-directed code search outperform one-shot code RAG for "
    "repository-level software engineering tasks?"
)
EXPECTED_PILOTS = {"pi_lazy_extension_loading", "pi_package_filtering"}
REQUIRED_DOCS = [
    "README.md",
    "docs/BEGINNER_GUIDE.md",
    "docs/EXECUTION_CHECKLIST.md",
    "docs/methodology.md",
    "docs/handoff_contract.md",
    "docs/literature_review.md",
    "docs/ownership_matrix.md",
    "docs/report_plan.md",
    "docs/appendix_templates.md",
]
REQUIRED_SCHEMAS = [
    "schemas/README.md",
    "schemas/retrieved_chunk.schema.json",
    "schemas/index_metadata.schema.json",
    "schemas/snapshots.schema.json",
    "schemas/ground_truth.schema.json",
    "schemas/experiment_run.schema.json",
]
CHUNK_FIELDS = {
    "chunk_id",
    "path",
    "symbol",
    "start_line",
    "end_line",
    "content",
    "token_count",
    "content_hash",
    "score",
}


def main() -> int:
    try:
        import yaml
    except ImportError:
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml", "-q"])
        import yaml

    errors: list[str] = []

    print("=== REQUIRED DOCS / SCHEMAS ===")
    for rel in REQUIRED_DOCS + REQUIRED_SCHEMAS:
        if not (ROOT / rel).is_file():
            errors.append(f"missing {rel}")
            print(f"MISSING: {rel}")
        else:
            print(f"OK: {rel}")

    print("\n=== PARSE CONFIG + BENCHMARK ===")
    try:
        exp = yaml.safe_load((ROOT / "config" / "experiment.yaml").read_text(encoding="utf-8"))
        print("YAML: OK")
    except Exception as e:  # noqa: BLE001
        errors.append(f"YAML: {e}")
        exp = {}
        print(f"YAML FAIL: {e}")

    data = {}
    for rel in (
        "benchmark/tasks.json",
        "benchmark/candidates.json",
        "benchmark/manifests/snapshots.json",
    ):
        try:
            data[rel] = json.loads((ROOT / rel).read_text(encoding="utf-8"))
            print(f"JSON OK: {rel}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{rel}: {e}")
            print(f"JSON FAIL: {rel}: {e}")

    for rel in REQUIRED_SCHEMAS:
        if not rel.endswith(".json"):
            continue
        try:
            json.loads((ROOT / rel).read_text(encoding="utf-8"))
            print(f"SCHEMA OK: {rel}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"schema {rel}: {e}")
            print(f"SCHEMA FAIL: {rel}: {e}")

    print("\n=== RESEARCH IDENTITY ===")
    rq = " ".join(((exp.get("research") or {}).get("question") or "").split())
    if EXPECTED_Q not in rq:
        errors.append("research question changed")
        print("FAIL: research question")
    else:
        print("OK: research question unchanged")
    topic = (exp.get("research") or {}).get("topic")
    if topic != "Repository-Level Context for Coding Agents":
        errors.append(f"topic changed: {topic}")
    else:
        print("OK: topic unchanged")

    print("\n=== CANDIDATES / PILOTS PRESERVED ===")
    cand = data.get("benchmark/candidates.json") or {}
    primary = cand.get("primary_candidates", [])
    reserve = cand.get("advanced_reserve", [])
    if len(primary) != 8:
        errors.append(f"primary count {len(primary)}")
    if len(reserve) != 1 or reserve[0].get("target_commit") != "32bcdc9":
        errors.append("reserve 32bcdc9 missing/wrong")
    for item in primary + reserve:
        if item.get("validation_status") != "unverified":
            errors.append(f"{item.get('task_id')} not unverified")
    pilots = {c["task_id"] for c in primary if c.get("status") == "pilot"}
    task_ids = {t["task_id"] for t in (data.get("benchmark/tasks.json") or {}).get("tasks", [])}
    if pilots != EXPECTED_PILOTS or task_ids != EXPECTED_PILOTS:
        errors.append("pilot/task mismatch")
    else:
        print("OK: eight candidates + two pilots preserved")
    snaps = data.get("benchmark/manifests/snapshots.json") or {}
    if snaps.get("snapshots"):
        errors.append("snapshots not empty")
    else:
        print("OK: snapshots still provisional/empty")

    print("\n=== METRIC / OWNERSHIP ALIGNMENT ===")
    primary_metrics = set((exp.get("evaluation") or {}).get("primary_metrics") or [])
    secondary_metrics = set((exp.get("evaluation") or {}).get("secondary_metrics") or [])
    for need in (
        "file_precision",
        "file_recall",
        "file_f1",
        "essential_file_recall",
        "planning_token_usage",
        "tool_call_count",
        "latency_ms",
    ):
        if need not in primary_metrics:
            errors.append(f"missing primary metric {need}")
    if "mean_reciprocal_rank" in primary_metrics:
        errors.append("MRR incorrectly listed as primary")
    if "mean_reciprocal_rank" not in secondary_metrics or "ndcg" not in secondary_metrics:
        errors.append("MRR/nDCG missing from secondary")
    else:
        print("OK: primary/secondary metric split")
    if (exp.get("retrieval") or {}).get("shared_by_methods") is not True:
        errors.append("retrieval.shared_by_methods must be true")
    if (exp.get("meta") or {}).get("config_frozen") is not False:
        errors.append("config must remain unfrozen")
    if str((exp.get("meta") or {}).get("stage")) not in {"1.5", "1.5.0"}:
        errors.append(f"meta.stage should be 1.5, got {(exp.get('meta') or {}).get('stage')}")
    else:
        print("OK: meta.stage=1.5, config_frozen=false")

    print("\n=== RETRIEVER SCHEMA FIELDS ===")
    chunk_schema = json.loads(
        (ROOT / "schemas" / "retrieved_chunk.schema.json").read_text(encoding="utf-8")
    )
    req = set(chunk_schema.get("required") or [])
    if req != CHUNK_FIELDS:
        errors.append(f"RetrievedChunk required fields mismatch: {req}")
        print(f"FAIL fields: {req}")
    else:
        print("OK: RetrievedChunk required fields")

    run_schema = json.loads(
        (ROOT / "schemas" / "experiment_run.schema.json").read_text(encoding="utf-8")
    )
    run_req = set(run_schema.get("required") or [])
    for field in (
        "paired_trial_id",
        "method",
        "evidence_pack",
        "evidence_tokens",
        "planning_tokens",
        "tool_call_count",
        "latency_ms",
        "stop_reason",
    ):
        if field not in run_req:
            errors.append(f"experiment_run missing required {field}")
    else:
        print("OK: experiment_run required identity/budget fields")

    print("\n=== DOC CONSISTENCY SPOT CHECKS ===")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs" / "EXECUTION_CHECKLIST.md").read_text(encoding="utf-8")
    handoff = (ROOT / "docs" / "handoff_contract.md").read_text(encoding="utf-8")
    methodology = (ROOT / "docs" / "methodology.md").read_text(encoding="utf-8")

    if "Stage 2 is next" not in readme and "Stage 2 is next" not in checklist:
        errors.append("docs do not identify Stage 2 as next")
    else:
        print("OK: Stage 2 identified as next")
    if "Current stage: Stage 1 — Initialize" in checklist and "Complete" not in checklist.split("Stage 1")[1][:800]:
        # Stage 1 should be marked complete in 1.5
        pass
    if "**Complete**" not in checklist or "1.5" not in checklist:
        errors.append("checklist missing Stage 1.5 complete markers")
    else:
        print("OK: checklist includes Stage 1.5")
    if "search(query: str, top_k: int, max_tokens: int)" not in handoff:
        errors.append("handoff missing retriever protocol signature")
    else:
        print("OK: retriever protocol in handoff")
    if "assume agent-directed search is inherently superior" not in methodology:
        errors.append("methodology missing principle 9 language")
    else:
        print("OK: methodology principles present")
    # Ensure we did not mark methods implemented
    if (exp.get("methods") or {}).get("method_a", {}).get("status") != "planned":
        errors.append("method_a not planned")
    if (exp.get("methods") or {}).get("method_b", {}).get("status") != "planned":
        errors.append("method_b not planned")
    # No fake teammate modules
    for bad in (
        "src/repo_search/retriever.py",
        "src/repo_search/embeddings.py",
        "src/repo_search/agent.py",
        "src/repo_search/oneshot.py",
    ):
        if (ROOT / bad).exists():
            errors.append(f"unexpected implementation file {bad}")
    else:
        print("OK: no premature method/retriever implementation modules")

    # Appendix / report plan preserved
    appendix = (ROOT / "docs" / "appendix_templates.md").read_text(encoding="utf-8")
    if "Appendix A" not in appendix or "Appendix D" not in appendix:
        errors.append("appendix templates damaged")
    report = (ROOT / "docs" / "report_plan.md").read_text(encoding="utf-8")
    if "1,500" not in report and "1500" not in report:
        errors.append("report plan word count missing")
    else:
        print("OK: report plan and appendices preserved")

    print("\n=== SUMMARY ===")
    if errors:
        print(f"VALIDATION FAIL ({len(errors)} issues):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("STAGE 1.5 VALIDATION PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
