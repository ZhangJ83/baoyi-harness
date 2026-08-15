"""Re-run the four failing tasks after harness optimization."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"E:\project\agent\xiaopu")
RUN_ROOT = ROOT / "workspace" / "iteration_runs"
sys.path.insert(0, str(ROOT / "benchmarks"))
from iteration_loop import ensure_task_package, discover_output, score_workbuddy, score_ppteval  # noqa: E402

TASKS = [
    "board-material-update-timeline-excel",
    "html-report-quadrant-ppt",
    "xmind-screenshot-template-ppt",
    "Accounting Equation-004",
]
PROMPTS = {
    "board-material-update-timeline-excel": "完成 tasks/board-material-update-timeline-excel：用 XLSX 更新治理会 PPT 并保持一致。",
    "html-report-quadrant-ppt": "完成 tasks/html-report-quadrant-ppt：用 HTML/XLSX 数据生成一页四象限汇报 PPT。",
    "xmind-screenshot-template-ppt": "完成 tasks/xmind-screenshot-template-ppt：按模板与截图生成社区工作坊演示稿。",
    "Accounting Equation-004": "完成 tasks/Accounting Equation-004：只把 Liability/Liabilities 改为 Debt/Debts。",
}
WB = {"board-material-update-timeline-excel", "html-report-quadrant-ppt", "xmind-screenshot-template-ppt"}
results = []
for task_id in TASKS:
    task_dir = ensure_task_package(task_id)
    # clear previous output so the score is from this run
    out_dir = task_dir / "output"
    if out_dir.is_dir():
        for file in out_dir.glob("*.pptx"):
            file.unlink()
    log = RUN_ROOT / f"retry_{task_id}.log"
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    started = time.time()
    run = subprocess.run(
        [sys.executable, "-m", "agent.main", "--workspace", str(RUN_ROOT), PROMPTS[task_id]],
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
    results.append(cell)
    print(json.dumps({k: cell.get(k) for k in ("task", "score", "passed", "total", "error", "elapsed")}, ensure_ascii=False), flush=True)

(RUN_ROOT / "retry_failures.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("done")
