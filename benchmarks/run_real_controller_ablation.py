"""Run/resume the frozen 12-task x 4-policy real PPT controller ablation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from benchmarks.evaluate_real_controller_cell import evaluate
from benchmarks.validate_real_controller_ablation_protocol import validate as validate_protocol
from benchmarks.validate_real_controller_ablation_results import validate as validate_results
from agent.controller_policies import resolve_policy


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_schedule(protocol: dict, *, smoke: bool = False) -> list[tuple[dict, str]]:
    tasks = protocol["tasks"][:1] if smoke else protocol["tasks"]
    orders = protocol["order_control"]["orders"]
    return [(task, policy) for index, task in enumerate(tasks) for policy in orders[index % len(orders)]]


def _latest_summary(log_path: Path) -> dict:
    if not log_path.is_file():
        return {}
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return next((event for event in reversed(events) if event.get("kind") == "finish"), {})


def _artifact(root: Path, path: Path, absence_reason: str) -> dict:
    if not path.is_file():
        return {"present": False, "absence_reason": absence_reason}
    return {"present": True, "path": str(path.relative_to(root)).replace("\\", "/"), "sha256": digest(path)}


def _prompt(task: dict, input_name: str | None) -> str:
    facts = "\n".join(f"- {value}" for value in task["facts"])
    required = ", ".join(task["required_text"])
    input_instruction = f"Open and modify `{input_name}`; do not overwrite it. " if input_name else "Create the deck from scratch. "
    return (
        f"{task['prompt']}\n\nFrozen facts:\n{facts}\n\n"
        f"Required visible text includes: {required}. Slide count must be {task['min_slides']}..{task['max_slides']}.\n"
        f"{input_instruction}Save the final artifact exactly as `deck.pptx`. "
        "Before finishing, follow the active controller intervention. The common evaluator runs after the agent and must not be anticipated or bypassed."
    )


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_cell(root: Path, protocol: dict, source_tasks: dict[str, dict], run_root: Path, task: dict, policy: str, timeout: int) -> dict:
    cell_root = run_root / task["id"] / policy
    cell_root.mkdir(parents=True, exist_ok=False)
    full_task = source_tasks[task["id"]]
    task_path = cell_root / "task.json"
    _write_json(task_path, full_task)
    input_name = None
    if full_task.get("input"):
        input_name = "input.pptx"
        shutil.copy2(root / full_task["input"]["path"], cell_root / input_name)
    command = [
        sys.executable, "-m", "agent.benchmark", "--workspace", str(cell_root),
        "--model", protocol["model"]["name"], "--max-steps", str(resolve_policy(policy).max_model_steps), "--max-tool-calls", "60",
        "--max-total-tokens", "180000", "--max-generated-output-tokens", "4500",
        "--controller-policy", policy, "--json", _prompt(full_task, input_name),
    ]
    started = time.monotonic()
    timed_out = False
    try:
        process = subprocess.run(command, cwd=root, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=timeout, env=os.environ.copy())
        returncode = process.returncode
        # Under a sandbox that forbids named pipes, capture_output can leave
        # stdout/stderr as None even though the child ran and wrote its own
        # .xiaopu/run.jsonl ledger. Treat that as empty; the ledger is the
        # authoritative record anyway.
        stdout, stderr = process.stdout or "", process.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
    elapsed = time.monotonic() - started
    (cell_root / "launcher.stdout.txt").write_text(stdout, encoding="utf-8")
    (cell_root / "launcher.stderr.txt").write_text(stderr, encoding="utf-8")
    summary = _latest_summary(cell_root / ".xiaopu/run.jsonl")
    evaluation = evaluate(cell_root, full_task)
    usage = {
        "authoritative": summary.get("provider_usage_authoritative") is True and bool(summary.get("usage_sources")),
        "generated_output_tokens": summary.get("generated_output_tokens", 0),
        "covered_local_tool_calls": summary.get("tool_calls", 0),
        "wall_seconds": summary.get("elapsed_seconds", round(elapsed, 3)),
    }
    _write_json(cell_root / "usage_ledger.json", {"usage": usage, "sources": summary.get("usage_sources", {})})
    _write_json(cell_root / "timing.json", {"launcher_elapsed_seconds": elapsed, "timed_out": timed_out, "returncode": returncode})
    paths = {
        "pptx": cell_root / "deck.pptx",
        "pdf": cell_root / "common_evaluation/rendered/deck.pdf",
        "slide_pngs": cell_root / "common_evaluation/slide_pngs_manifest.json",
        "structural_report": cell_root / "common_evaluation/structural_report.txt",
        "pixel_audit": cell_root / "common_evaluation/pixel_audit.txt",
        "trace": cell_root / ".xiaopu/run.jsonl",
        "usage_ledger": cell_root / "usage_ledger.json",
        "timing": cell_root / "timing.json",
    }
    infra = evaluation["infrastructure_valid"] and not timed_out and summary.get("status") != "provider_unavailable"
    return {
        "task_id": task["id"], "policy": policy, "infrastructure_valid": infra,
        "policy_manifest": summary.get("policy_manifest", {}),
        "usage": usage,
        "artifacts": {name: _artifact(run_root, path, f"not produced; status={summary.get('status','missing')}") for name, path in paths.items()},
        "evaluation": evaluation["evaluation"], "artifact_success": evaluation["artifact_success"],
        "runner": {"returncode": returncode, "status": summary.get("status", "missing"), "errors": evaluation["errors"]},
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--protocol", type=Path, default=Path("benchmarks/real_controller_ablation_v1.json"))
    p.add_argument("--run-root", type=Path, required=True)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--smoke", action="store_true")
    p.add_argument("--acknowledge-model-cost", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--timeout", type=int, default=330)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    protocol_path = (root / args.protocol).resolve() if not args.protocol.is_absolute() else args.protocol.resolve()
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol_check = validate_protocol(protocol, root)
    if not protocol_check["valid"]:
        raise SystemExit("protocol invalid: " + ", ".join(protocol_check["errors"]))
    source = json.loads((root / protocol["task_source"]["path"]).read_text(encoding="utf-8"))
    source_tasks = {task["id"]: task for task in source["tasks"]}
    schedule = build_schedule(protocol, smoke=args.smoke)
    if args.dry_run:
        print(json.dumps({"schema":"real-controller-dry-run-v1", "cells": [{"task_id":t["id"], "policy":p} for t, p in schedule], "n_cells":len(schedule)}, indent=2))
        return 0
    if not args.acknowledge_model_cost:
        raise SystemExit("live run refused without --acknowledge-model-cost")
    if not (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        raise SystemExit("live run refused: no provider credential in current process")
    run_root = args.run_root.resolve()
    run_root.mkdir(parents=True, exist_ok=args.resume)
    run_manifest = {
        "schema": "real-controller-run-manifest-v1",
        "protocol_sha256": digest(protocol_path),
        "task_source_sha256": digest(root / protocol["task_source"]["path"]),
        "runner_sha256": digest(Path(__file__)),
        "model": protocol["model"], "budget": protocol["budget"],
        "smoke": args.smoke,
    }
    manifest_path = run_root / "run_manifest.json"
    if args.resume:
        if not manifest_path.is_file() or json.loads(manifest_path.read_text(encoding="utf-8")) != run_manifest:
            raise SystemExit("resume refused: run manifest missing or protocol/runtime drifted")
    else:
        _write_json(manifest_path, run_manifest)
    cells = []
    for task, policy in schedule:
        record_path = run_root / task["id"] / policy / "cell_record.json"
        if args.resume and record_path.is_file():
            cell = json.loads(record_path.read_text(encoding="utf-8"))
        else:
            if record_path.parent.exists():
                raise SystemExit(f"incomplete existing cell refuses overwrite: {record_path.parent}")
            cell = run_cell(root, protocol, source_tasks, run_root, task, policy, args.timeout)
            _write_json(record_path, cell)
        cells.append(cell)
        _write_json(run_root / "raw_cells.partial.json", {"cells": cells})
    raw = {"schema":"real-controller-ablation-raw-v1", "protocol_sha256":digest(protocol_path), "protocol_frozen_before_run":True, "cells":cells}
    _write_json(run_root / "raw_cells.json", raw)
    if args.smoke:
        smoke = {"schema":"real-controller-live-smoke-v1", "valid":all(cell["infrastructure_valid"] for cell in cells), "n_cells":len(cells), "policies":sorted({cell["policy"] for cell in cells})}
        _write_json(run_root / "smoke_result.json", smoke)
        print(json.dumps(smoke))
        return 0 if smoke["valid"] else 1
    result = validate_results(protocol, digest(protocol_path), raw, run_root)
    _write_json(run_root / "real_controller_ablation.json", result)
    print(json.dumps({"run_root":str(run_root), "valid":result["valid"], "n_cells":len(cells)}))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
