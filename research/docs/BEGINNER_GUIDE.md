# Beginner Guide: Repository-Level Context for Coding Agents

This guide assumes **no prior knowledge** of RAG or repository-level search. It uses the Pi project as a concrete example.

---

## What is this experiment testing?

We ask one fixed question:

> Does agent-directed code search outperform one-shot code RAG for repository-level software engineering tasks?

In plain language: when an AI coding agent needs to understand a large codebase to work on a task, **is it better to (A) retrieve relevant code once with a standard search index, or (B) let the agent search, read, notice gaps, and search again?**

We score **how good the retrieved code context is**, not whether the agent successfully rewrites Pi.

---

## Why repository-level context matters

Pi is a **monorepo**: many packages and modules live in one Git repository. A task such as “understand lazy extension loading” rarely lives in a single file. Useful clues might sit in:

- an extension loader module,
- configuration that lists extensions,
- call sites that trigger loading,
- tests that describe expected behaviour.

If the agent only sees one file, it may miss the real story. **Repository-level context** means gathering the right pieces across the tree.

---

## What is a repository snapshot?

A **snapshot** is a frozen copy of the codebase at one specific Git commit.

For each task we intend to use the **pre-change** snapshot: the parent state *before* a known fix or feature landed. That way the search methods look for context the way a developer would *before* the solution existed in the tree.

Example (illustrative only — SHAs are **not verified** in Stage 1):

- Task: lazy extension loading  
- We would check out Pi at the parent of the change, not at the commit that already contains the finished solution.

---

## What is a corpus?

The **corpus** is the collection of source files (from that snapshot) that we allow the search system to index and retrieve from. Here the intended corpus is the **full Pi monorepo** at the task’s pre-change snapshot.

Think of it as: “everything the search methods are allowed to look through.”

---

## What is a code chunk?

Search indexes usually do not store each whole file as one blob. They split files into **chunks** — smaller pieces (for example a function, or a fixed-size window of lines) that can be embedded and ranked.

A good chunk is big enough to be meaningful and small enough to fit in an evidence budget. Exact chunking settings are **placeholders** in Stage 1.

---

## What is a retriever? What is RAG?

A **retriever** takes a query (derived from the task) and returns the most similar or relevant chunks from the index.

**RAG** means Retrieval-Augmented Generation: retrieve relevant text first, then (often) give it to an LLM. In this project we care mainly about the **retrieval** step and the quality of the **evidence pack** (the ranked context that would be shown to an agent).

**Repository-level RAG** means the index covers a whole repository snapshot, not a single file or a tiny tutorial snippet.

---

## What is ground truth?

**Ground truth** is the carefully labelled answer key for *what context should have been found* — for example required files, essential vs supporting sections, important symbols, and line ranges.

It is **evaluator-only**. Methods A and B must not see it. We use it after the fact to score their evidence packs.

No real gold labels are invented in Stage 1.

---

## Method A — One-shot code RAG

1. Receive the same task prompt (e.g. investigate package filtering in Pi).  
2. Build one query.  
3. Run **exactly one** retrieval against the shared index.  
4. Return a ranked evidence pack within the token budget (preliminary: 6,000 tokens).

No second chance. No “I should also open that config file” loop.

---

## Method B — Agent-directed code search

1. Receive the **same** task prompt.  
2. Search the repository (via the shared retrieval tools / index).  
3. Inspect retrieved files or symbols.  
4. Notice missing context (“I see registration, but not where loading is deferred”).  
5. Refine the query and search again.  
6. Stop when the tool-call limit or evidence budget is hit (preliminary: 5 tool calls; 6,000 evidence tokens).  
7. Return a ranked evidence pack.

Inspired by iterative retrieval ideas (e.g. RepoCoder), but **not** a full copy of that system. We still score **retrieval quality**, not completion success.

---

## How will results be compared?

For each pilot task (initially lazy extension loading and package filtering):

1. Run Method A and Method B on the **same** snapshot, **same** Teammate 1 index/retriever, prompt, and budgets.  
2. Repeat a few times (preliminary: 3) for stability.  
3. Score each **final evidence pack** against Teammate 2 ground truth (EXP: file precision/recall/F1, essential-file recall; T3 may add MRR/nDCG later using the **same** labels).  
4. Record cost separately: evidence tokens, planning tokens, tool calls, latency.  
5. Ask: did Method B find more *useful* context, or mostly extra noise / diminishing returns?

Who builds what (short version): Teammate 1 builds the search engine; Teammate 2 validates snapshots and labels relevant files; this workstream runs both methods and the core scores; Teammate 3 deepens charts/synthesis for the presentation. Details: `docs/ownership_matrix.md`.

---

## What exists today (Stage 1.5)?

| Ready | Not ready yet |
|---|---|
| Project docs, ownership matrix, integration schemas | Pi clone / verified snapshots (Stage 2) |
| Candidate and provisional pilot task metadata | Working Teammate 1 retriever / EXP agent |
| Provisional experiment config | Teammate 2 gold annotations |
| Documented handoff contracts | Real experimental results / T3 charts |

If a command or module is labelled **planned**, it is not executable yet.
