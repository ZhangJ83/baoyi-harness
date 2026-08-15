# Revision log

| ID | Issue | Type | Blocks finalization? | Required change |
|---|---|---|---|---|
| R1 | No official agent-generated SWE/Terminal score | evidence | yes | Infrastructure repaired; 3-task Terminal pilot and 1-task official SWE pilot now exist, but full scores remain open |
| R2 | Pointwise rather than dynamic oracle | experiment | addressed for wording; external efficacy still open | `dynamic_oracle_h3.json` supplies finite-horizon DP counterexample |
| R3 | Estimator calibrated only by construction | experiment | addressed for synthetic scope | Controlled shift sweep plus 20-seed 70/30 held-out ECE/Brier calibration; external learned calibration remains open |
| R4 | Native competitor provider contracts differ | protocol | partially addressed | Common Flash-provider matched slice is complete and disclosed; larger predeclared slice still required |
| R5 | Synthetic seed CIs only | statistics | yes for external claims | Paired task bootstrap now covers the 3-task pilot; larger task-level sample still required |
| R6 | Correlation sweep not executed | experiment | addressed for narrow invariant claim | `verifier_correlation_sweep.json` varies shared error and checks the bound |

No prose revision can resolve R1–R5; these require evidence or a narrower
claim boundary.
