# Provider pilot failure analysis

## Observed run

The first one-task DeepSeek pilot reached the provider and executed 11 tool
calls, consuming 23,915 tokens. It stopped because the response exceeded the
configured total-token budget; it did not fail authentication and did not
modify the workspace.

## Root-cause classification

1. **Fixed per-turn cap**: every request used the default output cap, even when
   little budget remained.
2. **Late stopping signal**: the model was not explicitly told to switch from
   exploration to final verification near exhaustion.
3. **No repeated-action circuit breaker**: identical no-progress actions could
   continue until the global budget was consumed.

## Implemented changes

- Per-turn output caps now use the smaller of the configured cap and remaining
  total budget, for both OpenAI and Anthropic clients.
- Near-exhaustion turns receive a final-verification-and-finish hint.
- Three identical no-progress action batches trigger a circuit breaker.
- Provider retries default to zero in benchmark pilots.

## Required follow-up

Run exactly one fresh pilot with the same task and a 12k-token cap using
`benchmarks/run_provider_pilot.ps1`. Compare total tokens, tool calls, status,
and changed files against the recorded baseline. No claim of improvement is
valid until that run exists.
