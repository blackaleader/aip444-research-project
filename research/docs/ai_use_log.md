# AI Use Log

**Purpose:** Record actual AI-assisted work for Appendix A and research integrity.  
**Rule:** Do not invent interactions. Add rows only when work happens.

| Date | Tool / model | Stage | Task summary | Human oversight | Output used? | Notes |
|---|---|---|---|---|---|---|
| 2026-11-18 | Cursor agent (Composer) | 1 | Initialise `./research` scaffolding, configs, and documentation | Author reviews all generated files before relying on them | Pending review | Stage 1 foundation only; no experiments run |
| 2026-11-18 | Cursor agent (Composer) | 1.5 | Align ownership, integration contracts, schemas, metric split | Author reviews edits before relying on them | Pending review | Docs/schemas only; no Stage 2 implementation |
| 2026-11-18 | Cursor agent (Composer) | 2 | Clone/verify Pi snapshots, pilot worktrees, verify_benchmark.py | Author reviews SHAs, docs, and script output | Pending review | Candidate E unresolved; no corpus/RAG built |
| 2026-11-18 | Cursor agent (Composer) | docs | Independent-execution rule across checklist/handoff/README/methodology | Author reviews before relying | Pending review | Docs only; no Stage 3 implementation |
| 2026-11-18 | Cursor agent (Composer) | 3 | Construct pilot tasks/GT from diffs; loader + tests | Author verifies annotations vs parent worktrees | Pending review | preliminary_self_validated only; no RAG |
| 2026-11-18 | Cursor agent (Composer) | 4 | Freeze pilot-v1.0 protocol; config + tests | Author reviews freeze vs Stage 3 artifacts | Pending review | Design freeze only; no trials |
| 2026-11-19 | Cursor agent (Composer) | 5 | Corpus, OpenRouter embeddings, NumPy index, shared retriever | Author reviews code/docs; set API key for live probe | Pending review | Live API pending without key; no Method A/B |
| 2026-11-19 | Cursor agent (Composer) | 6 | Method A/B, chat client, orchestration, tests | Author reviews before pilot runs | Pending review | No 12-record pilot batch executed |

---

## Guidance

- Log planning, coding, editing, and literature-summary assistance separately when material.  
- Note when AI drafts were rejected or heavily rewritten.  
- Never paste API keys or secrets into prompts or this log.  
- Link to files touched when helpful (`research/...`).

## T2 local integration — 20 November 2026

| Tool | Actual assistance | Verification | Human review |
| --- | --- | --- | --- |
| ChatGPT / Codex, GitHub connector and local Git | Read the central README, handoff, benchmark files and interfaces; selectively adapt the existing Ni handoff | Original candidate identities checked against GitHub and Git objects | Student review pending |
| ChatGPT / Codex | Implement T2 benchmark validation, input isolation, deterministic generation, worktree reproduction, tests and documentation | Command exits and saved results recorded in the T2 validation record | Student and independent peer relevance sign-off pending |
| ChatGPT / Codex with primary-source reading | Verify CodeRAG-Bench bibliographic data and annotation/evaluation connection | ACL Anthology record and relevant PDF sections checked | Student critical reading remains personal work |

No model identifier beyond ChatGPT/Codex was recorded. No retrieval implementation,
agent controller, behavior-analysis utility, experimental result, personal reflection
or human review was fabricated. No GitHub push is performed in this delivery.
