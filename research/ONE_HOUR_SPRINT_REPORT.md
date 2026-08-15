# One-hour evidence sprint report

Date: 2026-08-11. Claim status: partial evidence only.

## P0 matched real-task pilot

Blocked before token spend. `provider_preflight_sprint.json` shows Docker 29.5.3
ready and pinned images cached, but no provider credential in the current
process. No trial was started and no model failure was recorded.

## P1 controller evidence

The paired synthetic ablation was rerun with 20 seeds and 2,000 tasks per seed.
On the heterogeneous family, CEGAR-H minus always-joint is 0.0270 with paired
bootstrap 95% CI [0.0267, 0.0273], and minus direct is 0.1853 [0.1842,
0.1864]. This is synthetic-only auxiliary evidence and does not close the
real-task causal-ablation requirement.

## P2 PPT mini-slice

Five deterministic structural fixtures were regenerated and scored against the
frozen `pptbench-fixed-v1` manifest. All five scored 1.0 on openability,
minimum slides, required text, and overflow proxy. Create, modify, and restyle
fixtures were additionally converted by the pinned local Docker renderer:

- create: 3 PNG slides plus PDF; pixel audit passed;
- modify: 1 PNG slide plus PDF; pixel audit passed;
- restyle: 1 PNG slide plus PDF; pixel audit passed.

This validates the scorer/render path only. The fixtures are not model outputs,
and the result is not PPTBench performance.

## P3 SWE and P4 independent review

No new provider-backed SWE trial was started because the same credential gate
would make it invalid. The existing one-instance official result remains a
pilot. The external review packet was refreshed for handoff, but receipt of an
independent human report remains external and pending.

## Decision

The sprint strengthens reproducibility and confirms that P1/P2 auxiliary paths
remain operational. It does not change the paper's primary claim boundary. The
next valid experiment remains the credential-enabled, parity-logged P0 slice.

