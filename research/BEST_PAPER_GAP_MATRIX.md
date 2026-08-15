# ICLR Best Paper gap matrix

Audit time: 2026-08-11 05:25 CST

This matrix is deliberately strict: a green controlled demo is not promoted to
a publication-scale claim. Each row names the evidence that would close the
gap and the current blocker.

| Requirement | Current evidence | Status | Exact closure condition | Next action |
|---|---|---|---|---|
| Core problem and mechanism | CEGAR-H formulation, mutation epochs, typed evidence, adaptive action table | supported in prototype | Independent implementation audit and real-task ablation | Freeze runtime config and publish code path |
| Fresh-evidence safety | post-edit certificate rejection, controlled PPT trace, static audit of 15 registered PPT mutators including speaker notes | controlled-supported | Runtime mutation instrumentation coverage audit across all mutators and external side effects | Add property-based mutation trace and external-side-effect boundary test |
| Theory | Plug-in bounds, correlation bound, dynamic-oracle counterexample, finite checks | bounded-supported | Formal proof review with assumptions checked line by line | External theory review |
| Synthetic mechanism effect | 20-seed paired ablations, calibration shift, held-out calibration | synthetic-only | Held-out real-task trajectories with cost/risk labels | Collect real traces under fixed budget |
| PPT artifact workflow | 4-slide rendered demo plus validated 12-task/3-system protocol; version-pinned resumable 36-cell runner; independent PPTX/PNG recomputation; identity-free dual-reviewer bundles; attested form lock; paired/Holm validator | protocol, execution, and blind pipeline ready; model result missing | All 36 model decks rendered plus two independent locked review forms, agreement, and task-paired contrasts | Generate the frozen 36 decks after credential access, then obtain two real independent reviews |
| Terminal-Bench | 3/241 v2 pilot tasks, 3/3; v3 18-task protocol and adapters dry-run | pilot-only / prospective-ready except live smoke | Exact frozen 18-task v3 run with valid per-task parity ledgers; full score for leaderboard claims | Inject credential, pass non-scored smoke, then run pinned slice |
| SWE-bench Verified | 1 score-eligible pilot; 12-instance/7-repository frozen protocol validated against all 500 official rows | protocol-ready, multi-instance result missing | At least 10 of the 12 instances with score-eligible official reports; full Verified for benchmark claim | Generate genuine patches, then run pinned exact-commit evaluator |
| Competitor comparison | 3-task v2 raw comparison; v2 parity false; v3 gateway/hook/parity verifier implemented | exploratory-only | Same 18 task IDs, 4,500 generated-token / 60 covered-tool / 180-second caps, valid parity, paired CI and exact tests | Run authenticated live smoke and frozen v3 comparison |
| Causal attribution | Synthetic E8 plus validated prospective 12-task × 4-policy / 48-cell real protocol | protocol-ready, missing real causality | Complete all valid cells and preregistered paired inference for direct/always-verify/evidence-only/CEGAR-H | Run frozen protocol after authenticated access |
| Independent review | Local skeptical review and packet only | pending | Dated hash-pinned report and non-author/conflict attestation | Send refreshed paper and evidence packet |
| Claim boundary | Machine audit explicitly reports incomplete objective | honest | Only promote claims whose row is closed | Keep claim gate fail-closed |

## Decision

The strongest current submission is a bounded theory-and-engineering paper with
a controlled rendered PPT demonstration. It is not an ICLR Best Paper claim.
The next executable evidence step is the authenticated non-scored v3 smoke,
followed by the 18-task matched slice. The real controller campaign, paired
model-generated PPT evaluation, multi-instance SWE-bench, and external review
remain separately required; none can be substituted by the synthetic E8 run or
the controlled four-slide demo.
