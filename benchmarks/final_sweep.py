"""Final sweep: run and score every locally-scorable PPT task once."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"E:\project\agent\xiaopu")
RUN_ROOT = ROOT / "workspace" / "iteration_runs"
BENCH = Path(r"E:\project\agent\ppt-harness\benchmark_v0.1")
sys.path.insert(0, str(ROOT / "benchmarks"))
from iteration_loop import ensure_task_package, discover_output, score_workbuddy, score_ppteval  # noqa: E402

TASKS = [
    "3-002",
    "3-003",
    "board-material-update-timeline-excel",
    "html-report-quadrant-ppt",
    "xmind-screenshot-template-ppt",
    "4._Pre-Colonial_Filipino_Culture-001",
    "HSC Careers and Expo FINAL COM MOD-008",
    "Accounting Equation-004",
    "Aircraft_surface-004",
    "HSC Careers and Expo FINAL COM MOD-038",
    "Accounting Equation-045",
    "4._Pre-Colonial_Filipino_Culture-005",
]
SHORT = {
    "3-002": "完成 tasks/3-002 的 PPT 编辑。",
    "3-003": "完成 tasks/3-003 的 PPT 编辑。",
    "board-material-update-timeline-excel": "完成 tasks/board-material-update-timeline-excel：用 XLSX 更新治理会 PPT 并保持一致。",
    "html-report-quadrant-ppt": "完成 tasks/html-report-quadrant-ppt：用 HTML/XLSX 数据生成一页四象限汇报 PPT。",
    "xmind-screenshot-template-ppt": "完成 tasks/xmind-screenshot-template-ppt：按模板与截图生成社区工作坊演示稿。",
    "4._Pre-Colonial_Filipino_Culture-001": "完成 tasks/4._Pre-Colonial_Filipino_Culture-001 的 PPT 编辑。",
    "HSC Careers and Expo FINAL COM MOD-008": "完成 tasks/HSC Careers and Expo FINAL COM MOD-008 的 PPT 编辑。",
    "Accounting Equation-004": "完成 tasks/Accounting Equation-004：只把 Liability/Liabilities 改为 Debt/Debts。",
    "Aircraft_surface-004": "完成 tasks/Aircraft_surface-004 的 PPT 编辑。",
    "HSC Careers and Expo FINAL COM MOD-038": "完成 tasks/HSC Careers and Expo FINAL COM MOD-038 的 PPT 编辑。",
    "Accounting Equation-045": "完成 tasks/Accounting Equation-045：在第3页创建 Left Hand Side -> Right Hand Side -> Balance 流程图。",
    "4._Pre-Colonial_Filipino_Culture-005": "完成 tasks/4._Pre-Colonial_Filipino_Culture-005 的 PPT 编辑。",
}
WB = {"board-material-update-timeline-excel", "html-report-quadrant-ppt", "xmind-screenshot-template-ppt"}

results = {"unscorable": ["3-006"], "cells": []}
for task_id in TASKS:
    task_dir = ensure_task_package(task_id)
    prompt = SHORT[task_id]
    log = RUN_ROOT / f"final_sweep_{task_id}.log"
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    started = time.time()
    run = subprocess.run(
        [sys.executable, "-m", "agent.main", "--workspace", str(RUN_ROOT), prompt],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=1500, env=env,
    )
    elapsed = round(time.time() - started, 1)
    log.write_text(run.stdout + "\n[stderr]\n" + run.stderr, encoding="utf-8")
    output = discover_output(task_dir)
    if output is None:
        cell = {"task": task_id, "score": None, "error": "output missing", "elapsed": elapsed}
    elif task_id in WB:
        cell = score_workbuddy(task_id, task_dir, output)
        cell.update({"task": task_id, "elapsed": elapsed, "output": str(output)})
    else:
        cell = score_ppteval(task_id, output)
        cell.update({"task": task_id, "elapsed": elapsed, "output": str(output)})
    results["cells"].append(cell)
    print(json.dumps({k: cell.get(k) for k in ("task", "score", "passed", "total", "error", "elapsed")}, ensure_ascii=False), flush=True)

results["overall"] = {
    "scorable": len(results["cells"]),
    "pass": sum(1 for c in results["cells"] if c.get("score") == 1.0),
    "scored_1.0": [c["task"] for c in results["cells"] if c.get("score") == 1.0],
    "not_1.0": [c["task"] for c in results["cells"] if c.get("score") != 1.0],
}
out_path = RUN_ROOT / "final_sweep.json"
out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("saved:", out_path)
print("overall:", json.dumps(results["overall"], ensure_ascii=False))
