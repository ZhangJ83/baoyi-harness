# Xiaopu experiment report (current branch)

> Evidence update 2026-08-10: the historical statements below that say no
> matched run or no official execution predate the repaired Docker/provider
> path. Current authoritative status is in
> `workspace/results/completion_audit_current.json` and
> `docs/evidence-index.md`: a 3-task matched Flash pilot and a one-instance
> score-eligible SWE pilot exist, but neither is a full benchmark score.

## Scope

This report consolidates the current evidence for the harness and PPT
workflow. It does not claim official benchmark superiority.

## Prototype pilots

| Suite | Completed | Attempted | Interpretation |
|---|---:|---:|---|
| Terminal-style | 3 | 5 | custom pilot only |
| SWE-style | 3 | 5 | custom pilot only |
| PPT | 1 | 1 | end-to-end structural and rendered evidence |

Full token/tool metrics are in `PILOT_SUMMARY.json`.

## Official SWE-bench preparation

The five frozen Astropy samples have verified base commits, problem
statements, and gold patches. `workspace/official_swe/verification5.json`
records five `checkout_verified` rows and five successful `gold_patch_check`
rows.

Official test execution is not yet complete. Historical Astropy C-extension
compatibility remains an environment gate.

The official SWE-bench repository is now pinned locally at commit
`cd37836`. Its evaluator entrypoint and Verified dataset name are available,
but no official SWE-bench score has been claimed: a valid score still requires
an official prediction file, the exact `SWE-bench/SWE-bench_Verified` split,
and the evaluator's Docker test path.

The evaluator source has been import-audited. The current offline Python
environment is missing the optional `modal` runtime; a narrow local-only
fallback now keeps the official Docker evaluator path importable and fails
explicitly if `--modal` is requested. Source checkouts for `ghapi`,
`fastcore`, `fastspec`, and `unidiff` are present under `official_refs/` for a
reproducible dependency repair.

The official loader has also returned the cached Verified test record
`astropy__astropy-12907` at base commit
`d16bfe05a744909de4b27f5875fe0d4ed41ce607`; this is recorded as metadata
readiness only, not a model or oracle score.

An oracle-only official scorer smoke was attempted for that instance. It
reached the official Docker base-image build, but apt dependency installation
failed under five recorded endpoint configurations (archive endpoint failure,
missing CA for HTTPS mirror, HTTP 403, and intermittent package fetch
failures from Aliyun). The evaluator therefore did not
run tests; this is an environment blocker, not a benchmark result.

## Official Terminal-Bench preparation and pilot

The official Terminal-Bench repository is pinned at `d28711d` (`0.2.18`). A
Windows-only POSIX-container-path compatibility shim was applied outside the
Xiaopu package. The official harness completed `hello-world` (1/1) and a
finalized three-task pilot (`hello-world`, `fix-permissions`, `extract-safely`,
2/3). These are small protocol pilots, not the full benchmark score.

## Near-line issue evidence

`NEARLINE_EVIDENCE.json` records three reproduced issue behaviors and one
environment incompatibility under Astropy 5.0.4/NumPy 1.26.4. These results
are diagnostic only and are explicitly not formal SWE-bench scores.

## Claims boundary

There is currently no full official Terminal-Bench score, no full official
SWE-bench score, and no evidence supporting an ICLR Best Paper or
state-of-the-art claim. A matched 3-task Claude Code/Codex/OpenCode pilot now
exists, but `benchmarks/paired_stats.py`
now provides task-level Wilson intervals and paired bootstrap deltas for the
future matched runs; it must not be fed repeated-call counts as independent
tasks.

## Next experiment

Run one exact-commit official test in a pinned Linux environment, persist raw
logs, then extend to the remaining four tasks before spending additional
model/API budget on competitor comparison.
