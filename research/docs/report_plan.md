# Group Report Plan

**Do not generate the final paper or fabricate findings in Stage 1.** This plan only reserves structure, word budgets, and source expectations.

---

## Formal requirements

| Requirement | Target |
|---|---|
| Length | Approximately **1,500 words** excluding references and appendices |
| Style | **APA** academic format |
| Sources | **Minimum five** credible sources |
| Appendices | Use templates in `docs/appendix_templates.md` (fill with real activity later) |

### Suggested section budgets

| Section | Approx. words |
|---|---|
| Introduction | 250 |
| Background / literature review | 350 |
| Main content (method + planned/actual experiment) | 550 |
| Critical analysis | 200 |
| Conclusion | 150 |
| **Total body** | **~1,500** |

---

## Section outlines (content placeholders)

### Introduction (~250)

- Repository-level software engineering and coding agents  
- Why context retrieval matters in monorepos (Pi as motivating setting)  
- Fixed research question  
- Contribution: controlled comparison of one-shot RAG vs agent-directed search on **retrieval quality**

### Background / literature (~350)

- RepoBench — retrieval vs completion; multi-file relevance  
- RepoCoder — iterative retrieval (inspiration, not reproduction)  
- Repoformer — selective retrieval; irrelevant context; cost  
- Gap: issue/task-based retrieval comparison under shared controls  
- Cite originals; no invented metrics  

### Main content (~550)

- Operational definitions and independent variable  
- Shared controls and budgets  
- Methods A and B  
- Pi candidates / pilots (honest verification status)  
- Metrics: EXP primary (file P/R/F1, essential-file recall, tokens/tools/latency); T3 secondary (MRR/nDCG/viz) on the same labels  

- **After Stage 8 only:** real paired results  

### Critical analysis (~200)

- Threats to validity (see `docs/limitations.md`)  
- C/D overlap; single-repo scope; fallback quality  
- Whether extra searches help or add noise  

### Conclusion (~150)

- Restate question and what evidence can/cannot support  
- Practical implication for coding-agent context gathering  
- Future work (broader tasks, frozen backends, optional downstream studies)

---

## Minimum source set (planning)

At least five credible sources. Starter set (verify in final bibliography):

1. RepoBench (ICLR 2024) — link in `literature_review.md`  
2. RepoCoder (EMNLP 2023)  
3. Repoformer (PMLR / ICML 2024 proceedings link)  
4. Additional peer-reviewed or high-quality survey/tool paper on RAG or code agents (to be selected)  
5. Additional methodological or SE benchmark source (to be selected)

Do not invent citations.

---

## Alignment with appendices

| Appendix | Purpose |
|---|---|
| A | AI tools and interaction log |
| B | Individual reflections (200–300 words each) |
| C | Group contribution breakdown |
| D | AI presentation dry-run, feedback, improvements made/ignored |

Fill only with **actual** project activity.

---

## Stage 1 status

Report body: **not written**. Plan and templates only.
