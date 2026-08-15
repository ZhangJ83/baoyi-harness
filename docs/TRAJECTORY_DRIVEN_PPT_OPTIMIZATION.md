# Trajectory-driven PPT harness optimization

## Evidence used

The benchmark analysis normalizes 42 recorded trajectories under
`benchmark_v0.1/agent_workspaces/full13`: 13 Claude Code, 13 Codex, 13
WorkBuddy-DeepSeek and 3 OpenCode runs. The records use different schemas and
are agent-authored summaries unless raw telemetry is present, so process
claims are restricted to recorded evidence.

## Repeated effective patterns

1. Claude Code repeatedly follows targeted inspect -> deterministic edit ->
   render -> inspect, with a scoped repair when rendering exposes a defect.
2. Codex records an explicit compact plan and stable artifact operations, then
   exports and renders the current artifact.
3. WorkBuddy reads the supplied rubric/evaluator and runs a task-native check;
   its failure records expose why generic structure checks are insufficient.
4. OpenCode's completed subset shows useful failure -> repair -> re-verify
   traces, but the sample is too small for comparative quality claims.

## Xiaopu architecture decision

The model chooses intent; the harness owns lifecycle and evidence:

`task intake -> ContentIR + evaluator discovery -> compact plan -> semantic
PPT operation -> required-path save -> structure check -> official evaluator
when supplied -> render -> visual audit -> bounded scoped repair -> finish`

The implementation intentionally avoids putting this workflow in every user
prompt. It is enforced by phase-based tool exposure, mutation epochs, fresh
evidence, the final-artifact gate and a capped repair loop.

## Implemented deltas

- Cross-agent trajectory normalization now understands `action`, `kind`,
  `tool` and `step`, companion plan/check files, visual image reads and stop
  records.
- Intake discovers `tests/grading/test_verify.py` and binds it as the official
  evaluator for the active task.
- `run_task_evaluator` executes that evaluator with local task/output/gold/log
  paths, records its transcript and creates fresh current-epoch evidence.
- `finish` automatically requires the official evaluator when one was found,
  before buying final render and visual evidence.
- Semantic edit tools cover repeated benchmark operations without ad-hoc
  scripts: cross-run text replacement, peer bullet append with style
  inheritance, text style/fill changes, specified-slide text insertion and a
  3-5 node flowchart.
- Generic shell/script mutation remains hidden after ContentIR closes task
  discovery; the model sees typed office operations instead.

## Evidence boundary and next measurement

These changes are implementation improvements derived from existing
trajectories. They do not by themselves prove higher benchmark quality. The
next valid comparison is to run the same frozen tasks with Xiaopu and use the
official evaluator plus the already defined 0/1/2 process rubric. Existing
competitor trajectories must not be rewritten or treated as raw telemetry.
