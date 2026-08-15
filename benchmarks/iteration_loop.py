"""Continuous optimization loop for xiaopu.

Each round:
- samples the 2 lowest-scoring tasks of the frozen 13-task benchmark (until 1.0);
- runs one code-direction task from the downloaded HumanEval dataset;
- records scores and failed checks, and appends generic (not task-specific)
  optimization notes used by subsequent rounds.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = Path(r"E:\project\agent\ppt-harness\benchmark_v0.1")
PPTEVAL_RUBRICS = Path(r"E:\project\agent\ppt-harness\PPTEval\task_registry\rubrics")
PPTEVAL_SOURCE = BENCH / "ppt-eval" / "data" / "files" / "PowerPoint"
STATE_PATH = ROOT / "benchmarks" / "iteration_state.json"
RUN_ROOT = ROOT / "workspace" / "iteration_runs"
CODE_TASKS = ROOT / "benchmarks" / "code_tasks"
PROMPT_SUFFIX = ROOT / "benchmarks" / "optimization_prompt.txt"

TASKS13 = [
    "3-002", "3-003", "4._Pre-Colonial_Filipino_Culture-001", "3-006",
    "HSC Careers and Expo FINAL COM MOD-008", "Accounting Equation-004",
    "Aircraft_surface-004", "HSC Careers and Expo FINAL COM MOD-038",
    "Accounting Equation-045", "4._Pre-Colonial_Filipino_Culture-005",
    "board-material-update-timeline-excel", "html-report-quadrant-ppt",
    "xmind-screenshot-template-ppt",
]
WB_TASKS = {"board-material-update-timeline-excel", "html-report-quadrant-ppt",
            "xmind-screenshot-template-ppt"}
SHORT_PROMPT = {
    "3-002": "把标题里的 Lecture 3 改成 Lecture 1。",
    "3-003": "在第 2 页 Dual Mode 后添加一条 bullet 'File System'。",
    "4._Pre-Colonial_Filipino_Culture-001": "把演示文稿标题字号改为 48pt。",
    "3-006": "把第 3 页 vCPU1 的颜色从 magenta 改为 green。",
    "HSC Careers and Expo FINAL COM MOD-008": "在第 2 页右下角创建文本框 'Important Note'。",
    "Accounting Equation-004": "把全文 'Liability' 替换为 'Debt'。",
    "Aircraft_surface-004": "在第 2 页列表末尾添加给定 bullet 并缩放图片避免重叠。",
    "HSC Careers and Expo FINAL COM MOD-038": "把第 8 页 checklist 改成两栏布局。",
    "Accounting Equation-045": "在第 3 页创建 Left Hand Side → Right Hand Side → Balance 流程图。",
    "4._Pre-Colonial_Filipino_Culture-005": "合并第 2、3 页为一张新页（男/女服装表格+两图），保留原页。",
    "board-material-update-timeline-excel": "用 XLSX 更新治理会 PPT 的口径并保持页面一致。",
    "html-report-quadrant-ppt": "用工作区材料包生成一页四象限汇报 PPT。",
    "xmind-screenshot-template-ppt": "基于 XMind 和绿色模板生成工作坊演示稿。",
}


def load_state() -> dict:
    if STATE_PATH.is_file():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    seeded = {
        "3-002": 1.0, "3-003": 1.0,
        "board-material-update-timeline-excel": 0.686,
        "html-report-quadrant-ppt": 0.7564,
        "xmind-screenshot-template-ppt": 0.531,
    }
    return {"round": 0, "ppt_scores": dict(seeded), "ppt_best": dict(seeded),
            "ppt_failures": {}, "ppt_unscorable": {}, "ppt_attempts": {},
            "code_scores": {}, "code_next": 0, "no_improve_streak": 0, "notes": []}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_task_package(task_id: str) -> Path:
    task_dir = RUN_ROOT / "tasks" / task_id
    if task_dir.exists():
        return task_dir
    task_dir.mkdir(parents=True, exist_ok=True)
    if task_id in WB_TASKS:
        src = BENCH / "workbuddy" / task_id
        shutil.copytree(src, task_dir, dirs_exist_ok=True)
    else:
        src = BENCH / "agent_workspaces" / "full13" / "xiaopuharness" / "tasks" / task_id
        if src.is_dir():
            for name in ("instruction.md", "task_card.md"):
                if (src / name).is_file():
                    shutil.copy2(src / name, task_dir / name)
        (task_dir / "input").mkdir(exist_ok=True)
        deck = {
            "3-002": "3.pptx", "3-003": "3.pptx", "3-006": "3.pptx",
            "4._Pre-Colonial_Filipino_Culture-001": "4._Pre-Colonial_Filipino_Culture.pptx",
            "4._Pre-Colonial_Filipino_Culture-005": "4._Pre-Colonial_Filipino_Culture.pptx",
            "HSC Careers and Expo FINAL COM MOD-008": "HSC Careers and Expo FINAL COM MOD.pptx",
            "HSC Careers and Expo FINAL COM MOD-038": "HSC Careers and Expo FINAL COM MOD.pptx",
            "Accounting Equation-004": "Accounting Equation.pptx",
            "Accounting Equation-045": "Accounting Equation.pptx",
            "Aircraft_surface-004": "Aircraft_surface.pptx",
        }[task_id]
        shutil.copy2(PPTEVAL_SOURCE / deck, task_dir / "input" / deck)
    return task_dir


def discover_output(task_dir: Path) -> Path | None:
    out = task_dir / "output"
    if not out.is_dir():
        return None
    cands = [p for p in out.glob("*.pptx") if not p.name.startswith("~$")]
    return sorted(cands, key=lambda p: p.stat().st_mtime)[-1] if cands else None


def score_workbuddy(task_id: str, task_dir: Path, output: Path) -> dict:
    grading = BENCH / "workbuddy" / task_id / "tests" / "grading"
    gold = BENCH / "workbuddy" / task_id / "tests" / "gold" / "gold_answer.json"
    logs = RUN_ROOT / "verifier_logs" / task_id
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"; env["PYTHONUTF8"] = "1"
    env["WB_BENCH_GOLD_PATH"] = str(gold); env["WB_BENCH_CASE_DIR"] = str(task_dir)
    env["WB_BENCH_OUTPUT_PATH"] = str(output); env["WB_BENCH_VERIFIER_LOGS"] = str(logs)
    run = subprocess.run([sys.executable, str(grading / "eval_core.py"), str(output),
                          "--case-dir", str(task_dir), "--verifier-logs", str(logs)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=180, env=env)
    try:
        result = json.loads(run.stdout.strip())
    except json.JSONDecodeError:
        return {"error": "no json", "stdout": run.stdout[-500:]}
    score = result.get("pass_rate")
    if score is None and result.get("model_total"):
        score = result.get("model_score", 0) / result["model_total"]
    failed = result.get("failed_checks") or []
    return {"score": score, "passed": result.get("passed_count"), "total": result.get("total_count"),
            "failed": failed, "gated_pass": result.get("gated_pass")}


def score_ppteval(task_id: str, output: Path) -> dict:
    rubric = json.loads((PPTEVAL_RUBRICS / f"{task_id}.json").read_text(encoding="utf-8"))

    def leaves(node):
        if "scorer" in node:
            yield node
        for child in node.get("children", []):
            yield from leaves(child)

    results = []
    for node in leaves(rubric["root"]):
        code = (node.get("scorer") or {}).get("function_code", "") or ""
        if not code.strip() or "vlm_call" in code or "screenshots" in code or "ppt_diff" in code:
            results.append({"name": node.get("name"), "status": "unavailable"})
            continue
        ns = {"original_ppt_path": str(PPTEVAL_SOURCE / {
            "3-002": "3.pptx", "3-003": "3.pptx", "3-006": "3.pptx",
            "4._Pre-Colonial_Filipino_Culture-001": "4._Pre-Colonial_Filipino_Culture.pptx",
            "4._Pre-Colonial_Filipino_Culture-005": "4._Pre-Colonial_Filipino_Culture.pptx",
            "HSC Careers and Expo FINAL COM MOD-008": "HSC Careers and Expo FINAL COM MOD.pptx",
            "HSC Careers and Expo FINAL COM MOD-038": "HSC Careers and Expo FINAL COM MOD.pptx",
            "Accounting Equation-004": "Accounting Equation.pptx",
            "Accounting Equation-045": "Accounting Equation.pptx",
            "Aircraft_surface-004": "Aircraft_surface.pptx",
        }[task_id]), "modified_ppt_path": str(output)}
        try:
            exec(code, ns)
            reason, s = ns["compute_score"]()
            results.append({"name": node.get("name"), "status": "scored", "score": float(s), "reason": reason})
        except Exception as exc:
            results.append({"name": node.get("name"), "status": "error", "score": 0.0, "reason": str(exc)})
    scored = [r for r in results if r["status"] == "scored"]
    failed = [r for r in scored if r["score"] < 1.0]
    return {"score": (sum(r["score"] for r in scored) / len(scored)) if scored else None,
            "passed": sum(r["score"] for r in scored), "total": len(scored),
            "failed": failed, "unavailable": sum(r["status"] == "unavailable" for r in results)}


def run_ppt_cell(task_id: str, state: dict) -> dict:
    task_dir = ensure_task_package(task_id)
    prompt = f"完成 tasks/{task_id}：{SHORT_PROMPT[task_id]}"
    notes = "\n".join(state.get("notes", [])[-3:])
    if notes:
        prompt += "\n\n通用执行要求（上一轮优化）：\n" + notes
    log = RUN_ROOT / f"log_{task_id}.log"
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    start = time.time()
    run = subprocess.run([sys.executable, "-m", "agent.main", "--workspace", str(RUN_ROOT), prompt],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=1500, env=env)
    elapsed = round(time.time() - start, 1)
    log.write_text(run.stdout + "\n[stderr]\n" + run.stderr, encoding="utf-8")
    trajectory = _parse_trajectory(run.stdout)
    output = discover_output(task_dir)
    if output is None:
        return {"task": task_id, "score": None, "error": "output missing", "elapsed": elapsed,
                "trajectory": trajectory, "tail": (run.stdout + run.stderr)[-500:]}
    result = score_workbuddy(task_id, task_dir, output) if task_id in WB_TASKS else score_ppteval(task_id, output)
    result.update({"task": task_id, "elapsed": elapsed, "output": str(output),
                   "trajectory": trajectory, "tail": (run.stdout + run.stderr)[-800:]})
    return result


def _parse_trajectory(stdout: str) -> dict:
    """Cheap trajectory induction from a single-shot CLI log."""
    tool_calls = re.findall(r"> (\w+)\((.{0,120})", stdout)
    failures = re.findall(r"TOOL ERROR \(([^)]+)\): ([^\n]{0,160})", stdout)
    saved = bool(re.search(r"saved \d+ slides", stdout))
    verified = bool(re.search(r"passed/total = \d+/\d+|78/78|113/113|Verification: no structural", stdout))
    finished = "task marked complete" in stdout or "已完成" in stdout
    connection_error = bool(re.search(r"APIConnectionError|Connection error", stdout))
    return {"tool_calls": tool_calls[-20:], "failures": failures[-10:], "saved": saved,
            "verified": verified, "finished": finished, "connection_error": connection_error}


def run_code_cell(state: dict) -> dict:
    gz = CODE_TASKS / "HumanEval.jsonl.gz"
    if not gz.is_file():
        return {"error": "HumanEval dataset missing"}
    rows = [json.loads(line) for line in gzip.open(gz, "rt", encoding="utf-8") if line.strip()]
    index = state.get("code_next", 0) % len(rows)
    problem = rows[index]
    task_id = problem["task_id"].replace("/", "_")
    workdir = CODE_TASKS / "runs" / task_id
    shutil.rmtree(workdir, ignore_errors=True)
    workdir.mkdir(parents=True)
    (workdir / "problem.md").write_text(
        f"# {problem['task_id']}\n\n{problem['prompt']}\n\n"
        f"请在 {workdir.name} 目录中实现函数 `{problem['entry_point']}`，保存为 solution.py，"
        "只输出代码，不要写测试文件。", encoding="utf-8")
    env = dict(os.environ); env["PYTHONIOENCODING"] = "utf-8"
    start = time.time()
    run = subprocess.run([sys.executable, "-m", "agent.main", "--workspace", str(workdir),
                          f"完成代码任务：见 problem.md，实现 {problem['entry_point']} 并保存到 solution.py。"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=1500, env=env)
    elapsed = round(time.time() - start, 1)
    solution = workdir / "solution.py"
    code = solution.read_text(encoding="utf-8", errors="replace") if solution.is_file() else ""
    payload = code + "\n" + problem["test"] + "\n" + f"check({problem['entry_point']})\n"
    try:
        proc = subprocess.run([sys.executable, "-c", payload], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120)
        passed = proc.returncode == 0
        detail = (proc.stdout + proc.stderr)[-1000:]
    except subprocess.TimeoutExpired:
        passed, detail = False, "timeout"
    return {"task": task_id, "passed": passed, "elapsed": elapsed, "detail": detail,
            "has_solution": bool(code), "tail": (run.stdout + run.stderr)[-600:]}


def apply_trajectory_optimizations(state: dict, cells: list[dict]) -> None:
    """Apply system-level (not task-specific) optimizations from round evidence."""
    applied = list(state.get("applied_optimizations", []))
    analyses = dict(state.get("trajectory_analyses", {}))

    for cell in cells:
        if cell.get("kind") != "ppt":
            continue
        traj = cell.get("trajectory") or {}
        score = cell.get("score")
        key = f"r{state['round']}_{cell.get('task')}"
        analyses[key] = {
            "score": score,
            "error": cell.get("error"),
            "failed_checks": [f.get("name") for f in (cell.get("failed") or [])],
            "trajectory": traj,
        }
        if traj.get("connection_error") and "llm_retry_apiconnection" not in applied:
            applied.append("llm_retry_apiconnection")  # code changed in agent/llm.py
        if cell.get("error") == "output missing" and "save_before_pause" not in applied:
            applied.append("save_before_pause")  # code changed in agent/harness.py
        names = " ".join(f.get("name", "") for f in (cell.get("failed") or [])).casefold()
        if ("extraneous" in names or "unwanted" in names or "unintended" in names) \
                and "finish_immutability_gate" not in applied:
            applied.append("finish_immutability_gate")  # code changed in agent/tools/code_tools.py
        if traj.get("finished") and score == 1.0 and "success_profile_1.0" not in applied:
            applied.append("success_profile_1.0")
    state["trajectory_analyses"] = analyses
    state["applied_optimizations"] = applied
    notes = set(state.get("notes", []))
    if "finish_immutability_gate" in applied:
        notes.add("局部编辑任务只允许修改目标页；保存后系统会对照输入 deck 检查非目标页并阻止 finish。")
    if "llm_retry_apiconnection" in applied:
        notes.add("连接类错误会自动重试；仍失败时先保存再继续，不要空转。")
    state["notes"] = sorted(notes)[-8:]


def optimize_generically(state: dict, cells: list[dict]) -> None:
    notes = set(state.get("notes", []))
    for cell in cells:
        if cell.get("kind") != "ppt":
            continue
        failed = cell.get("failed") or []
        for item in failed:
            name = (item.get("name") if isinstance(item, dict) else str(item)).casefold()
            if "extraneous" in name or "unwanted" in name or "unintended" in name:
                notes.add("修改范围严格限定在目标对象；不得改动无关文字、格式、换行、动画或转场。")
            if "connector" in name or "arrow" in name or "flowchart" in name:
                notes.add("图示/流程图必须同时创建节点形状和箭头连接线，连接线连接相邻节点。")
            if "placeholder" in name:
                notes.add("生成后必须运行任务自带的 tests/grading/eval_core.py，并逐条修复失败的确定性检查，直到全部通过再 finish。")
            if "provenance" in name or "binding" in name:
                notes.add("多来源任务必须保留来源绑定（可见 source chip、speaker notes 或对象描述），并覆盖要求的 anchor/chart/metric ID。")
            if "dump" in name or "bulk" in name:
                notes.add("可见文本保持董事会语言，禁止把原表、JSON 片段、文件名和批量 ID 堆进正文。")
        if cell.get("error") == "output missing":
            notes.add("在 finish 之前必须先保存产物到任务要求的 output 路径，然后运行任务自带的验证器。")
    code_cells = [c for c in cells if c.get("kind") == "code"]
    if code_cells and not code_cells[-1].get("passed"):
        notes.add("代码任务先读 problem.md 定位需求，写出最小正确实现并保存到指定文件，再用本地测试快速自检后 finish。")
    state["notes"] = sorted(notes)[-8:]


def run_round(round_no: int | None = None) -> dict:
    state = load_state()
    state["round"] = round_no if round_no is not None else state.get("round", 0) + 1
    pending = [t for t in TASKS13
               if state.get("ppt_best", {}).get(t) not in (1.0,)
               and not state.get("ppt_unscorable", {}).get(t)]
    if not pending:
        print("all locally-scorable tasks reached 1.0 (unscorable: "
              + ",".join(state.get("ppt_unscorable", {})) + ")")
        return {"stable": True, "reason": "best_reached"}
    before = dict(state.get("ppt_best", {}))
    # Fair rotation: each pending task gets retries before stuck tasks monopolize
    # the two slots; within the same attempt count, lowest score goes first.
    sample = sorted(pending, key=lambda t: (state.get("ppt_attempts", {}).get(t, 0),
                                            state.get("ppt_best", {}).get(t, 0.0)))[:2]
    cells = []
    for task_id in sample:
        print(f"[round {state['round']}] PPT cell: {task_id}", flush=True)
        result = run_ppt_cell(task_id, state)
        result["kind"] = "ppt"
        state.setdefault("ppt_attempts", {})[task_id] = state.get("ppt_attempts", {}).get(task_id, 0) + 1
        if result.get("score") is not None:
            score = round(float(result["score"]), 4)
            state["ppt_scores"][task_id] = score
            state.setdefault("ppt_best", {})[task_id] = max(state.get("ppt_best", {}).get(task_id, 0.0), score)
        elif result.get("total") == 0:
            # VLM-only rubric (e.g. 3-006): no local deterministic checks exist.
            state["ppt_scores"][task_id] = None
            state.setdefault("ppt_unscorable", {})[task_id] = True
        state["ppt_failures"][task_id] = result.get("failed", [])
        cells.append(result)
        save_state(state)
        print(json.dumps({k: result.get(k) for k in ("task", "score", "passed", "total", "elapsed", "error")},
                         ensure_ascii=False), flush=True)
    code = run_code_cell(state)
    code["kind"] = "code"
    state["code_scores"][code.get("task", state["code_next"])] = {"passed": code.get("passed"), "detail": code.get("detail")}
    state["code_next"] = state.get("code_next", 0) + 1
    cells.append(code)
    apply_trajectory_optimizations(state, cells)
    optimize_generically(state, cells)
    improved = any(
        state.get("ppt_best", {}).get(t, 0.0) > before.get(t, 0.0)
        for t in set(before) | set(state.get("ppt_best", {}))
    )
    if improved:
        state["no_improve_streak"] = 0
    else:
        state["no_improve_streak"] = state.get("no_improve_streak", 0) + 1
    stable = state["no_improve_streak"] >= 3
    save_state(state)
    summary = {"round": state["round"], "ppt_cells": sample, "stable": stable,
               "no_improve_streak": state["no_improve_streak"],
               "ppt_best": {t: state.get("ppt_best", {}).get(t) for t in TASKS13 if t in state.get("ppt_best", {})},
               "ppt_unscorable": sorted(state.get("ppt_unscorable", {})),
               "code": {k: code.get(k) for k in ("task", "passed", "has_solution")},
               "notes": state["notes"]}
    (ROOT / "benchmarks" / "iteration_last_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--round-no", type=int, default=None)
    args = parser.parse_args()
    for _ in range(args.rounds):
        try:
            summary = run_round(args.round_no)
        except Exception as exc:
            print(f"ROUND ERROR: {type(exc).__name__}: {exc}", flush=True)
            return 1
        if summary.get("stable"):
            print("STABLE BEST REACHED; stopping.", flush=True)
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
