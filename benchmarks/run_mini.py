"""Run a frozen, small, auditable harness pilot.

The runner intentionally does not compare against competitors itself. It emits
the same task and result schema for each harness so an external driver can run
Claude Code/Codex under matched settings.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["terminal_bench", "swe_bench_verified", "pptbench"], required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--agent-module", default="agent.benchmark", help="module used to execute each task")
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--max-tool-calls", type=int, default=None)
    parser.add_argument("--max-total-tokens", type=int, default=None)
    parser.add_argument("--max-output-tokens", type=int, default=None)
    parser.add_argument(
        "--continue-on-provider-unavailable",
        action="store_true",
        help="keep probing tasks after the first provider outage (costs more time)",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "benchmarks" / "mini_tasks.json").read_text(encoding="utf-8"))
    tasks = manifest["tasks"][args.suite][: args.limit]
    protocol = manifest["protocol"]
    override = manifest.get("suite_overrides", {}).get(args.suite, {})
    max_steps = args.max_steps or override.get("max_steps", protocol["max_steps"])
    max_tool_calls = args.max_tool_calls or override.get("max_tool_calls", protocol["max_tool_calls"])
    max_total_tokens = args.max_total_tokens or override.get("max_total_tokens", protocol["max_total_tokens"])
    max_output_tokens = args.max_output_tokens or override.get("max_output_tokens", protocol.get("max_output_tokens", 3000))
    args.workspace.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for task in tasks:
        task_dir = args.workspace / task["id"]
        task_dir.mkdir(parents=True, exist_ok=True)
        started = time.time()
        command = [
            sys.executable, "-m", args.agent_module, task["prompt"],
            "--workspace", str(task_dir), "--max-steps", str(max_steps),
            "--max-tool-calls", str(max_tool_calls), "--max-total-tokens", str(max_total_tokens), "--json",
        ]
        # Per-response cap is passed through the environment so the adapter and
        # the model client share one auditable budget contract.
        task_env = os.environ.copy()
        task_env["OPENAI_MAX_TOKENS"] = str(max_output_tokens)
        completed = subprocess.run(command, cwd=root, text=True, capture_output=True, env=task_env)
        rows.append({
            "suite": args.suite,
            "task_id": task["id"],
            "kind": task["kind"],
            "returncode": completed.returncode,
            "elapsed_seconds": round(time.time() - started, 3),
            "stdout": completed.stdout[-20000:],
            "stderr": completed.stderr[-8000:],
        })
        if not args.continue_on_provider_unavailable:
            try:
                payload = json.loads(completed.stdout.strip().splitlines()[-1])
            except (json.JSONDecodeError, IndexError):
                payload = {}
            if payload.get("status") == "provider_unavailable":
                break
    args.out.write_text(json.dumps({"manifest": manifest["version"], "suite": args.suite, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    unavailable = 0
    for row in rows:
        try:
            payload = json.loads(row["stdout"].strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            payload = {}
        unavailable += payload.get("status") == "provider_unavailable"
    process_passed = sum(row["returncode"] == 0 for row in rows)
    print(json.dumps({
        "suite": args.suite,
        "tasks": len(rows),
        "passed_process": process_passed,
        "provider_unavailable": unavailable,
        "out": str(args.out),
    }, ensure_ascii=False))
    if rows and unavailable == len(rows):
        return 3
    return 0 if all(row["returncode"] == 0 for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
