# Continuous optimization goal

## North-star objective

Continuously improve the Xiaopu / CEGAR-H PPT harness research until the
evidence package is genuinely competitive for an ICLR Best Paper-level review.
This is an evidence target, not a guaranteed award outcome.

## Optimization loop

Every iteration must:

1. read `workspace/results/objective_gate_current.json`;
2. choose the unresolved row with the highest expected information gain;
3. freeze task, baseline, budget, metric, stop rule, and claim-promotion rule;
4. run the smallest valid discriminative experiment;
5. classify failures as model, protocol, infrastructure, or external blockers;
6. update code, tests, paper, claim map, failure analysis, and evidence manifest;
7. rerun regression, objective gate, and archive verification;
8. continue until every required row has authoritative evidence.

## Priority frontier

1. credential-enabled, parity-logged real-task comparison;
2. real-task CEGAR-H controller causal ablation;
3. frozen model-generated PPT generation/edit/layout slice with rendering and
   blinded semantic/visual review;
4. multi-instance official SWE-bench Verified evidence;
5. dated independent external review and resulting revisions.

## Non-negotiable gates

- No superiority claim without identical task IDs, scorer, model/provider
  contract, token/tool/step budgets, preregistered minimum n, paired confidence
  interval excluding zero, and exact-test threshold.
- No PPT efficacy claim from deterministic fixtures or the controlled demo.
- No benchmark score from a pilot denominator.
- No independent-review claim from self-review or an unsent review packet.
- No Best Paper or completion claim while `objective_complete=false`.

## Completion condition

Completion requires every required objective-gate row to be achieved, all
paper claims mapped to durable evidence, full regression and archive integrity
passing, and no unresolved required work. Award selection itself remains an
external conference decision and cannot be guaranteed by the artifact.
