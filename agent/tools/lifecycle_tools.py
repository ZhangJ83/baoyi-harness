"""Workspace discovery and explicit source-to-output provenance tools."""
from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

from .. import config
from ..lifecycle import discover_workspace
from ..permissions import path_within


def _make(name, description, params, required, fn):
    return ({"type": "function", "function": {"name": name, "description": description, "parameters": {"type": "object", "properties": params, "required": required}}}, fn)


def _discover(h):
    result = discover_workspace()
    if getattr(h, "recorder", None):
        h.recorder.event("workspace_discovery_requested", discovery=result)
    return result


def _bind(h, source_path: str, output_path: str, usage: str):
    root = config.sandbox_root().resolve()
    source = (root / source_path).resolve()
    output = (root / output_path).resolve()
    if not path_within(root, source) or not source.is_file():
        raise FileNotFoundError(source_path)
    if not path_within(root, output):
        raise PermissionError("output path escapes workspace")
    if not getattr(h, "recorder", None):
        raise RuntimeError("run recorder is not initialized")
    h.recorder.bind_source(source, str(output), usage)
    return f"bound source {source_path} -> {output_path} ({usage})"


def _run_task_evaluator(h, timeout_seconds: int = 120):
    root = config.sandbox_root().resolve()
    evaluator_rel = h.state.facts.get("official_evaluator")
    if not evaluator_rel:
        raise RuntimeError("no official task evaluator was discovered during intake")
    evaluator = (root / evaluator_rel).resolve()
    if not path_within(root, evaluator) or not evaluator.is_file():
        raise FileNotFoundError(evaluator_rel)
    task_root = evaluator.parents[2]
    tests_root = task_root / "tests"
    grading = tests_root / "grading"
    output_rel = h.state.facts.get("required_output_pptx")
    if not output_rel:
        raise RuntimeError("official evaluator requires a bound task output")
    output = (root / output_rel).resolve()
    if not output.is_file():
        raise FileNotFoundError(f"save the required output before evaluation: {output_rel}")
    logs = getattr(getattr(h, "recorder", None), "evidence", task_root / "trajectory") / "task_evaluator"
    logs.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    # The task-local evaluator receives artifact paths, never provider secrets.
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"):
        env.pop(name, None)
    env.update({
        "WB_BENCH_CASE_DIR": str(task_root),
        "WB_BENCH_FIXTURES_DIR": str(tests_root / "gold" / "fixtures"),
        "WB_BENCH_GOLD_PATH": str(tests_root / "gold" / "gold_answer.json"),
        "WB_BENCH_OUTPUT_PATH": str(output),
        "WB_BENCH_VERIFIER_LOGS": str(logs),
        "WB_BENCH_WORKSPACE": str(task_root),
        "PYTHONPATH": os.pathsep.join([str(task_root), str(grading), env.get("PYTHONPATH", "")]),
    })
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", str(evaluator), "-p", "no:cacheprovider", "-q", "--tb=short"],
        cwd=task_root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=max(10, min(timeout_seconds, 300)), check=False,
    )
    transcript = (completed.stdout + "\n" + completed.stderr).strip()
    (logs / "test_output.txt").write_text(transcript, encoding="utf-8")
    passed = completed.returncode == 0
    if passed:
        h.state.record_evidence("task_evaluator", "official task evaluator passed")
        h.state.unresolved_checks.discard("task_evaluator")
    else:
        h.state.unresolved_checks.add("task_evaluator")
        h.state.last_verification_failed = True
        h.state.last_verification_epoch = h.state.mutation_epoch
    if getattr(h, "recorder", None):
        h.recorder.check("task_evaluator", passed, transcript[-12000:])
    return f"official evaluator {'passed' if passed else 'failed'} (exit={completed.returncode})\n{transcript[-5000:]}"


lifecycle_tools = [
    _make("discover_workspace", "Discover instruction/task files, supplied office inputs, output hints, and available PPT routes before planning.", {}, [], lambda h, **kw: _discover(h)),
    _make("bind_provenance", "Record how a supplied source file contributes to an output. Use for HTML/XLSX/PPTX/PDF/DOCX and other multi-source tasks.", {"source_path": {"type": "string"}, "output_path": {"type": "string"}, "usage": {"type": "string"}}, ["source_path", "output_path", "usage"], lambda h, **kw: _bind(h, kw["source_path"], kw["output_path"], kw["usage"])),
    _make("run_task_evaluator", "Run the official task-local deterministic evaluator discovered by intake against the saved required output.", {"timeout_seconds": {"type": "integer"}}, [], lambda h, **kw: _run_task_evaluator(h, kw.get("timeout_seconds", 120))),
]
