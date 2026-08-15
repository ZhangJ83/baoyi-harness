# Xiaopu architecture implementation checklist

- [x] Recover and confirm the CEGAR-H theory contract.
- [x] Audit the third-task no-progress trajectory.
- [x] Select the Codex + Claude Code + Xiaopu fusion architecture.
- [x] Freeze implementation and acceptance requirements.
- [x] Add runtime phase and typed turn outcome abstractions.
- [x] Extend belief state with facts, obligations, artifact identity, phase, budgets, and progress.
- [x] Invoke CEGAR-H meta-action selection from the production loop.
- [x] Add semantic observation fingerprints and no-progress control.
- [x] Add read cache and bounded model-visible tool results.
- [x] Add stable idempotent PPT artifact lifecycle.
- [x] Add progressive, phase-aware tool routing.
- [x] Make trajectory writes thread-safe, bounded, and deduplicated.
- [x] Add focused regression tests.
- [x] Run focused architecture tests after final lifecycle changes: 55 passed.
- [x] Re-run the full test suite after the final output-contract and lifecycle changes: 205 passed, 7 skipped.
- [x] Refresh the prospective frozen runtime hashes without changing tasks, budgets, outcomes, or statistics.
- [x] Regenerate real PowerPoint render smoke for the new runtime hash.
- [x] Record implemented scope, limitations, and next checkpoint.

## Implemented checkpoint

- Production `Harness.run()` now calls the CEGAR-H meta-action selector.
- Runtime phases form a safety envelope while CEGAR-H remains adaptive inside it.
- Equivalent observation calls are canonicalized, cached, and scored for novelty.
- Repeated low-information PPT observations force production or terminate safely.
- Model-visible tool results are bounded; full results remain in the recorder.
- PPT working copies are stable and idempotent.
- Recorder sequence and append operations are thread-safe; duplicate inputs/artifacts are suppressed.
- Prospective evaluation protocols were re-pinned before any registered live cells were run.

## Remaining second-stage work

- [x] Add typed `Session` and `TurnOutcome` behind the compatible `Harness.run()` facade.
- [x] Add a thread-safe runtime event bus for controller/tool/turn events.
- [x] Add batched office extraction and a provenance-preserving `ContentIR` foundation.

## Final acceptance checkpoint

- [x] Add deterministic preflight ContentIR and task-directory discovery.
- [x] Add semantic PPT composition for the four-quadrant task.
- [x] Normalize malformed minimal PPT templates into a standard PowerPoint container.
- [x] Make task-specified output paths authoritative over model-supplied generic paths.
- [x] Reject completion without a final PPTX saved during the current run.
- [x] Move final rendering, pixel audit, and multi-source provenance into the lifecycle.
- [x] Refresh the task-local trajectory on every completed run while preserving immutable per-run records.
- [x] Complete the real third task in 31.837 seconds and four model tool calls with structural, render, and visual evidence.

## Remaining later-stage research work

- Continue extracting provider sampling and tool execution from the still-large `Harness` facade.
- Replace heuristic action-gain estimates with a calibrated estimator and persistent failure features.
- Move TUI rendering from the compatibility printer callback fully onto the new event bus.
- Run all preregistered paired competitor/controller cells before making comparative or causal claims; the clean third-task run is engineering acceptance only.
