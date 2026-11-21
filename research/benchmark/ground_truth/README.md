# Ground Truth (Evaluator-Only)

## Purpose

Ground-truth annotations exist **only for evaluation**. They must **never** be passed to Method A (one-shot code RAG) or Method B (agent-directed code search) as input.

They answer: *which repository locations would a careful human judge consider relevant evidence for this task?* Retrieval quality is scored by comparing each method’s evidence pack against these annotations.

## Status

**Stage 3:** Pilot annotations exist as `preliminary_self_validated`:

- `pi_lazy_extension_loading.json`
- `pi_package_filtering.json`

Machine-readable contract: `schemas/ground_truth.schema.json`. Non-pilot candidates are not fully annotated yet. Candidate E remains snapshot-unresolved.

**Independent path (required):** EXP authors preliminary prompts and ground truth from historical diffs, verifies every annotation against the **parent** snapshot, and labels files `preliminary` / `self_validated`. EXP also defines schemas, loads artifacts, and scores methods.

**Optional enhancement:** Teammate 2 may later review/replace annotations. Integrate only after schema checks; do not invent teammate validation or claim unreceived review.

## Future annotation structure

Each task will eventually have a JSON (or YAML) annotation file, e.g. `ground_truth/<task_id>.json`, containing:

| Field | Meaning |
|---|---|
| `task_id` | Stable task identifier matching `tasks.json` / `candidates.json`. |
| `snapshot_id` | Link to a verified pre-change snapshot in `manifests/snapshots.json` (Stage 2+). |
| `required_files` | Files that must appear for the evidence pack to be considered adequate. |
| `relevance` | Per-file or per-span labels: `essential` vs `supporting`. |
| `relevant_symbols` | Functions, classes, constants, or other symbols judged relevant. |
| `relevant_line_spans` | Inclusive line ranges within files (snapshot-relative). |
| `annotation_notes` | Free-text rationale, ambiguity notes, and edge cases. |
| `existing_tests` | Tests already present on the **pre-change** snapshot that exercise related behaviour. |
| `target_added_tests` | Tests introduced by the **target** change (evaluator metadata only; not shown to methods). |

### Illustrative skeleton (not real gold data)

```json
{
  "task_id": "example_task_id",
  "snapshot_id": null,
  "validation_status": "unverified",
  "required_files": [],
  "relevance": {
    "essential": [],
    "supporting": []
  },
  "relevant_symbols": [],
  "relevant_line_spans": [],
  "annotation_notes": "",
  "existing_tests": [],
  "target_added_tests": []
}
```

## Integrity rules

1. Do not fabricate annotations to “complete” Stage 1.
2. Do not leak ground truth into task prompts, retrieval queries, or method inputs.
3. Label any fallback or preliminary annotations honestly (`preliminary`, `unverified`, or similar).
4. Prefer multi-file, multi-span relevance (RepoBench-inspired) over single-file shortcuts.
5. Keep annotation files out of method runtime paths; evaluation scripts load them separately.

## Planned ownership

| Activity | Owner |
|---|---|
| Snapshot verification (Git) + preliminary prompts/GT | EXP (required independent path) |
| Schema definition + loader / scoring (core P/R/F1, essential-file recall) | EXP |
| Optional reviewed gold / leakage audit | Teammate 2 (enhancement) |
| Optional MRR/nDCG/viz | Teammate 3 (enhancement) |

## T2 versioned proposal

The two top-level JSON files remain the independent frozen-pilot baseline. `t2_context_v1/*.json` contains eight proposed T2 annotations following the same schema, with additional parent-file/span hashes and explicit pending human-review status. Select it only in the offline evaluator with `load_ground_truth(task_id, annotation_set="t2_context_v1")`. Matching neutral prompts are in `benchmark/task_sets/t2_context_v1.json`; do not silently mix these revised requests and labels into pilot-v1.0. All gold and review files are evaluator-only. See `docs/t2_integration.md` from the research root.
