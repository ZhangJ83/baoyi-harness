"""Validate the prospective v3 protocol without confusing validity with readiness."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_HARD_CAPS = {
    "max_cumulative_output_tokens",
    "max_covered_local_tool_calls",
    "max_agent_wall_seconds",
}


def validate(protocol: dict, task_manifest: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if protocol.get("status") != "prospective_not_run":
        errors.append("protocol status must remain prospective_not_run before execution")
    if not protocol.get("anti_harking_boundary"):
        errors.append("anti-harking boundary is missing")
    benchmark = protocol.get("benchmark", {})
    task_ids = task_manifest.get("task_ids", [])
    if benchmark.get("n_tasks") != len(task_ids) or len(task_ids) < 18:
        errors.append("task manifest does not satisfy the preregistered minimum n=18")
    if len(task_ids) != len(set(task_ids)):
        errors.append("task manifest contains duplicates")
    envelope = protocol.get("hard_envelope", {})
    for key in REQUIRED_HARD_CAPS:
        value = envelope.get(key)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            errors.append(f"invalid hard envelope field: {key}")
    if "hosted" not in str(envelope.get("covered_tool_surface", "")):
        warnings.append("covered tool surface does not explicitly discuss hosted-tool exclusion")
    readiness = protocol.get("readiness_gates", {})
    required_ready = {
        "tool_hook_unit_tests",
        "tool_hook_live_smoke",
        "gateway_accounting_core_unit_tests",
        "gateway_unit_tests",
        "gateway_live_smoke",
        "provider_credential_current_process",
    }
    missing_readiness = sorted(required_ready - readiness.keys())
    if missing_readiness:
        errors.append(f"missing readiness gates: {', '.join(missing_readiness)}")
    derived_ready = not errors and all(readiness.get(key) is True for key in required_ready)
    if readiness.get("ready_for_confirmatory_run") is not derived_ready:
        errors.append("ready_for_confirmatory_run does not equal the conjunction of readiness gates")
    if envelope.get("gateway") == "pending implementation":
        warnings.append("HTTP gateway transport is not implemented")
    return {
        "schema": "matched-terminal-protocol-v3-validation",
        "valid": not errors,
        "ready_for_confirmatory_run": derived_ready,
        "errors": errors,
        "warnings": warnings,
        "task_count": len(task_ids),
        "boundary": "protocol validity is not execution readiness or performance evidence",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=Path("benchmarks/matched_protocol_v3.json"))
    parser.add_argument("--tasks", type=Path, default=Path("research/matched_terminal_slice_v1.json"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(args.protocol.read_text(encoding="utf-8-sig"))
    tasks = json.loads(args.tasks.read_text(encoding="utf-8-sig"))
    result = validate(protocol, tasks)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
