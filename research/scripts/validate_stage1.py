"""Stage 1 lightweight validation — structure already checked by caller."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        import yaml
    except ImportError:
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml", "-q"])
        import yaml

    errors: list[str] = []
    print("=== PARSE YAML + JSON ===")

    exp = None
    try:
        with (ROOT / "config" / "experiment.yaml").open(encoding="utf-8") as f:
            exp = yaml.safe_load(f)
        print("YAML: OK")
    except Exception as e:  # noqa: BLE001
        errors.append(f"YAML parse: {e}")
        print(f"YAML: FAIL {e}")

    json_paths = [
        "benchmark/tasks.json",
        "benchmark/candidates.json",
        "benchmark/manifests/snapshots.json",
    ]
    data: dict[str, object] = {}
    for rel in json_paths:
        try:
            with (ROOT / rel).open(encoding="utf-8") as f:
                data[rel] = json.load(f)
            print(f"JSON OK: {rel}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{rel}: {e}")
            print(f"JSON FAIL: {rel}: {e}")

    print("\n=== DOC REFERENCES EXIST ===")
    docs = [
        "docs/BEGINNER_GUIDE.md",
        "docs/EXECUTION_CHECKLIST.md",
        "docs/methodology.md",
        "docs/literature_review.md",
        "docs/task_cards.md",
        "docs/handoff_contract.md",
        "docs/limitations.md",
        "docs/report_plan.md",
        "docs/ai_use_log.md",
        "docs/contribution_log.md",
        "docs/appendix_templates.md",
    ]
    for d in docs:
        ok = (ROOT / d).is_file()
        label = "OK" if ok else "MISSING"
        print(f"{label}: {d}")
        if not ok:
            errors.append(f"missing doc {d}")

    print("\n=== CANDIDATE / TASK CONSISTENCY ===")
    cand = data.get("benchmark/candidates.json") or {}
    tasks = data.get("benchmark/tasks.json") or {}
    snaps = data.get("benchmark/manifests/snapshots.json") or {}

    primary = cand.get("primary_candidates", [])
    reserve = cand.get("advanced_reserve", [])
    print(f"Primary candidates: {len(primary)} (expected 8)")
    print(f"Advanced reserve: {len(reserve)} (expected 1)")
    if len(primary) != 8:
        errors.append(f"expected 8 primary, got {len(primary)}")
    if len(reserve) != 1:
        errors.append(f"expected 1 reserve, got {len(reserve)}")

    for item in primary + reserve:
        vs = item.get("validation_status")
        tid = item.get("task_id")
        st = item.get("status")
        if vs != "unverified":
            errors.append(f"{tid} validation_status={vs} (must be unverified)")
            print(f"FAIL: {tid} validation_status={vs}")
        else:
            print(f"OK unverified: {tid} status={st}")

    expected_pilots = {"pi_lazy_extension_loading", "pi_package_filtering"}
    pilots = {c["task_id"] for c in primary if c.get("status") == "pilot"}
    print(f"Pilot candidates: {sorted(pilots)}")
    if pilots != expected_pilots:
        errors.append(f"pilot mismatch: {pilots}")

    task_ids = {t["task_id"] for t in tasks.get("tasks", [])}
    print(f"Task entries: {sorted(task_ids)}")
    if task_ids != expected_pilots:
        errors.append(f"tasks.json ids mismatch: {task_ids}")

    for t in tasks.get("tasks", []):
        if t.get("validation_status") != "unverified":
            errors.append(f"task {t['task_id']} not unverified")
        desc = t.get("description", "")
        for c in primary:
            if c["task_id"] != t["task_id"]:
                continue
            for key in ("target_commit", "known_parent_prefix"):
                val = c.get(key)
                if val and val in desc:
                    errors.append(f"leak: {key}={val} in task description")
                    print(f"FAIL leak: {val} in description")

    c = next(x for x in primary if x["letter_id"] == "C")
    d = next(x for x in primary if x["letter_id"] == "D")
    if "overlap_flag" not in c or "overlap_flag" not in d:
        errors.append("C/D missing overlap_flag")
        print("FAIL: C/D overlap_flag missing")
    else:
        print("OK: C/D overlap flags present")

    r = reserve[0]
    if r.get("target_commit") != "32bcdc9":
        errors.append("reserve target != 32bcdc9")
    if r.get("status") != "advanced_reserve":
        errors.append("reserve status wrong")
    if any(x.get("target_commit") == "32bcdc9" for x in primary):
        errors.append("32bcdc9 incorrectly in primary")
    print(f"OK reserve: {r.get('task_id')} status={r.get('status')}")

    snap_list = snaps.get("snapshots", [])
    print(f"Snapshots status: {snaps.get('status')}, count={len(snap_list)}")
    if snap_list:
        errors.append("snapshots should be empty in Stage 1")
        print("FAIL: snapshots not empty")
    else:
        print("OK: snapshots empty/provisional")

    # No entry marked verified
    verified_hits = []
    for item in primary + reserve:
        if str(item.get("validation_status", "")).lower() in {"verified", "frozen", "validated"}:
            verified_hits.append(item.get("task_id"))
    if verified_hits:
        errors.append(f"incorrectly verified: {verified_hits}")
    else:
        print("OK: no candidate marked verified/frozen/validated")

    print("\n=== EXPERIMENT.YAML ===")
    if exp:
        rq = " ".join(((exp.get("research") or {}).get("question") or "").split())
        expected_q = (
            "Does agent-directed code search outperform one-shot code RAG for "
            "repository-level software engineering tasks?"
        )
        if expected_q not in rq:
            errors.append(f"research question mismatch: {rq!r}")
            print("FAIL: research question")
        else:
            print("OK: research question preserved")
        if exp.get("meta", {}).get("config_frozen") is not False:
            errors.append("config_frozen should be false")
        stage = exp.get("meta", {}).get("stage")
        if stage not in (1, "1", "1.5"):
            errors.append("meta.stage should be 1 or 1.5")
        budgets = exp.get("budgets", {})
        if budgets.get("evidence_token_budget") != 6000:
            errors.append("evidence budget")
        if budgets.get("agent_tool_call_limit") != 5:
            errors.append("tool call limit")
        if exp.get("execution", {}).get("repetitions") != 3:
            errors.append("repetitions")
        if exp.get("execution", {}).get("temperature") != 0:
            errors.append("temperature")
        pilot_cfg = set((exp.get("pilot") or {}).get("task_ids") or [])
        if pilot_cfg != expected_pilots:
            errors.append(f"experiment pilot ids {pilot_cfg}")
        for method_key in ("method_a", "method_b"):
            st = ((exp.get("methods") or {}).get(method_key) or {}).get("status")
            if st != "planned":
                errors.append(f"{method_key} status should be planned, got {st}")
        print(
            "OK budgets: "
            f"tokens={budgets.get('evidence_token_budget')} "
            f"tools={budgets.get('agent_tool_call_limit')} "
            f"reps={exp.get('execution', {}).get('repetitions')} "
            f"temp={exp.get('execution', {}).get('temperature')}"
        )
        print(
            f"OK config_frozen={exp.get('meta', {}).get('config_frozen')} "
            f"stage={exp.get('meta', {}).get('stage')}"
        )

    print("\n=== NO FALSE COMPLETION CLAIMS ===")
    checklist = (ROOT / "docs" / "EXECUTION_CHECKLIST.md").read_text(encoding="utf-8")
    if "Current stage: Stage 1" not in checklist:
        errors.append("checklist missing current stage 1")
        print("FAIL: current stage not 1")
    else:
        print("OK: checklist current stage is 1")
    if "Not started" in checklist:
        print("OK: future stages include Not started")
    else:
        errors.append("checklist missing Not started markers")

    findings = (ROOT / "results" / "findings.md").read_text(encoding="utf-8").lower()
    if "no experiments have been run" in findings or "empty placeholder" in findings:
        print("OK: findings placeholder honest")
    else:
        errors.append("findings.md missing honest placeholder language")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "Not yet available" not in readme and "not implemented" not in readme.lower():
        errors.append("README missing honest status language")
    else:
        print("OK: README has honest status language")

    print("\n=== SUMMARY ===")
    if errors:
        print(f"VALIDATION FAIL ({len(errors)} issues):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("VALIDATION PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
