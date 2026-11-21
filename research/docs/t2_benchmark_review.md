# T2 benchmark validation record

## Annotation sets

The independent A/B pilot remains unchanged. `t2_context_v1` has eight matching
neutral task cards and evaluator annotations. All 34 task-file judgments and 49
spans pass source/schema checks. Human relevance sign-off and main-set acceptance
are pending and recorded separately.

Each judgment records essential/supporting relevance and its rationale. Changed
files are not automatically relevant. Files introduced by the later target are
excluded from pre-change retrieval evidence. Unlisted files remain unjudged.

## Recorded A/B differences

| Task | T2 difference | Context |
| --- | --- | --- |
| A | Adds SDK initialization as supporting evidence | The T2 request explicitly includes SDK/startup dependency timing |
| B | Makes the CLI path essential, adds resource-loader context and omits the public-export judgment | The T2 request explicitly includes install/remove/list and selective resource loading |

`pilot_comparison.json` records the exact paths and label changes. Both task prompts
also differ from the original pilot. The versions are distinct; the T2 annotations
are not substituted into frozen-pilot scoring.

## Candidate overlap

All 28 pairs are recorded in `overlap.csv`. Jaccard values describe file-set overlap;
they are not agent performance or proof of statistical independence.

| Pair | Essential-file Jaccard | Recorded relationship |
| --- | --- | --- |
| B/C | 0.5 | Shared package-management context |
| C/D | 0.5 | C target is already in D parent; both remain reserved candidates |
| E/F | 1.0 | Different behaviors share the same essential file |
| G/H | 0.3333 | Partially shared context; G target is already in H parent |

Eight verified candidate snapshots do not establish eight independent benchmark
observations. Candidate acceptance is a separate recorded decision from Git and
annotation integrity.

## Test inventory and review status

Annotations distinguish existing tests, target-added test files and existing files
modified by the target. Newly added test cases in an existing file are future
content; retrieval uses the parent version only. Inspected Pi test commands are
recorded as not executed.

`review_log.csv` contains the outstanding human relevance reviews. No reviewer
identity or sign-off is fabricated. The CodeRAG-Bench connection and APA reference
are recorded in `literature_review.md`.
