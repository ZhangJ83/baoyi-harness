# Constrained Evidence-Guided Adaptive Runtime for Harnesses (CEGAR-H)

The proof-facing derivations, assumptions, and constants are collected in
`THEORY_APPENDIX.md`; this file remains the compact design statement.

EGAD is retained below as the compute-gating subproblem. CEGAR-H extends it by
jointly selecting evidence acquisition and deliberation; mutation freshness is
a constraint, not the paper's standalone novelty.

## 1. Problem

At decision step `t`, a harness observes compressed state `x_t`, may either act directly
or buy an additional computation `d_t` (planning, branching, retrieval, or verification),
then chooses an environment action. Let task utility be success `Y in {0,1}`, inference and
tool cost be `C`, and safety loss be `L`. For multipliers `lambda, mu >= 0`, optimize

`J(pi) = E[Y - lambda C - mu L]`.

This is a metareasoning objective, not a standard bandit regret claim. The base LLM may be
fixed; learning occurs in the harness's calibrated benefit estimator and persistent state.

## 2. Value-of-computation gate

Let `Delta(x) = E[Y | deliberate, x] - E[Y | direct, x]` and deliberation cost `c(x)`.
The oracle Lagrangian policy deliberates exactly when

`Delta(x) > lambda c(x) + mu Delta_L(x)`.

This follows pointwise because the meta-action is binary and expectations are additive.
It explains why neither always-search nor never-search can be optimal on heterogeneous tasks.

### Proposition 1: plug-in gate regret

Assume the estimated net benefit `b_hat(x)` satisfies `|b_hat(x)-b(x)| <= epsilon`, where
`b(x)=Delta(x)-lambda c(x)-mu Delta_L(x)`. The plug-in rule `1[b_hat(x)>0]` has per-decision
utility regret at most `epsilon` relative to the oracle gate; therefore over `T` decisions
its regret is at most `epsilon T`.

Proof sketch: the rules differ only when zero lies between `b` and `b_hat`; then
`|b| <= |b-b_hat| <= epsilon`.

For this binary zero-threshold gate the proof can use the tighter `epsilon`
bound: disagreement implies that `b` and `b_hat` have opposite signs (or one is
zero), hence `|b| <= |b-b_hat|`. For selecting the argmax among three or more
meta-actions under uniform score error, the standard bound is `2 epsilon`;
experiments and the formal appendix must not conflate these two settings.

This is deliberately not advertised as sublinear regret. Sublinear results would require a
specified online learner, feedback observability, and distributional assumptions.

## 3. Fresh evidence as a termination invariant

Let `e_t` be a monotone mutation epoch, incremented after every state-changing tool. Evidence
record `v` has scope, outcome, and epoch `epoch(v)`. A completion certificate is fresh iff

`pass(v)=1 and epoch(v)=e_t`

for every required scope affected by the task.

### Proposition 2: stale-certificate exclusion

Under complete mutation instrumentation, a completion rule requiring epoch equality cannot
accept solely on evidence produced before the most recent mutation.

This is an invariant, not a probabilistic accuracy claim. It eliminates a concrete failure
mode in the previous implementation. It does not prove that a fresh verifier is sound.

## 4. Correlation-robust cascade

For required verifiers `V_1...V_K`, acceptance occurs only if all pass. If verifier `i` has
false-accept probability `alpha_i` on bad states, then without independence

`P(all pass | bad) <= min_i alpha_i`.

The product `prod_i alpha_i` is valid only under conditional independence. Experiments will
vary error correlation explicitly rather than assuming it away. Ordering affects expected
cost, so we estimate conditional continuation probabilities from data.

## 5. Approximately sufficient compressed state

A compressed state map `phi(H_t)` is `epsilon`-predictively sufficient if, for every allowed
action, the total-variation distance between next-observation/reward distributions conditioned
on full history and on `phi(H_t)` is at most `epsilon`.

Under bounded per-step reward `|r| <= R_max` and horizon `H`, a standard simulation argument
gives value deviation of order `O(H^2 R_max epsilon)`; exact constants depend on whether the
error is uniform per transition or stated over trajectory distributions. We will not present
a sharper constant until the proof assumptions are fixed. Operationally, EGAD preserves goal,
open obligations, mutation epochs, fresh evidence, failure fingerprints, and recent raw turns,
then measures recovery loss under controlled truncation.

## 6. Falsifiable predictions

1. If task difficulty is homogeneous or benefit estimates are uncalibrated, EGAD should not
beat the better fixed policy and may be worse due to controller overhead.
2. If verifier errors are perfectly correlated, adding cascade levels should not produce the
product-form gain.
3. If mutation instrumentation misses a state-changing tool, epoch freshness can be bypassed.
4. If compressed state omits an action-relevant latent variable, recovery loss will persist
regardless of summary fluency.

## 7. Joint evidence/computation selection

Let meta-action `m` be direct action, a deliberation operator, or an evidence
operator. Each has expected utility gain `g_m(x)`, cost `c_m(x)`, latency
`tau_m(x)`, and residual false-completion risk `rho_m(x)`. The one-step oracle
chooses

`argmax_m g_m(x) - lambda c_m(x) - nu tau_m(x) - mu rho_m(x)`

subject to fresh-certificate constraints. This pointwise rule is only myopically
optimal. A multi-step optimality claim requires a belief-state MDP and is not
made here. The research contribution must therefore compare the practical
myopic/index controller with a dynamic-programming oracle in small synthetic
environments and quantify the gap.

### Proposition 3: correlation-robust acceptance

For any chosen verifier set `S`, accepting only when every verifier passes has
bad-state false-accept probability at most `min_{i in S} alpha_i`, without an
independence assumption. This bound alone cannot justify adding verifiers: the
controller must trade the measured conditional risk reduction against cost.

## 8. Finite-domain exhaustive check

`experiments/exhaustive_theory_check.py` enumerates every binary case and every
three-action case on the declared grid `{-1,-0.75,...,1}` with errors in
`{-epsilon,0,+epsilon}`. At `epsilon=0.25`, it checks 27 binary and 19,683
multi-action cases, with maximum regrets exactly `epsilon` and `2 epsilon` and
zero violations. This is a finite-grid consistency check, not a proof over
continuous values; the proof obligations remain the assumptions stated above.
