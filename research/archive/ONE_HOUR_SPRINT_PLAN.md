# One-hour evidence sprint

Start: 2026-08-11 03:10 Asia/Shanghai. Hard stop: 04:10.

## Run contract

- Question: can the current package add valid real-task and PPT evidence within one hour?
- Baselines: existing three-task Terminal-Bench pilot, direct/always-verify/evidence-only policies, controlled PPT demo.
- Fixed conditions: frozen task IDs, one attempt, one concurrent run, temperature 0, explicit token/tool/step caps.
- Primary metrics: resolved rate, paired delta, tokens, tool calls, steps, wall time; PPT structural/render/visual scores.
- Stop rule: abandon any branch after five minutes without a new discriminative signal; infrastructure-invalid trials are never scored as model failures.
- Claim rule: all one-hour results remain pilot evidence unless the preregistered minimum-n, parity, and statistical gates pass.

## Execution frontier

1. P0 provider/Docker preflight and authorized matched mini-pilot.
2. P1 real controller comparison if provider execution is available; otherwise refresh paired synthetic ablation as auxiliary evidence.
3. P2 frozen three-task model-generated PPT mini-slice, or deterministic fixture slice if provider execution is unavailable.
4. P3 bounded SWE mini-slice only if official evaluator and remaining runtime allow.
5. P4 prepare, but do not fabricate, an external review request packet.
6. Update paper, objective gate, integrity manifest, regression and archive.

