# Independent-review packet (ready for external reviewer)

This packet is prepared for a reviewer who did not participate in the
implementation. It is not itself an external review and must not be cited as
one until a reviewer returns a signed report.

## Scope

Review the method, theory boundaries, statistical protocol, and evidence claims
for CEGAR-H. The intended decision is whether each claim is supported, needs a
downgrade, or is blocked by missing evidence.

## Materials

1. Method and draft: `research/PAPER_DRAFT.md`.
2. Proof-facing theory: `research/THEORY_APPENDIX.md` and `research/THEORY.md`.
3. Claim ledger: `research/CLAIM_EVIDENCE_MAP.json`.
4. Experimental matrix: `research/paper_experiment_matrix.json`.
5. Pilot comparison and paired statistics:
   `workspace/results/official_tb_matched_summary.json` and
   `workspace/results/claims_gate_current.json`.
6. Synthetic ablations:
   `workspace/results/paired_synthetic_ablation.json`,
   `workspace/results/cegarh_ablation_20seed.json`, and
   `workspace/results/verifier_correlation_sweep.json`.
7. Completion audit: `workspace/results/completion_audit_current.json`.
8. One-hour sprint evidence and explicit non-promotions:
   `research/ONE_HOUR_SPRINT_REPORT.md`,
   `workspace/results/paired_synthetic_ablation_latest.json`, and
   `workspace/results/one_hour_ppt_score.json`.
9. Prospective v3 fairness protocol and readiness boundary:
   `benchmarks/matched_protocol_v3.json`,
   `workspace/results/matched_protocol_v3_validation.json`, and
   `workspace/results/matched_v3_live_smoke_validation.json`.
10. Authoritative full-objective gate:
    `workspace/results/objective_gate_current.json`.

## Reviewer questions

### Theory

- Are the binary and finite-action regret statements correctly scoped?
- Does the freshness theorem rely on an assumption that is clearly visible?
- Is the correlated-verifier bound stated without an invalid independence step?
- Does the dynamic-oracle counterexample adequately block a global optimality
  interpretation?

### Experimental design

- Are seed-level synthetic intervals clearly separated from task-level benchmark
  intervals?
- Does the matched protocol prevent task-set, model, provider, or scorer drift?
- Are the planned 12-task and multi-instance SWE slices sufficient for the
  proposed claim, or should the inferential gate require more?
- Is the deterministic PPT fixture evidence correctly excluded from model
  efficacy claims?

### Reproducibility and claim integrity

- Can every number in the draft be traced to a durable artifact?
- Are any sentences stronger than the evidence supports?
- Are there hidden degrees of freedom in the comparator adapters or token caps?
- What single missing experiment most threatens the central claim?

## Required response format

Return a dated report with one row per claim (`C1`–`C4`), a severity label
(`blocking`, `major`, `minor`), concrete evidence, and a recommended wording
change. State explicitly whether the review was blind to system identity and
whether any external computation was performed.

To make the review machine-admissible, also return
`research/review/external_review_attestation.json` using
`research/review/external_review_attestation.example.json` as the template.
The report must be inside `research/review/`; the attestation must declare
non-authorship, independence and conflicts, and pin the returned report's
SHA-256. The packet itself never satisfies this gate.

## Current known blockers

The repository intentionally records the following as unresolved: full
Terminal-Bench score, multi-instance SWE-bench Verified score, sufficiently
powered competitor superiority, model-generated PPT evaluation, and external
independent review. A reviewer should verify rather than assume these have
since changed.

The 2026-08-11 sprint did not change those blockers: provider-backed trials
were prevented before token spend by a missing process credential, while the
synthetic and deterministic PPT paths were successfully revalidated.
