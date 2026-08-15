"""Validate that PPTBench v2 is executable without treating readiness as results."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(root: Path, protocol_validation_path: Path, manifest_path: Path, render_smoke_path: Path) -> dict:
    protocol_path = root / "benchmarks/pptbench_model_eval_v2.json"
    protocol = load(protocol_path)
    protocol_validation = load(protocol_validation_path)
    manifest = load(manifest_path)
    render = load(render_smoke_path)
    expected = {(system, task["id"]) for system in protocol.get("systems", []) for task in protocol.get("tasks", [])}
    observed_rows = manifest.get("cells", [])
    observed = {(row.get("system"), row.get("task_id")) for row in observed_rows}
    execution = protocol.get("execution", {})
    evaluation = render.get("evaluation", {})
    errors = []
    if not (protocol_validation.get("valid") is True and protocol_validation.get("assets_ready") is True):
        errors.append("protocol_validation_not_ready")
    if manifest.get("protocol_sha256") != sha256(protocol_path):
        errors.append("dry_run_protocol_hash_mismatch")
    runner = root / execution.get("runner", {}).get("path", "")
    if not runner.is_file() or manifest.get("runner_sha256") != sha256(runner) or execution.get("runner", {}).get("sha256") != sha256(runner):
        errors.append("runner_hash_mismatch")
    if manifest.get("dry_run") is not True or len(observed_rows) != 36 or observed != expected:
        errors.append("dry_run_36_cell_schedule_invalid")
    if manifest.get("model") != protocol.get("model") or manifest.get("budget") != protocol.get("budget"):
        errors.append("model_or_budget_drift")
    if manifest.get("observed_cli_versions") != execution.get("cli_versions"):
        errors.append("cli_version_drift")
    if not (render.get("infrastructure_valid") is True and evaluation.get("pdf_complete") is True
            and evaluation.get("png_complete") is True and evaluation.get("fresh_evidence") is True):
        errors.append("real_powerpoint_render_smoke_invalid")
    if render.get("renderer_sha256") != execution.get("xiaopu_ppt_tools", {}).get("sha256"):
        errors.append("render_smoke_runtime_hash_mismatch")
    credential = bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    valid = not errors
    return {
        "schema": "pptbench-v2-execution-readiness",
        "valid": valid,
        "protocol_valid": protocol_validation.get("valid") is True,
        "scheduled_cells": len(observed_rows),
        "unique_cells": len(observed),
        "cli_versions_match": manifest.get("observed_cli_versions") == execution.get("cli_versions"),
        "real_powerpoint_pdf_png_smoke": "real_powerpoint_render_smoke_invalid" not in errors,
        "runtime_hashes_match": not any("hash_mismatch" in error for error in errors),
        "provider_credential_current_process": credential,
        "runnable_now": valid and credential,
        "errors": errors,
        "claim_boundary": "execution readiness only; no model decks, blind scores, or performance evidence",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--protocol-validation", type=Path, required=True)
    parser.add_argument("--run-manifest", type=Path, required=True)
    parser.add_argument("--render-smoke", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.root.resolve(), args.protocol_validation.resolve(), args.run_manifest.resolve(), args.render_smoke.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
