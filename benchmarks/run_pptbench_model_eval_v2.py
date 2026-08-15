"""Resumable, fixed-budget launcher for the frozen 36-deck PPTBench v2 run."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from agent.competitor_stream_ledger import normalize
from benchmarks.evaluate_real_controller_cell import evaluate
from benchmarks.prepare_pptbench_blind_review import prepare
from benchmarks.validate_model_generated_ppt_eval import recompute_deck_checks, recompute_pixel_checks


ROOT = Path(__file__).resolve().parents[1]
SYSTEMS = ("xiaopu", "claude_code", "codex")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def observed_cli_versions(systems: list[str], *, allow_missing: bool = False) -> dict[str, str]:
    versions = {"xiaopu": "repository-runtime"}
    commands = {
        "claude_code": [shutil.which("claude.cmd") or shutil.which("claude"), "--version"],
        "codex": [shutil.which("codex.cmd") or shutil.which("codex"), "--version"],
    }
    for system in systems:
        if system == "xiaopu":
            continue
        command = commands[system]
        if not command[0]:
            if allow_missing:
                versions[system] = "not-installed"
                continue
            raise RuntimeError(f"{system} executable not found")
        result = subprocess.run(command, capture_output=True, text=True, timeout=20)
        if result.returncode != 0:
            if allow_missing:
                versions[system] = "not-installed"
                continue
            raise RuntimeError(f"{system} --version failed")
        versions[system] = (result.stdout or result.stderr).strip()
    return versions


def build_prompt(task: dict, *, has_input: bool) -> str:
    input_instruction = (
        "Open input.pptx and edit it; do not replace the subject with a different deck."
        if has_input else "Create the presentation from scratch."
    )
    facts = "\n".join(f"- {value}" for value in task["facts"])
    required = ", ".join(task["required_text"])
    return f"""You are running one frozen PPTBench v2 evaluation cell.
{input_instruction}

Task: {task['prompt']}
Audience: {task['audience']}
Deck job: {task['deck_job']}
Allowed facts (do not invent facts):
{facts}

Hard artifact contract:
- Save the final artifact as deck.pptx in the current workspace.
- Produce {task['min_slides']} to {task['max_slides']} slides and include: {required}.
- Use a 16:9 layout, one audience-facing claim per slide, no planning instructions in visible copy.
- Minimum explicit font sizes: deck title 50 pt, slide titles 35 pt, subheads 24 pt, body 16 pt.
- No unintended text overlap, overflow, empty placeholders, or shapes outside slide bounds.
- Every slide must contain a speaker-notes block beginning exactly with [Sources].
- Use [Sources] Internal evaluation task packet when the only source is this task packet.
- Inspect the saved deck before finishing. Do not write system/vendor identity into visible slide text.
"""


def _hook_settings(state: Path, max_tools: int) -> dict:
    command = f'"{sys.executable}" -m agent.tool_budget_hook --state "{state}" --max-tool-calls {max_tools}'
    return {
        "hooks": {
            "PreToolUse": [{"matcher": ".*", "hooks": [{"type": "command", "command": command, "timeout": 10}]}]
        }
    }


def prepare_cell(cell: Path, task: dict) -> None:
    cell.mkdir(parents=True, exist_ok=True)
    write_json(cell / "task.json", task)
    (cell / "PROMPT.md").write_text(build_prompt(task, has_input=task.get("input") is not None), encoding="utf-8")
    source = task.get("input")
    if source:
        input_path = ROOT / source["path"]
        if sha256(input_path) != source["sha256"]:
            raise RuntimeError(f"input hash drift: {task['id']}")
        shutil.copy2(input_path, cell / "input.pptx")


def _competitor_command(system: str, cell: Path, protocol: dict, prompt: str) -> tuple[list[str], dict]:
    budget = protocol["budget"]
    logs = cell / "runner_logs"
    logs.mkdir(parents=True, exist_ok=True)
    tool_state = logs / "tool_budget_hook.json"
    gateway_state = logs / "generation_budget_gateway.json"
    stream = logs / "cli_stream.jsonl"
    timing = logs / "timing.json"
    if system == "claude_code":
        executable = shutil.which("claude.cmd") or shutil.which("claude")
        if not executable:
            raise RuntimeError("Claude Code executable not found")
        settings = cell / "claude_settings.json"
        write_json(settings, _hook_settings(tool_state, budget["max_covered_local_tool_calls"]))
        child = [
            executable, "--verbose", "--output-format", "stream-json", "--print", prompt,
            "--model", protocol["model"], "--settings", str(settings),
            "--allowedTools", "Bash,Edit,Write,Read,Glob,Grep,LS",
            "--permission-mode", "bypassPermissions", "--no-session-persistence",
        ]
        upstream = "https://api.deepseek.com/anthropic"
        extra_env = {"ANTHROPIC_MODEL": protocol["model"]}
    elif system == "codex":
        executable = shutil.which("codex.cmd") or shutil.which("codex")
        if not executable:
            raise RuntimeError("Codex executable not found")
        codex_home = cell / ".codex_eval"
        codex_home.mkdir(parents=True, exist_ok=True)
        write_json(codex_home / "hooks.json", _hook_settings(tool_state, budget["max_covered_local_tool_calls"]))
        (codex_home / "config.toml").write_text(
            'model = "deepseek-v4-flash"\nmodel_provider = "xiaopu_gateway"\n'
            '[model_providers.xiaopu_gateway]\nname = "Xiaopu Budget Gateway"\n'
            'base_url = "http://127.0.0.1:8787"\nwire_api = "responses"\n'
            'env_key = "OPENAI_API_KEY"\n[features]\nhooks = true\n',
            encoding="utf-8",
        )
        child = [
            executable, "exec", "--sandbox", "workspace-write", "--skip-git-repo-check",
            "--dangerously-bypass-hook-trust", "--json", "--model", protocol["model"],
            "--ephemeral", "-C", str(cell), "--", prompt,
        ]
        upstream = "https://api.deepseek.com"
        extra_env = {"CODEX_HOME": str(codex_home)}
    else:
        raise ValueError(system)
    command = [
        sys.executable, "-m", "agent.budgeted_cli_runner",
        "--upstream-base", upstream, "--gateway-state", str(gateway_state),
        "--stream-log", str(stream), "--timing", str(timing),
        "--output-cap", str(budget["max_generated_output_tokens"]),
        "--wall-seconds", str(budget["max_agent_wall_seconds"]), "--", *child,
    ]
    return command, extra_env


def command_for(system: str, cell: Path, protocol: dict, prompt: str) -> tuple[list[str], dict]:
    if system != "xiaopu":
        return _competitor_command(system, cell, protocol, prompt)
    budget = protocol["budget"]
    return ([
        sys.executable, "-m", "agent.benchmark", "--workspace", str(cell),
        "--model", protocol["model"], "--max-steps", "50",
        "--max-tool-calls", str(budget["max_covered_local_tool_calls"]),
        "--max-generated-output-tokens", str(budget["max_generated_output_tokens"]),
        "--controller-policy", "cegar_h", "--json", prompt,
    ], {})


def budget_ledger(system: str, cell: Path, protocol: dict, returncode: int) -> dict:
    budget = protocol["budget"]
    if system == "xiaopu":
        events = []
        log = cell / ".xiaopu" / "run.jsonl"
        if log.is_file():
            events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        finish = next((event for event in reversed(events) if event.get("kind") == "finish"), {})
        output = finish.get("generated_output_tokens")
        tools = finish.get("tool_calls")
        wall = finish.get("elapsed_seconds")
        within = bool(
            returncode == 0 and finish.get("status") == "completed"
            and finish.get("provider_usage_authoritative") is True
            and isinstance(output, int) and output <= budget["max_generated_output_tokens"]
            and isinstance(tools, int) and tools <= budget["max_covered_local_tool_calls"]
            and isinstance(wall, (int, float)) and wall <= budget["max_agent_wall_seconds"] + 1
            and finish.get("budget_overrun") is not True
        )
        return {"system": system, "input_tokens": finish.get("input_tokens"), "output_tokens": output,
                "covered_local_tool_calls": tools, "wall_seconds": wall, "provider_usage_authoritative": finish.get("provider_usage_authoritative"),
                "returncode": returncode, "within_budget": within, "source": "xiaopu provider usage and Harness dispatch ledger"}
    logs = cell / "runner_logs"
    stream = logs / "cli_stream.jsonl"
    normalized = normalize(system, stream.read_text(encoding="utf-8").splitlines()) if stream.is_file() else {}
    gateway = json.loads((logs / "generation_budget_gateway.json").read_text(encoding="utf-8")) if (logs / "generation_budget_gateway.json").is_file() else {}
    tools = json.loads((logs / "tool_budget_hook.json").read_text(encoding="utf-8")) if (logs / "tool_budget_hook.json").is_file() else {}
    timing = json.loads((logs / "timing.json").read_text(encoding="utf-8")) if (logs / "timing.json").is_file() else {}
    output = gateway.get("committed_output_tokens")
    allowed = len(tools.get("allowed", []))
    wall = timing.get("wall_seconds")
    within = bool(
        returncode == 0 and normalized.get("final_event_seen") is True and not normalized.get("parse_errors")
        and isinstance(output, int) and output == normalized.get("output_tokens")
        and output <= budget["max_generated_output_tokens"] and allowed <= budget["max_covered_local_tool_calls"]
        and isinstance(wall, (int, float)) and wall <= budget["max_agent_wall_seconds"] + 1
        and timing.get("timed_out") is False and not gateway.get("violations")
    )
    return {"system": system, "input_tokens": normalized.get("input_tokens"), "output_tokens": output,
            "covered_local_tool_calls": allowed, "wall_seconds": wall, "provider_usage_authoritative": isinstance(output, int),
            "returncode": returncode, "within_budget": within, "stream": normalized,
            "gateway_violations": gateway.get("violations", []), "source": "budget gateway, PreToolUse hook, and CLI JSON stream"}


def finalize_cell(system: str, cell: Path, task: dict, protocol_path: Path, ledger: dict) -> dict:
    deck = cell / "deck.pptx"
    if not deck.is_file():
        return {"cell_complete": False, "failure": "missing_deck", "budget": ledger}
    common = evaluate(cell, task, "deck.pptx")
    rendered = cell / "common_evaluation" / "rendered"
    pdf = rendered / "deck.pdf"
    montage = rendered / "montage.png"
    pngs = sorted(path for path in rendered.glob("*.png") if path.name.lower() != "montage.png")
    slides = cell / "slides"
    slides.mkdir(exist_ok=True)
    for stale in slides.glob("*.png"):
        stale.unlink()
    if pdf.is_file():
        shutil.copy2(pdf, cell / "deck.pdf")
    if montage.is_file():
        shutil.copy2(montage, cell / "montage.png")
    for index, path in enumerate(pngs, 1):
        shutil.copy2(path, slides / f"slide-{index:03d}.png")
    structure = recompute_deck_checks(deck, task)
    pixels = recompute_pixel_checks(sorted(slides.glob("*.png")), structure["slide_count"])
    write_json(cell / "structural_report.json", structure)
    write_json(cell / "pixel_audit.json", pixels)
    complete = bool(ledger.get("within_budget") and structure["valid"] and pixels["pass"] and common["infrastructure_valid"] and pdf.is_file() and montage.is_file())
    trace = {
        "schema": "pptbench-v2-generation-trace", "model_generated": True,
        "system": system, "task_id": task["id"], "model": "deepseek-v4-flash", "protocol_sha256": sha256(protocol_path),
        "completed_at": datetime.now(timezone.utc).isoformat(), "budget": ledger,
        "independent_structure_valid": structure["valid"], "independent_pixel_valid": pixels["pass"],
        "common_evaluator_infrastructure_valid": common["infrastructure_valid"], "cell_complete": complete,
    }
    write_json(cell / "generation_trace.json", trace)
    return trace


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=ROOT / "benchmarks/pptbench_model_eval_v2.json")
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--system", action="append", choices=SYSTEMS)
    parser.add_argument("--task-id", action="append")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--acknowledge-live-cost", action="store_true")
    args = parser.parse_args()
    protocol_path = args.protocol.resolve()
    protocol = json.loads(protocol_path.read_text(encoding="utf-8-sig"))
    systems = args.system or list(SYSTEMS)
    expected_versions = protocol.get("execution", {}).get("cli_versions", {})
    observed_versions = observed_cli_versions(systems, allow_missing=args.dry_run)
    if not args.dry_run:
        for system in systems:
            if expected_versions and observed_versions.get(system) != expected_versions.get(system):
                raise SystemExit(f"{system} version drift: expected {expected_versions.get(system)!r}, observed {observed_versions.get(system)!r}")
    tasks = [task for task in protocol["tasks"] if not args.task_id or task["id"] in set(args.task_id)]
    if args.task_id and len(tasks) != len(set(args.task_id)):
        raise SystemExit("unknown or duplicate task id")
    if not args.dry_run and not args.acknowledge_live_cost:
        raise SystemExit("live model run refused without --acknowledge-live-cost")
    credential = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not args.dry_run and not credential:
        raise SystemExit("no provider credential in current process; secret is never read from a file or persisted")
    run_root = args.run_root.resolve()
    if run_root.exists() and any(run_root.iterdir()) and not args.resume:
        raise SystemExit("run root is non-empty; use a new path or explicit --resume")
    run_root.mkdir(parents=True, exist_ok=True)
    cells = [{"system": system, "task_id": task["id"]} for task in tasks for system in systems]
    manifest = {
        "schema": "pptbench-v2-run-manifest", "protocol_sha256": sha256(protocol_path),
        "runner_sha256": sha256(Path(__file__)), "model": protocol["model"], "budget": protocol["budget"],
        "observed_cli_versions": observed_versions,
        "systems": systems, "task_ids": [task["id"] for task in tasks], "cells": cells,
        "dry_run": args.dry_run, "resume": args.resume,
        "claim_boundary": "run scheduling and artifact execution; no performance claim",
    }
    write_json(run_root / "run_manifest.json", manifest)
    if args.dry_run:
        print(json.dumps(manifest, ensure_ascii=False))
        return 0
    base_env = dict(os.environ)
    base_env.update({"PYTHONPATH": str(ROOT), "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
                     "DEEPSEEK_API_KEY": credential, "OPENAI_API_KEY": credential, "ANTHROPIC_API_KEY": credential})
    failures = []
    for task in tasks:
        for system in systems:
            cell = run_root / "raw" / system / task["id"]
            trace_path = cell / "generation_trace.json"
            if args.resume and trace_path.is_file() and json.loads(trace_path.read_text(encoding="utf-8")).get("cell_complete") is True:
                continue
            prepare_cell(cell, task)
            prompt = (cell / "PROMPT.md").read_text(encoding="utf-8")
            command, extra_env = command_for(system, cell, protocol, prompt)
            started = time.time()
            completed = subprocess.run(command, cwd=cell, env={**base_env, **extra_env}, timeout=protocol["budget"]["max_agent_wall_seconds"] + 60)
            ledger = budget_ledger(system, cell, protocol, completed.returncode)
            ledger["caps"] = protocol["budget"]
            ledger["launcher_wall_seconds"] = time.time() - started
            write_json(cell / "usage_ledger.json", ledger)
            try:
                trace = finalize_cell(system, cell, task, protocol_path, ledger)
            except Exception as exc:
                trace = {"cell_complete": False, "failure": f"{type(exc).__name__}:{exc}"}
                write_json(cell / "generation_trace.json", {"schema": "pptbench-v2-generation-trace", "model_generated": True,
                           "system": system, "task_id": task["id"], "protocol_sha256": sha256(protocol_path), **trace})
            if not trace.get("cell_complete"):
                failures.append({"system": system, "task_id": task["id"], "failure": trace.get("failure", "contract_or_budget_gate")})
            write_json(run_root / "progress.json", {"completed_or_attempted": len(cells) - len([c for c in cells if not (run_root / 'raw' / c['system'] / c['task_id'] / 'generation_trace.json').is_file()]), "failures": failures})
    complete = not failures and len(cells) == 36
    if complete:
        prepare(protocol_path, run_root / "raw", run_root / "blind_review")
    summary = {"schema": "pptbench-v2-run-summary", "complete_36_cells": complete, "attempted_cells": len(cells), "failures": failures,
               "blind_review_bundles_created": complete, "result_gate_requires_two_locked_real_review_forms": True}
    write_json(run_root / "run_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
