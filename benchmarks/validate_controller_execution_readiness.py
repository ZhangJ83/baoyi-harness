"""Validate that the frozen controller protocol has a runnable, rendered execution path."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from benchmarks.run_real_controller_ablation import build_schedule
from benchmarks.validate_real_controller_ablation_protocol import validate as validate_protocol


def validate(root: Path, smoke_path: Path) -> dict:
    protocol_path = root / "benchmarks/real_controller_ablation_v1.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    protocol_result = validate_protocol(protocol, root)
    schedule = build_schedule(protocol)
    smoke = json.loads(smoke_path.read_text(encoding="utf-8")) if smoke_path.is_file() else {}
    checks = smoke.get("evaluation", {})
    runner = root / "benchmarks/run_real_controller_ablation.py"
    evaluator = root / "benchmarks/evaluate_real_controller_cell.py"
    renderer = root / "agent/tools/ppt_tools.py"
    valid = bool(
        protocol_result["valid"]
        and len(schedule) == 48
        and len({(task["id"], policy) for task, policy in schedule}) == 48
        and runner.is_file() and evaluator.is_file()
        and smoke.get("evaluator_sha256") == hashlib.sha256(evaluator.read_bytes()).hexdigest()
        and smoke.get("renderer_sha256") == hashlib.sha256(renderer.read_bytes()).hexdigest()
        and smoke.get("infrastructure_valid") is True
        and checks.get("pdf_complete") is True
        and checks.get("png_complete") is True
        and checks.get("fresh_evidence") is True
    )
    credential = bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    return {
        "schema": "real-controller-execution-readiness-v1",
        "valid": valid, "protocol_valid": protocol_result["valid"],
        "scheduled_cells": len(schedule), "unique_cells": len({(task["id"], policy) for task, policy in schedule}),
        "runner_present": runner.is_file(), "common_evaluator_present": evaluator.is_file(),
        "real_pdf_png_smoke": bool(smoke.get("infrastructure_valid") and checks.get("pdf_complete") and checks.get("png_complete") and checks.get("fresh_evidence")),
        "provider_credential_current_process": credential,
        "runnable_now": valid and credential,
        "claim_boundary": "execution readiness only; the smoke deck is excluded from causal results",
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--render-smoke", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    result = validate(a.root.resolve(), a.render_smoke.resolve())
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
