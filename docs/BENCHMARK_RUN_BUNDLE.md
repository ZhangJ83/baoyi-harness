# Minimal benchmark run bundle

The benchmark runner and the evaluator may evolve independently.  Their
handoff is a small, score-neutral directory contract:

```text
run/
├── input/                 # non-empty task inputs
├── output.<ext>           # or a non-empty output/ directory
├── trajectory.md          # or steps.jsonl/events.jsonl/trajectory/events
├── tool_calls.json        # .jsonl is also accepted
├── evaluation.json        # evaluator-owned scores and judgments
├── run_manifest.json      # manifest.json/artifact_manifest.json also accepted
└── screenshots/           # optional
```

Validate a bundle without running an agent or evaluator:

```powershell
xiaopu-validate-run E:\path\to\run
```

Or from a source checkout:

```powershell
python -m benchmarks.validate_run_bundle E:\path\to\run
```

To let the benchmark adapter create the recorder-owned part of the bundle:

```powershell
xiaopu-bench --workspace E:\path\to\task --bundle run --json "your task"
```

This writes `input/instruction.md`, the redacted execution trace,
`tool_calls.json`, `run_result.json`, and `run_manifest.json`. Your benchmark
driver/evaluator then places its immutable task inputs or references, final
`output.<ext>` (or `output/`), and evaluator-owned `evaluation.json` in that
directory. Xiaopu deliberately does not synthesize a score for itself.

Exit code `0` means the bundle is complete. Exit code `2` means it is
incomplete or malformed; the JSON output lists every missing or invalid
component in one pass. Use `--out validation.json` to persist the report.

This validator does **not** compute, normalize, reinterpret, or change any
field in `evaluation.json`. It checks packaging only. If a manifest contains
the existing evidence-manifest `files` table, declared byte sizes and SHA-256
digests are verified using the existing manifest digest implementation.
