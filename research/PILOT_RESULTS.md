# Small pilot results

These are harness pilots, not official Terminal-Bench or SWE-bench scores.
All runs used DeepSeek through the configured OpenAI-compatible endpoint, Docker,
temperature 0, one attempt per task, and persisted raw JSON under
`workspace/pilot_*`.

The first five official SWE-bench Verified metadata records have now been
acquired separately; see `research/OFFICIAL_BENCHMARK_SAMPLE.md`. No official
score is claimed until their repositories and test environments are executed.

## Terminal-style pilot

Manifest `xiaopu-mini-v1`, 5 tasks, 20,000 total-token cap, 3,000 output cap:

- 3/5 completed with fresh verification evidence where applicable.
- 2/5 stopped at the budget boundary after mutating or inspecting state.
- Valid completed tasks included exact three-line file creation, read-only
  repository inspection, and safe workspace inspection.
- The two stopped tasks are counted as failures for the pilot; their artifacts
  are not silently promoted to success.

## SWE-style pilot

5 repository-navigation/documentation tasks, same 20,000-token cap:

- 3/5 completed.
- 2/5 stopped at the budget boundary.
- These are harness tasks, not official SWE-bench Verified issue instances;
  no official patch/test score is claimed.

## PPT pilot

PPT uses a predeclared 32,000-token total-context cap and 3,000 output cap
because slide tool schemas and serialized deck state are larger.

- 3-slide coffee deck: structural verification passed, but one run exceeded
  the cap during final completion; counted as stopped.
- 4-slide AI-agent-harness deck: completed successfully; structural verification
  and shape inspection passed, artifact was saved and reopened.
- Linux container rendering was unavailable because LibreOffice is not installed;
  Windows PowerPoint COM rendering is separately available but failed in the
  current non-interactive login session.

Follow-up with `xiaopu-ppt-render:mini` installed LibreOffice Impress and
Poppler. A model-driven 3-slide coffee task completed with fresh structural and
render evidence, producing a PPTX, PDF, three PNG slides, and a montage. The
montage was visually inspected for clipping, hierarchy, and alignment. This is
end-to-end PPT evidence, not a benchmark score.

## Interpretation

The pilot validates the end-to-end plumbing and exposes a real failure mode:
long tool histories can consume the context budget after the requested artifact
already exists. This motivates explicit context compaction and task-specific
budgeting. It is not evidence of superiority over Claude Code or Codex.
