# Failure analysis: authorized Terminal-Bench slice (2026-08-11)

## One-hour sprint credential gate

The later one-hour sprint passed Docker and pinned-image preflight but found no
provider credential in the current process. The runner stopped before any
model-backed trial or token spend. This is a preflight blocker, not a model
failure and not an infrastructure-invalid scored trial.

## Offline aggregate-budget sensitivity

`benchmarks/analyze_budget_sensitivity.py` compares the same three tasks under
singleton and aggregate offline reproduction runs. Singleton execution resolves
3/3, whereas aggregate execution under the shared cap resolves 1/3, a
descriptive rate delta of -0.667. `extract-safely` and `hello-world` regress;
both truncated aggregate trials are missing token ledgers. The evidence supports
a budget-allocation sensitivity warning, but the missing ledgers prevent precise
per-task causal attribution. This is offline real-trace analysis, not an
official score or randomized controller ablation.

The adapter has since been repaired so every exit path, including provider,
tmux, parse, and budget failures, returns input/output token totals and writes a
`budget_ledger.json` with the failure mode when a logging directory is
available. Seven adapter tests pass in the official Terminal-Bench environment,
including fatal-parse and provider-error ledger preservation. Historical null
ledgers remain unrecoverable; future runs should no longer lose this evidence.

The first post-reboot authorized three-task run is retained as a failure
analysis artifact, not as a performance score.

| Task | Observed outcome | Root cause class | Interpretation |
|---|---|---|---|
| `hello-world` | parser error | container dependency/network | `run-tests.sh` could not install `curl`/`uv`; no valid test summary was produced |
| `fix-permissions` | parser error and model truncation | dependency/network plus budget | apt/GHCR setup failed and the 1500-token output cap was too small |
| `extract-safely` | unresolved | agent behavior | test harness ran, but the requested solution file was not produced |

The aggregate `0/3` is therefore not a valid estimate of harness accuracy:
two tasks are infrastructure-invalid and one is a genuine agent failure. The
next controlled run must pre-cache the official base images and test tools,
raise the output cap for repair tasks, and report infrastructure-invalid
trials separately from valid task outcomes.

After the official images were cached, the follow-up run resolved
`hello-world` (`1/2` completed before the runner timeout). `fix-permissions`
became a valid task failure (`test_script_permissions: failed`), while
`extract-safely` was still in progress when the outer runner timed out. This
confirms that container initialization failures and agent task behavior must
be analyzed separately.

The targeted `fix-permissions` retry then showed the intended agent trace:
`test -x`, `chmod +x`, and an invocation of `/app/process_data.sh` all ran.
The official test phase still failed to download `uv` from GitHub, so the
trial remains parser-invalid despite the corrected agent behavior.

Using the independent offline reproduction protocol with the cached Linux
dependencies and a 3000-token output cap, `fix-permissions` resolved `1/1`.
Together with the earlier offline `hello-world` result (`1/1`), this gives a
2/2 offline behavioral result. It is explicitly not an official benchmark
score, but it is direct evidence that the harness-level repair removed the
agent failure once infrastructure and output-budget confounds were controlled.

Finally, the same protocol resolved `extract-safely` (`1/1`), yielding a
controlled **3/3** behavioral result across the matched task slice. This is
reported as offline reproduction evidence only; the official score remains
the run performed against the unmodified benchmark environment.

An aggregated three-task run with the same nominal 12k total-token cap later
produced 1/3 because two model calls were truncated, even though the three
single-task runs under the same offline protocol each resolved 1/1. This is a
budget-allocation sensitivity finding: the paper must report per-task caps,
truncation counts, and retry policy rather than treating one aggregate run as
the complete estimate.

The adapter now performs one budget-accounted compact-JSON repair call after a
parse/truncation failure. The retry is capped at 512 output tokens and is
included in the ledger, so recovery cannot silently exceed the declared
budget.
