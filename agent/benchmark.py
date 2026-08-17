"""Non-interactive benchmark adapter for containerized coding tasks."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
import sys
import time
from pathlib import Path
import shutil


def is_provider_unavailable(error_text: str) -> bool:
    """Return whether an exception string denotes an infrastructure outage."""
    lowered = error_text.lower()
    return any(
        marker in lowered
        for marker in ("apiconnectionerror", "connection error", "timeout", "timed out")
    )


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Baoyi in a benchmark workspace")
    parser.add_argument("task", nargs="*", help="task text; stdin is used when omitted")
    parser.add_argument("--workspace", required=True, help="isolated task workspace")
    parser.add_argument("--model")
    parser.add_argument("--max-steps", type=int, default=60)
    parser.add_argument("--max-tool-calls", type=int, default=240)
    parser.add_argument("--max-total-tokens", type=int, default=180000)
    parser.add_argument("--max-generated-output-tokens", type=int, default=4500)
    parser.add_argument("--controller-policy", choices=("direct", "always_verify", "evidence_only", "cegar_h"), default="cegar_h")
    parser.add_argument("--log", default=".baoyi/run.jsonl")
    parser.add_argument(
        "--bundle",
        help="optional directory to materialize a benchmark-ready run bundle",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    # Redirection on Windows often inherits a legacy GBK stream.  The agent
    # output is Unicode by contract, so benchmark launchers must not crash
    # after a successful run merely because the summary contains symbols.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")
    args = _arguments()
    workspace = Path(args.workspace).resolve()
    if not workspace.is_dir():
        print(f"workspace is not a directory: {workspace}", file=sys.stderr)
        return 2
    task = " ".join(args.task).strip() or sys.stdin.read().strip()
    if not task:
        print("task is empty", file=sys.stderr)
        return 2

    os.environ["WORKSPACE"] = str(workspace)
    os.environ["COMMAND_POLICY"] = "allow"
    os.environ["ISOLATED_BENCHMARK"] = "1"
    os.environ["STRICT_RUN_BUDGET"] = "1"
    os.environ["MAX_STEPS"] = str(args.max_steps)
    os.environ["MAX_TOOL_CALLS"] = str(args.max_tool_calls)
    os.environ["MAX_TOTAL_TOKENS"] = str(args.max_total_tokens)
    os.environ["MAX_GENERATED_OUTPUT_TOKENS"] = str(args.max_generated_output_tokens)
    # Benchmark runs must not spend budget retrying an unavailable provider.
    # Users can explicitly override this for a controlled robustness study.
    os.environ.setdefault("API_RETRIES", "0")

    from .harness import Harness
    from .redact import redact

    log_path = (workspace / args.log).resolve()
    try:
        log_path.relative_to(workspace)
    except ValueError:
        print("log path escapes workspace", file=sys.stderr)
        return 2
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_log = workspace / ".xiaopu/run.jsonl"
        if args.log == ".baoyi/run.jsonl" and not log_path.exists() and legacy_log.is_file():
            shutil.copy2(legacy_log, log_path)
    except Exception:
        pass
    started = time.time()

    def record(kind: str, payload: dict) -> None:
        event = {"time": time.time(), "kind": kind, **payload}
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(redact(json.dumps(event, ensure_ascii=False)) + "\n")

    harness = Harness(model=args.model, max_steps=args.max_steps, controller_policy=args.controller_policy)
    harness.attach_printer(
        lambda name, tool_args, output: record(
            "tool",
            {"name": name, "arguments": redact(tool_args[:4000]), "output": redact(output[:12000])},
        )
    )
    record("start", {"model": harness.llm.model, "task": task, "workspace": str(workspace), "controller_policy": args.controller_policy})
    try:
        answer = harness.run(task)
        status = "completed" if harness.state.final_summary else "stopped"
        code = 0 if status == "completed" else 1
    except Exception as exc:
        answer = f"{type(exc).__name__}: {exc}"
        # Provider outages are infrastructure diagnostics, not task failures.
        # Keep them explicit so a benchmark aggregator can exclude them from
        # success denominators without silently treating them as completions.
        unavailable = is_provider_unavailable(answer)
        status = "provider_unavailable" if unavailable else "error"
        code = 3 if unavailable else 1
    summary = {
        "status": status,
        "answer": answer,
        "tool_calls": harness.state.tool_calls,
        "total_tokens": harness.state.total_tokens,
        "input_tokens": harness.state.input_tokens,
        "generated_output_tokens": harness.state.generated_output_tokens,
        "provider_usage_authoritative": harness.state.provider_usage_authoritative,
        "changed_files": sorted(harness.state.changed_files),
        "evidence": [asdict(record) for record in harness.state.evidence],
        "budget_overrun": harness.state.budget_overrun,
        "elapsed_seconds": round(time.time() - started, 3),
        "policy_manifest": harness.policy_guard.manifest(),
        "usage_sources": {
            "input_tokens": "provider response usage",
            "generated_output_tokens": "provider response completion/output usage",
            "covered_local_tool_calls": "Harness dispatch count",
            "wall_seconds": "monotonic benchmark launcher elapsed time"
        },
    }
    record("finish", summary)
    if args.bundle:
        bundle = Path(args.bundle)
        if not bundle.is_absolute():
            bundle = workspace / bundle
        bundle = bundle.resolve()
        try:
            bundle.relative_to(workspace)
        except ValueError:
            print("bundle path escapes workspace", file=sys.stderr)
            return 2
        bundle.mkdir(parents=True, exist_ok=True)
        inputs = bundle / "input"
        inputs.mkdir(parents=True, exist_ok=True)
        (inputs / "instruction.md").write_text(task + "\n", encoding="utf-8")
        recorder = getattr(harness, "recorder", None)
        if recorder is not None and Path(recorder.steps_path).is_file():
            shutil.copy2(recorder.steps_path, bundle / "steps.jsonl")
        if not (bundle / "steps.jsonl").is_file():
            shutil.copy2(log_path, bundle / "events.jsonl")
        tool_rows = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("kind") == "tool":
                tool_rows.append(row)
        (bundle / "tool_calls.json").write_text(
            json.dumps(tool_rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (bundle / "run_result.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest = dict(getattr(recorder, "manifest", {}) or {})
        manifest.update({
            "schema": "baoyi-benchmark-run-bundle-v1",
            "bundle_root": str(bundle),
            "instruction": "input/instruction.md",
            "trace": "steps.jsonl" if (bundle / "steps.jsonl").is_file() else "events.jsonl",
            "tool_calls_path": "tool_calls.json",
            "run_result": "run_result.json",
            "evaluation_required": "evaluation.json",
            "output_required": "output.<ext> or output/",
        })
        (bundle / "run_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(redact(json.dumps(summary, ensure_ascii=False) if args.json else answer))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
