"""Validate three discardable v3 live-smoke runs without producing a score."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


SYSTEMS = ("xiaopu", "claude_code", "codex")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate(paths: dict[str, Path], protocol: dict, *, credential_present: bool) -> dict:
    failures: list[dict] = []
    systems: dict[str, dict] = {}
    caps = protocol["hard_envelope"]
    for name in SYSTEMS:
        results_path = paths[name]
        if not results_path.is_file():
            systems[name] = {"valid": False, "failures": ["missing_results"]}
            failures.append({"system": name, "reason": "missing_results"})
            continue
        payload = load(results_path)
        rows = payload.get("results", [])
        local: list[str] = []
        if len(rows) != 1:
            local.append("smoke_must_contain_exactly_one_trial")
        manifest_path = results_path.parent / "run_manifest_v3.json"
        manifest = load(manifest_path) if manifest_path.is_file() else {}
        if manifest.get("non_scored_smoke") is not True:
            local.append("run_not_marked_non_scored_smoke")
        ledger: dict = {}
        if len(rows) == 1:
            row = rows[0]
            ledger_path = (
                results_path.parent / str(row.get("task_id")) / str(row.get("trial_name"))
                / "agent-logs" / "budget_ledger_v3.json"
            )
            ledger = load(ledger_path) if ledger_path.is_file() else {}
            if not ledger:
                local.append("missing_budget_ledger_v3")
        if ledger:
            if ledger.get("system") != name or ledger.get("within_budget") is not True:
                local.append("ledger_not_eligible")
            ledger_caps = ledger.get("caps", {})
            expected_caps = {
                "max_cumulative_output_tokens": caps["max_cumulative_output_tokens"],
                "max_covered_local_tool_calls": caps["max_covered_local_tool_calls"],
                "max_agent_wall_seconds": caps["max_agent_wall_seconds"],
            }
            if any(ledger_caps.get(key) != value for key, value in expected_caps.items()):
                local.append("cap_mismatch")
            if name in {"claude_code", "codex"}:
                if ledger.get("gateway_output_matches_cli_stream") is not True:
                    local.append("gateway_not_live_verified")
                if not isinstance(ledger.get("covered_local_tool_calls"), int) or ledger.get("covered_local_tool_calls") < 1:
                    local.append("tool_hook_not_observed")
                if ledger.get("parse_errors") != [] or ledger.get("gateway_violations") != []:
                    local.append("competitor_audit_errors")
        for reason in local:
            failures.append({"system": name, "reason": reason})
        systems[name] = {
            "valid": not local,
            "failures": local,
            "covered_local_tool_calls": ledger.get("covered_local_tool_calls"),
            "output_tokens": ledger.get("output_tokens"),
        }
    smoke_valid = not failures and all(name in systems for name in SYSTEMS)
    return {
        "schema": "matched-v3-live-smoke-validation-v1",
        "smoke_valid": smoke_valid,
        "provider_credential_current_process": credential_present,
        "ready_for_confirmatory_run_now": smoke_valid and credential_present,
        "systems": systems,
        "failures": failures,
        "claim_boundary": "non-scored transport/hook smoke only; contains no performance evidence",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xiaopu", type=Path, required=True)
    parser.add_argument("--claude-code", type=Path, required=True)
    parser.add_argument("--codex", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=Path("benchmarks/matched_protocol_v3.json"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    credential = bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    result = validate(
        {"xiaopu": args.xiaopu, "claude_code": args.claude_code, "codex": args.codex},
        load(args.protocol),
        credential_present=credential,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["smoke_valid"] else 2)


if __name__ == "__main__":
    main()
