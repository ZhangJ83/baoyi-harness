# Research direction selection

Framing: problem-first. Bottleneck: fixed agent loops spend too much on easy
states, too little on risky states, and can terminate on evidence invalidated by
later mutations.

## Bounded divergence

Raw directions considered: fixed-depth search, learned tool routing, verifier
cascade ordering, mutation epochs, artifact dependency graphs, context
compression, selective abstention, risk-sensitive completion, online failure
memory, and joint evidence/compute allocation.

## Serious frontier

| Candidate | Novelty | Falsifiability | Feasibility | Evidence fit | Verdict |
|---|---:|---:|---:|---:|---|
| FreshCert: epoch-bound verification | 3 | 9 | 10 | 8 | reject as paper core; EA-Graph/STALE overlap |
| Adaptive deliberation only | 5 | 9 | 9 | 8 | defer; too close to adaptive compute/test-time scaling |
| **CEGAR-H: Constrained Evidence-Guided Adaptive Runtime for Harnesses** | **7** | **9** | **8** | **8** | selected, conditional on overlap audit |

Scores are /10 judgments, not experimental results.

## Selected idea: CEGAR-H

Stable id: `CEGAR-H-001`.

Two-sentence pitch: An agent should not always think longer or always run every
test. CEGAR-H jointly chooses the next computation and the next evidence source
by estimated marginal reduction in completion risk per unit cost, and permits
termination only when the resulting evidence certificate is fresh for the
current artifact state.

Falsifiable claim: at matched base model and safety budget, CEGAR-H improves
the area under the success-versus-cost curve over direct/ReAct-like,
always-deliberate, fixed-cascade, and adaptive-compute-only policies on
heterogeneous tasks; it should not improve on homogeneous tasks or with an
uncalibrated benefit model.

Why now: recent systems expose both test-time scaling and stale-evidence failure,
but their conjunction makes fixed loops increasingly wasteful and unsafe.

Strongest objection: this may be a clean integration of known mechanisms rather
than a new learning principle. Response boundary: the paper must earn its value
through a formal joint decision problem, correlation-aware guarantees, and
cross-domain Pareto evidence; otherwise it is infrastructure/platform value,
not a top-tier method claim.

## Minimal experiment contract

1. Synthetic oracle environment with known action/evidence utilities.
2. Policies: direct, always deliberate, fixed verifier cascade, compute-only
   gate, evidence-only gate, CEGAR-H, and oracle.
3. Metrics: success, unsafe false completion, cost, latency proxy, calibration,
   and hypervolume/area under the risk-constrained success-cost frontier.
4. Ablations: no epochs, independence-assuming cascade, FIFO context, no risk
   term, no evidence choice, and corrupted benefit estimates.
5. Promotion gate: deterministic predictions pass; then a small unpaid/local
   task pilot; only then paid DeepSeek and external benchmarks.

## Deferred/rejected

- Artifact dependency graph: defer because EA-Graph is directly adjacent.
- Learned monolithic router: reject for weak interpretability and costly data.
- Multi-agent debate: reject because it mainly buys performance with more tokens.
- PPT-only layout agent: retain as application/evaluation track, not core theory.

## References

See `research/literature_survey.md`; citations [1]–[12] there define the current
novelty boundary and experimental baselines.

