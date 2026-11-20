# Methods and Experiment Infrastructure (Stage 6)

**Protocol:** `pilot-v1.0` (design unchanged)  
**Scope:** Method A, Method B, shared orchestration, traces, OpenRouter chat client  
**Not in scope:** The 12 pilot trial records (Stage 7+)

---

## Components

| Module | Role |
|---|---|
| `src/repo_search/method_a.py` | One-shot RAG: exact prompt → one `search` → evidence pack |
| `src/repo_search/method_b.py` | Agent loop: initial search + OpenRouter tools ≤ 5 calls |
| `src/repo_search/repo_tools.py` | `semantic_search`, `read_file`, `find_symbol`, `grep` |
| `src/repo_search/chat_client.py` | OpenRouter `/chat/completions` (no silent model swap) |
| `src/repo_search/evidence.py` | Normalized evidence items + ledger |
| `src/repo_search/orchestrator.py` | Load task/snapshot/index → run method → trace |
| `src/repo_search/traces.py` | JSON/JSONL persistence with secret scrubbing |
| `src/repo_search/agent_prompts.py` | System prompt `pilot-v1.0-agent-system-1` |

Scripts: `scripts/run_method_a.py`, `scripts/run_method_b.py`, `scripts/probe_openrouter_chat.py`

---

## Frozen controls (unchanged)

Evidence budget 6000 (`cl100k_base`), top-k 10, Method B ≤ 5 tool calls (initial semantic search counts), temperature 0, shared Stage 5 retriever/indexes.

Planning/completion tokens are recorded separately from repository evidence tokens.

---

## Provisional technical settings (Stage 6)

| Setting | Value |
|---|---|
| Primary chat model | `openai/gpt-6-luna` |
| Max completion tokens | **4096** (not the evidence budget) |
| System prompt version | `pilot-v1.0-agent-system-1` |
| Secondary model | `openrouter/free` (exploratory only; never auto-replace) |

---

## Evidence pack fields

`evidence_id`, `path`, `symbol`, `start_line`, `end_line`, `text`, `token_count`, `source_tool`, optional `chunk_id` / `score` / `content_hash`, `rank`.

---

## Independent execution commands

```powershell
cd "C:\Users\froze\Desktop\AIP Research Project\research"
pip install -e ".[dev]"

# Neutral chat probe (not a pilot task)
python scripts/probe_openrouter_chat.py

# Single plumbing runs (not the 12-record Stage 7 batch)
python scripts/run_method_a.py --task-id pi_lazy_extension_loading --repetition 1
python scripts/run_method_b.py --task-id pi_lazy_extension_loading --repetition 1

python -m pytest tests/unit -q
```

Traces (when persisted): `results/raw/traces/`
