# Integration Schemas

JSON Schema drafts for teammate handoffs. **Contracts only** — no runtime loaders or teammate implementations are provided here.

| Schema | Workstream | Purpose |
|---|---|---|
| `retrieved_chunk.schema.json` | T1 → EXP | Retriever hit shape |
| `index_metadata.schema.json` | T1 → EXP | Index/backend provenance |
| `snapshots.schema.json` | T2 → EXP | Verified snapshot manifest entries |
| `ground_truth.schema.json` | T2 → EXP | Evaluator-only annotations |
| `experiment_run.schema.json` | EXP → T3 | Raw trial records (JSONL lines) |

Authoritative narrative: `docs/handoff_contract.md`.  
Ownership matrix: `docs/ownership_matrix.md`.

All teammate-produced instance data remains **pending** until delivered.

## T2 benchmark contracts

`tasks.schema.json` defines the central four-field method task. The existing GT and
snapshot schemas accept the T2 provenance fields and constrain complete source
identifiers. Offline checks validate source existence, hashes and span consistency.
