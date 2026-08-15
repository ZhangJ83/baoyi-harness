"""Cross-agent trajectory reverse engineering for the PPT harness.

Six adapters normalize the actual benchmark schemas.  Task contracts decide
the primary Skill; trajectories decide the execution, verification, repair,
and stopping policy.  Output is both research-readable and runtime-consumable.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


SKILL_BY_CAPABILITY = {
    "precise text editing": "ppt.atomic_edit",
    "text structure editing": "ppt.atomic_edit",
    "shape/color editing": "ppt.atomic_style",
    "font formatting": "ppt.atomic_style",
    "cross-slide synthesis and composite generation": "ppt.compose_from_slides",
    "global cross-slide text replacement": "ppt.atomic_edit",
    "diagram generation": "ppt.diagram_composition",
    "content editing plus overlap repair": "ppt.content_and_layout",
    "element creation and spatial positioning": "ppt.element_creation",
    "layout reflow": "ppt.layout_reflow",
    "pptx update from xlsx source; consistency editing": "ppt.source_sync",
    "source-grounded one-slide synthesis; four-quadrant layout; provenance": "ppt.source_grounded_build",
    "structured deck generation from mindmap; template following": "ppt.template_build",
}

CANONICAL = {
    "read": "READ", "load": "OPEN", "open": "OPEN", "inspect": "INSPECT",
    "extract": "EXTRACT", "plan": "PLAN", "create": "COMPOSE", "compose": "COMPOSE",
    "edit": "EDIT", "modify": "EDIT", "update": "EDIT", "save": "SAVE",
    "render": "RENDER", "export": "RENDER", "check": "CHECK", "verify": "VERIFY",
    "validate": "VERIFY", "repair": "REPAIR", "record": "RECORD", "stop": "STOP",
    "finish": "STOP", "start": "START", "output": "OUTPUT",
}


@dataclass
class Event:
    index: int
    kind: str
    tool: str = ""
    target: str = ""
    detail: str = ""
    result: str = ""
    success: bool = True
    error_type: str = ""
    raw_keys: tuple[str, ...] = ()


def text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def meta(path: Path) -> dict[str, Any]:
    try:
        return json.loads(text(path))
    except json.JSONDecodeError:
        return {}


def jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in text(path).splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def classify_kind(label: str, tool: str, detail: str, result: str) -> str:
    value = label.casefold().strip().replace("-", "_")
    for token in re.split(r"[^a-z_]+", value):
        if token in CANONICAL:
            return CANONICAL[token]
    joined = f"{label} {tool} {detail} {result}".casefold()
    rules = (
        (("render", "png", "screenshot", "powerpoint com", "libreoffice", "export"), "RENDER"),
        (("verify", "validation", "assert", "re-open", "reopen", "evaluator"), "VERIFY"),
        (("check", "overflow", "overlap", "bounds", "quality"), "CHECK"),
        (("repair", "retry", "fix"), "REPAIR"),
        (("save", "write ppt", "final.pptx", "output.pptx"), "SAVE"),
        (("inspect", "inventory", "geometry", "shapes"), "INSPECT"),
        (("extract", "parse", "read image", "read text"), "EXTRACT"),
        (("read", "load input", "instruction"), "READ"),
        (("plan", "strategy"), "PLAN"),
        (("compose", "insert new slide", "add slide", "flowchart", "textbox"), "COMPOSE"),
        (("edit", "replace", "change", "update", "resize", "reflow"), "EDIT"),
        (("stop", "finish", "complete"), "STOP"),
    )
    for needles, kind in rules:
        if any(needle in joined for needle in needles):
            return kind
    return "OTHER"


def adapt(row: dict[str, Any], index: int, source_agent: str) -> Event:
    # Preserve root identity; run_metadata sometimes collapses WorkBuddy modes.
    if source_agent == "claude-code":
        label, tool = str(row.get("action", "")), ""
        target, detail = str(row.get("target", "")), str(row.get("reason", ""))
    elif source_agent == "codex":
        label, tool = str(row.get("kind", "")), str(row.get("tool", ""))
        target = str(row.get("path") or row.get("file") or row.get("slide") or "")
        detail = str(row.get("detail", ""))
    elif source_agent == "opencode":
        label, tool = str(row.get("step", "")), str(row.get("tool", ""))
        target, detail = str(row.get("target", "")), str(row.get("detail", ""))
    elif source_agent == "workbuddy-ppt-agent-mode":
        label, tool = str(row.get("phase", "")), str(row.get("tool", ""))
        target, detail = str(row.get("target", "")), str(row.get("description", ""))
    else:  # deepseek and HY3
        label = str(row.get("action") or row.get("tool") or row.get("step") or "")
        tool = str(row.get("tool", ""))
        target = str(row.get("target") or row.get("args") or "")
        detail = str(row.get("detail", ""))
    result = str(row.get("result") or row.get("reason") or row.get("stop_reason") or "")
    error = ""
    low = f"{result} {detail}".casefold()
    success = not any(x in low for x in ("tool error", "failed", "exception", "traceback", "budgetexceeded"))
    if not success:
        m = re.search(r"(?:error|exception)\s*[:(]?\s*([A-Za-z][A-Za-z0-9_]*)", result, re.I)
        error = m.group(1) if m else "tool_failure"
    return Event(index=index, kind=classify_kind(label, tool, detail, result), tool=tool,
                 target=target[:1000], detail=detail[:2000], result=result[:2000],
                 success=success, error_type=error, raw_keys=tuple(sorted(row)))


def contract(task_dir: Path) -> dict[str, str]:
    card, instruction = text(task_dir / "task_card.md"), text(task_dir / "instruction.md")
    def field(name: str) -> str:
        m = re.search(rf"^{re.escape(name)}:\s*(.+)$", card, re.M | re.I)
        return m.group(1).strip() if m else ""
    capability = field("CAPABILITY").casefold()
    return {"task_id": field("TASK_ID") or task_dir.name, "source": field("SOURCE"),
            "difficulty": field("DIFFICULTY"), "capability": capability,
            "instruction": instruction.strip(), "skill": SKILL_BY_CAPABILITY.get(capability, "ppt.unknown")}


def compress_sequence(events: list[Event]) -> list[str]:
    result = []
    for event in events:
        if event.kind == "OTHER":
            continue
        if not result or result[-1] != event.kind:
            result.append(event.kind)
    return result


def collect(roots: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for root in roots:
        source_agent = root.parent.name
        for task_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            trajectory = task_dir / "trajectory"
            c = contract(task_dir)
            raw = jsonl(trajectory / "steps.jsonl")
            events = [adapt(item, i + 1, source_agent) for i, item in enumerate(raw)]
            sequence = compress_sequence(events)
            checks = text(trajectory / "checks.md")
            repairs = text(trajectory / "repairs.md")
            artifacts = text(trajectory / "artifacts.md")
            success = bool(re.search(r"\bPASS(?:ED)?\b|requirements met|completed|success", checks + artifacts, re.I))
            rows.append({
                **c, "agent": source_agent, "trajectory_dir": str(trajectory),
                "events": [asdict(e) for e in events], "event_count": len(events),
                "sequence": sequence, "success_recorded": success,
                "failed_events": sum(not e.success for e in events),
                "has_plan": "PLAN" in sequence or bool(text(trajectory / "plan.md").strip()),
                "has_render": "RENDER" in sequence or bool(re.search(r"render|png|screenshot", checks, re.I)),
                "has_verify": any(k in sequence for k in ("CHECK", "VERIFY")) or bool(checks.strip()),
                "has_repair": "REPAIR" in sequence or bool(repairs.strip() and not re.search(r"no .*repair", repairs, re.I)),
                "has_stop": "STOP" in sequence,
                "tools": sorted({e.tool for e in events if e.tool}),
            })
    return rows


def best_path(entries: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [e for e in entries if e["events"] and e["has_verify"]]
    if not usable:
        usable = [e for e in entries if e["events"]]
    if not usable:
        return {"agent": "", "sequence": [], "event_count": 0}
    def score(e):
        completeness = sum((e["has_plan"], e["has_verify"], e["has_render"], e["has_stop"], e["success_recorded"]))
        return (-completeness, e["failed_events"], e["event_count"])
    chosen = min(usable, key=score)
    return {"agent": chosen["agent"], "sequence": chosen["sequence"],
            "event_count": chosen["event_count"], "tools": chosen["tools"],
            "trajectory_dir": chosen["trajectory_dir"]}


def build_contracts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_skill: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_skill[row["skill"]].append(row)
    contracts = {}
    tool_map = {
        "ppt.atomic_edit": ["ppt_open", "ppt_inspect", "ppt_edit_text", "ppt_save", "ppt_check", "finish"],
        "ppt.atomic_style": ["ppt_open", "ppt_inspect", "ppt_style", "ppt_save", "ppt_check", "finish"],
        "ppt.compose_from_slides": ["ppt_open", "ppt_inspect", "ppt_compose", "ppt_save", "ppt_check", "finish"],
        "ppt.diagram_composition": ["ppt_open", "ppt_inspect", "ppt_compose", "ppt_save", "ppt_check", "finish"],
        "ppt.content_and_layout": ["ppt_open", "ppt_inspect", "ppt_edit_text", "ppt_arrange", "ppt_save", "ppt_check", "finish"],
        "ppt.element_creation": ["ppt_open", "ppt_inspect", "ppt_compose", "ppt_save", "ppt_check", "finish"],
        "ppt.layout_reflow": ["ppt_open", "ppt_inspect", "ppt_arrange", "ppt_save", "ppt_check", "finish"],
        "ppt.source_sync": ["ppt_open", "ppt_inspect", "ppt_edit_text", "ppt_style", "ppt_save", "ppt_check", "finish"],
        "ppt.source_grounded_build": ["ppt_open", "ppt_inspect", "ppt_compose", "ppt_save", "ppt_check", "finish"],
        "ppt.template_build": ["ppt_open", "ppt_inspect", "ppt_compose", "ppt_save", "ppt_check", "finish"],
    }
    for skill, entries in sorted(by_skill.items()):
        sequences = Counter(" > ".join(e["sequence"]) for e in entries if e["sequence"])
        task_ids = sorted({e["task_id"] for e in entries})
        complex_skill = skill not in {"ppt.atomic_edit", "ppt.atomic_style"}
        contracts[skill] = {
            "skill": skill, "evidence_runs": len(entries), "task_ids": task_ids,
            "visible_tools": tool_map.get(skill, ["ppt_open", "ppt_inspect", "ppt_save", "ppt_check", "finish"]),
            "canonical_stages": (["resolve", "inspect", "mutate", "save", "check", "finish"] if not complex_skill
                                 else ["resolve", "inspect", "compose", "save", "render_check", "repair_once", "finish"]),
            "verification": (["ppt_structural"] if not complex_skill else ["ppt_structural", "ppt_render", "ppt_visual"]),
            "max_repairs": 1, "failure_policy": {
                "missing_input": "return deterministic task-local candidates; never guess filenames",
                "same_error_family": "retry once with changed strategy, then stop",
                "verification_failure": "repair only cited slide/shape once, then reverify",
            },
            "stop_condition": "saved final artifact and fresh required evidence",
            "common_sequences": [{"sequence": seq, "count": n} for seq, n in sequences.most_common(5)],
        }
    return contracts


def write_outputs(rows: list[dict[str, Any]], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with (out / "trajectory_normalized_v2.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_task[row["task_id"]].append(row)
    paired = {}
    for task_id, entries in sorted(by_task.items()):
        paired[task_id] = {
            "skill": entries[0]["skill"], "capability": entries[0]["capability"],
            "instruction": entries[0]["instruction"], "runs": len(entries),
            "best_path": best_path(entries),
            "agents": {e["agent"]: {k: e[k] for k in ("event_count", "sequence", "failed_events", "has_plan", "has_render", "has_verify", "has_repair", "has_stop", "tools")} for e in entries},
        }
    (out / "paired_task_analysis.json").write_text(json.dumps(paired, ensure_ascii=False, indent=2), encoding="utf-8")
    contracts = build_contracts(rows)
    (out / "skill_contracts.json").write_text(json.dumps({"schema": "xiaopu.skill-contracts.v1", "skills": contracts}, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "task_skill_matrix_v2.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ["agent", "task_id", "difficulty", "capability", "skill", "event_count", "failed_events", "has_plan", "has_render", "has_verify", "has_repair", "has_stop"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        writer.writerows({k: row[k] for k in fields} for row in rows)
    taxonomy = Counter(e["kind"] for row in rows for e in row["events"])
    transitions = Counter()
    for row in rows:
        transitions.update(zip(row["sequence"], row["sequence"][1:]))
    (out / "operation_taxonomy_v2.json").write_text(json.dumps({"events": taxonomy, "transitions": [{"from": a, "to": b, "count": n} for (a,b),n in transitions.most_common()]}, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 78 条 PPT trajectory 逆向分析报告", "", f"- 轨迹总数：{len(rows)}", f"- 非空步骤：{sum(bool(r['events']) for r in rows)}", f"- 标准事件总数：{sum(r['event_count'] for r in rows)}", f"- Skill 数：{len(contracts)}", "", "## Skill 证据", ""]
    for name, c in contracts.items():
        lines += [f"### {name}", "", f"证据运行：{c['evidence_runs']}；任务：{', '.join(c['task_ids'])}", f"工具面：{', '.join(c['visible_tools'])}", f"标准阶段：{' → '.join(c['canonical_stages'])}", f"验证：{', '.join(c['verification'])}；修复上限：{c['max_repairs']}", ""]
    lines += ["## 核心设计结论", "", "1. Task contract 决定 Skill，trajectory 决定执行策略，避免关键词误分类。", "2. 输入解析、输出路径、范围和验证合同必须由 Harness 编译并持久化。", "3. 模型每轮只看主 Skill 的 5–7 个 canonical 工具；隐藏工具执行时同样拒绝。", "4. 原子编辑走 resolve→inspect→mutate→save→check→finish；复杂任务增加 render/visual 和一次有限 repair。", "5. 路径错误按 failure family 熔断，不能通过更换猜测文件名绕过。", "6. trajectory 是研究旁路；核心任务不依赖记录成功。", ""]
    (out / "TRAJECTORY_SKILL_DESIGN_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--root", action="append", required=True, type=Path); p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(); rows = collect(args.root); write_outputs(rows, args.output)
    print(json.dumps({"trajectories": len(rows), "events": sum(r["event_count"] for r in rows), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
