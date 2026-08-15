# Post-experiment change boundary

This implementation change was made after the recorded benchmark trajectories
under `benchmark_v0.1/agent_workspaces/full13` had completed.

- Existing competitor trajectory files and outputs were not modified.
- Frozen prospective protocol hashes remain unchanged and therefore correctly
  reject the new Xiaopu runtime as version drift.
- The new runtime must receive a new protocol/version hash before any future
  comparative run; old results cannot be attributed to it.
- Focused implementation tests and a real `3-002` artifact check establish
  code correctness only, not comparative benchmark improvement.

Changed capability surface:

- cross-agent trajectory normalization and process-score reporting;
- semantic PPT editing operations for common benchmark intentions;
- task-local official evaluator discovery and execution;
- finish-time evaluator, structural, render and visual evidence gates.
