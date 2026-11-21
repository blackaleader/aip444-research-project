# T2 snapshot and worktree review

All eight original targets were resolved in local Git and cross-checked against
GitHub's Git-commit API. `benchmark/reviews/t2_context_v1/upstream_identity_check.json`
records the upstream target, parent list, tree identity and source URLs.

| Candidate | Complete original target | Complete pre-change parent |
| --- | --- | --- |
| A | `40c256cccbce062f6af5f2cacb85d0ce1ab4224d` | `bfa6862400d0aaa3ebf3c09a44a2479487f470f1` |
| B | `ef1fc3103ee869244800f301993bd4952125db78` | `dd838d0fe09db079dcf2f57bab1d79d4df5a0e4c` |
| C | `4058680d225535d25705aaf02644957c0ed7a096` | `b846a4bfcf168ae218dbeb0fecc24a98c0b3e332` |
| D | `50c83235904bb24e8d634cc25f7f761ec1324e98` | `c5c515f56096f212e0ad1e7f5c3c9b115908d37c` |
| E | `37067e0166dbbcd9362797d84ab44c6f98e6cc40` | `486066574ce7a11dc55d1296e2adf322c940526e` |
| F | `835296b1d7d999100ee1c465b4958031d0bb5adc` | `9a0be024a6ff381362e04b19dd1c155c44675f4a` |
| G | `8191d59c170c9bb336a82771e1826d25bb7ec1e0` | `8632e1b9484b9be62e8fc9b31757176f7c560313` |
| H | `e40126f578ccc0a4a21f8d30cd8e96c8ecfe1722` | `1a584a7a56eb5e7b4ff8ccbd46430f1533282eed` |

## Candidate E resolution

The Stage 2 failure accurately described that checkout's available objects. The
original target is now directly resolvable, with subject `fix(coding-agent): retry
connection lost errors`; the expected `4860665` parent prefix matches. No alternate
commit or unrelated fix was substituted. Upstream source:
https://github.com/earendil-works/pi/commit/37067e0166dbbcd9362797d84ab44c6f98e6cc40

If that object is missing locally:

```sh
git -C /path/to/pi-upstream fetch origin 37067e0166dbbcd9362797d84ab44c6f98e6cc40
git -C /path/to/pi-upstream show -s --format="%H%n%P%n%T%n%s" 37067e0166dbbcd9362797d84ab44c6f98e6cc40
```

## Pilot worktree checks performed

Both pilot parents were materialized in separate detached worktrees using
`prepare_worktrees.py`. Each HEAD matched its recorded parent, both worktrees were
clean and their common Git directory matched the source clone. The existing source
clone and original benchmark files were left intact. The six additional annotation
sets were checked directly against Git objects. Pi application tests were not run;
only the two pilot worktrees were materialized.

Use the portable reproduction procedure in [t2_integration.md](t2_integration.md).
Worktree verification and annotation provenance do not certify semantic labels or
absence of model-training contamination from a public repository.
