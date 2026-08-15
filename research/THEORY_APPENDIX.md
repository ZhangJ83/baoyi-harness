# CEGAR-H theory appendix: assumptions and derivations

This appendix is the proof-facing companion to `THEORY.md`. It distinguishes
exact statements from finite computational checks. No empirical result below
is used as a substitute for a proof.

## A. Notation and utility

At a fixed decision state (x), let the two meta-actions be direct action
(d) and deliberate/check action (q). Define their conditional expected
net utilities

\[
U_d(x)=\mathbb{E}[Y-\lambda C-\mu L\mid d,x],\qquad
U_q(x)=\mathbb{E}[Y-\lambda C-\mu L\mid q,x].
\]

The oracle difference is (b(x)=U_q(x)-U_d(x)). The oracle chooses (q) iff
(b(x)>0). We assume both expectations are finite and that the state and
action are held fixed during this one-step comparison.

## B. Binary plug-in gate

**Theorem B.1.** Suppose an estimator satisfies
\[
|\widehat b(x)-b(x)|\leq\epsilon
\]
for a particular state. The plug-in rule
\(\widehat\pi(x)=\mathbf{1}[\widehat b(x)>0]\) has one-step regret at most
\(\epsilon\) relative to the oracle.

**Proof.** If both rules select the same action, regret is zero. Otherwise,
without loss of generality (b(x)>0) while \(\widehat b(x)\leq0\). Then
\[
0<b(x)=|b(x)|\leq |b(x)-\widehat b(x)|+|\widehat b(x)|.
\]
The sign conditions give the tighter direct relation
\(0<b(x)\leq b(x)-\widehat b(x)\leq\epsilon\). The selected action loses
exactly (b(x)), hence regret is at most (epsilon). The opposite sign case
is symmetric. Summing over (T) fixed decision points gives at most
(T\epsilon); this is a worst-case bound, not a sublinear online-regret
statement. □

## C. Finite-action plug-in argmax

**Theorem C.1.** Let a finite action set (mathcal A) have true scores
(u(a)) and estimates (widehat u(a)) satisfying
\[
\max_{a\in\mathcal A}|\widehat u(a)-u(a)|\leq\epsilon.
\]
If \(\widehat a\in\arg\max_a\widehat u(a)\) and
\(a^*\in\arg\max_a u(a)\), then
\[
u(a^*)-u(\widehat a)\leq 2\epsilon.
\]

**Proof.** By uniform error,
\(u(a^*)\leq\widehat u(a^*)+\epsilon\). By optimality of \(\widehat a\),
\(\widehat u(a^*)\leq\widehat u(\widehat a)\). Again by uniform error,
\(\widehat u(\widehat a)\leq u(\widehat a)+\epsilon\). Combining the three
inequalities yields the result. □

The binary theorem is tighter because the decision boundary is one scalar
difference. The (2\epsilon) finite-action result must not be reported as the
binary bound.

## D. Freshness invariant

Let the ledger epoch (e_t\in\mathbb N) increase strictly after every
state-changing operation that is visible to the harness. A certificate (v)
stores `epoch(v)` and a pass bit. A completion rule requires
\[
\forall v\in R_t:\quad \operatorname{pass}(v)=1
\land \operatorname{epoch}(v)=e_t,
\]
where (R_t) is the required certificate set at time (t).

**Theorem D.1.** Under complete mutation instrumentation, a certificate
created at epoch (e<e_t) cannot satisfy the completion rule at time (t).

**Proof.** The rule contains the equality `epoch(v)=e_t`. The certificate has
`epoch(v)=e`, while strict epoch monotonicity gives (e<e_t); equality is
false. Therefore that certificate cannot be the certificate that discharges
the affected requirement. □

The theorem is purely about admissibility. It does not imply verifier
soundness, completeness, or detection of uninstrumented external side effects.

## E. Correlation-robust all-pass bound

Let (B) denote a bad state and (A_i) the event that verifier (i) accepts.
Assume only marginal bounds (P(A_i\mid B)\leq\alpha_i). For any nonempty
verifier set (S),
\[
P(\cap_{i\in S} A_i\mid B)
\leq P(A_j\mid B)\leq\alpha_j
\quad\text{for every }j\in S.
\]
Taking the minimum over (j) gives
\[
P(\text{all pass incorrectly}\mid B)\leq\min_{j\in S}\alpha_j.
\]
No independence assumption is used. The product \(\prod_i\alpha_i\) is valid only
under conditional independence and is intentionally not used by the harness.

## F. Approximate predictive state compression

Let (H_t) be full history and (z_t=\phi(H_t)) a compressed state. Assume
for every paired histories with the same (z_t), every action (a), and every
bounded measurable next-state/reward event, the one-step transition/reward
kernel has total-variation distance at most (epsilon). Let per-step reward
lie in ([0,R]), horizon be (H), and use the same policy after matching
compressed states.

A coupling can keep the two processes identical at step (t) with probability
at least (1-t\epsilon) by a union bound over the previous (t) kernel
couplings. The expected reward difference at step (t) is therefore at most
(R t\epsilon). Summing gives the conservative finite-horizon value bound
\[
|V_H^{\text{full}}-V_H^{\text{compressed}}|
\leq R\epsilon\sum_{t=0}^{H-1}t
=\frac{R\epsilon H(H-1)}{2}.
\]

This bound assumes a uniform kernel error and identical action selection after
coupling. It is intentionally conservative; a sharper constant requires a
specific Markov-kernel contraction assumption. The repository therefore
reports compression checks as bounded analyses, not as a universal theorem of
summary quality.

## G. Why local optimality is not global optimality

The one-step controller maximizes estimated immediate net value. A finite
horizon process can make a low-immediate-value information action unlock a
large later reward, so a dynamic-programming policy can strictly dominate the
myopic index. The executable counterexample is recorded in
`workspace/results/dynamic_oracle_h3.json`. This is why the method claim is
bounded local allocation plus freshness safety, not optimality over all
belief-state policies.

## H. Computational checks and their status

`experiments/exhaustive_theory_check.py` enumerates 27 binary and 19,683
three-action finite-grid cases at (epsilon=0.25), observing maxima
(epsilon) and (2\epsilon) with zero violations. These checks are useful for
implementation regression, but finite enumeration cannot establish the
continuous-domain theorems above. The randomized checks in
`workspace/results/theory_bound_check.json` have the same status.
