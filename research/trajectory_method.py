"""Trajectory-Guided Domain Specialization, implemented as a runnable pipeline.

Only the non-loop part:
    Capture -> Induce -> Claim Gate -> Static Requirement -> C_static
Generic abstraction and PPT specialization are already code (core/, domains/ppt/),
so this module's terminal step builds the real C_static TaskContract per task.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

ACTION_MAP = {
    "read": "read", "discover": "discover", "inspect": "inspect", "plan": "plan",
    "edit": "mutate", "build": "mutate", "build_final": "mutate", "build_attempt1": "mutate",
    "mutate": "mutate", "tool_call": "tool_call", "render": "render",
    "render+pixel": "visual_inspect", "pixel_check": "visual_inspect",
    "diagnose": "detect_defect", "failure": "detect_defect", "debug": "detect_defect",
    "repair": "repair", "verify": "verify", "save": "finalize", "export": "finalize",
    "record": "finalize", "stop": "finalize",
}

EVIDENCE_CLASS = {
    "read": "A", "discover": "A", "inspect": "A/B", "plan": "B", "mutate": "B",
    "tool_call": "A/B", "render": "B", "visual_inspect": "B", "verify": "B",
    "detect_defect": "B", "repair": "B", "provenance": "B", "scope_check": "B",
    "finalize": "A/B",
}

# Where each induced behavior lands in the static C_static tuple.
STATIC_SLOT = {
    "read": ("I",), "discover": ("I",), "inspect": ("I",),
    "plan": ("T",), "mutate": ("M",), "tool_call": ("K",),
    "render": ("V",), "visual_inspect": ("V",), "verify": ("V",),
    "detect_defect": (), "repair": (),  # loop
    "provenance": ("V",), "scope_check": ("M",), "finalize": ("O",),
}

CAN_FIX_BEFORE_LOOP = {b: bool(STATIC_SLOT[b]) for b in STATIC_SLOT}


@dataclass
class RunRecord:
    agent: str
    task_id: str
    steps_path: Path
    events: int = 0
    behaviors: tuple = field(default_factory=tuple)
    behavior_counts: dict = field(default_factory=dict)


def _canonical_action(row: dict[str, Any]) -> str:
    if row.get("stop_reason"):
        return "finalize"
    raw = str(row.get("action") or row.get("tool") or row.get("step") or "unknown").strip()
    key = raw.casefold().replace(" ", "_")
    blob = json.dumps(row, ensure_ascii=False).casefold()
    if key in ACTION_MAP:
        action = ACTION_MAP[key]
    elif key.startswith("render"):
        action = "render"
    elif key.startswith("build") or key.startswith("edit"):
        action = "mutate"
    elif key.startswith("verif") or key.startswith("check"):
        action = "verify"
    elif key.startswith("repair") or key.startswith("retry"):
        action = "repair"
    else:
        action = "tool_call"
    if action in {"read", "discover", "inspect", "tool_call"}:
        if "provenance" in blob or "binding" in blob or "来源" in blob:
            return "provenance"
        if any(t in blob for t in ("unmodified", "未修改", "immutab", "保留原", "preserv", "scope")):
            return "scope_check"
    return action


def load_runs(root: Path) -> list[RunRecord]:
    """Capture: collect every preserved steps.jsonl under a workspaces root."""
    runs: list[RunRecord] = []
    for steps in sorted(root.rglob("trajectory/steps.jsonl")):
        task_dir = steps.parents[1]
        agent = task_dir.parents[0].parent.name
        counts: dict[str, int] = {}
        events = 0
        for line in steps.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not line.strip():
                continue
            events += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                row = {"action": "unparsed", "result": line}
            action = _canonical_action(row)
            counts[action] = counts.get(action, 0) + 1
        runs.append(RunRecord(agent=agent, task_id=task_dir.name, steps_path=steps,
                              events=events, behaviors=tuple(sorted(counts)),
                              behavior_counts=counts))
    return runs


@dataclass
class BehaviorStat:
    behavior: str
    frequency: int
    run_prevalence: float
    task_prevalence: float
    run_count: int
    task_count: int
    evidence_class: str
    static_slot: tuple
    can_fix_before_loop: bool


def induce(runs: list[RunRecord], all_tasks: Iterable[str] | None = None) -> list[BehaviorStat]:
    """Induce: frequency (secondary) + run prevalence + task prevalence."""
    task_universe = set(all_tasks) if all_tasks is not None else {r.task_id for r in runs}
    stats: list[BehaviorStat] = []
    for behavior in sorted(EVIDENCE_CLASS):
        matching = [r for r in runs if behavior in r.behaviors]
        tasks = {r.task_id for r in matching}
        stats.append(BehaviorStat(
            behavior=behavior,
            frequency=sum(r.behavior_counts.get(behavior, 0) for r in runs),
            run_prevalence=(len(matching) / len(runs)) if runs else 0.0,
            task_prevalence=(len(tasks) / len(task_universe)) if task_universe else 0.0,
            run_count=len(matching),
            task_count=len(tasks),
            evidence_class=EVIDENCE_CLASS[behavior],
            static_slot=STATIC_SLOT[behavior],
            can_fix_before_loop=CAN_FIX_BEFORE_LOOP[behavior],
        ))
    return stats


def claim_gate(behavior: str) -> str:
    """Claim gate only; does not decide where the design lives."""
    return EVIDENCE_CLASS.get(behavior, "B")


def extract_static_requirements(stats: list[BehaviorStat]) -> list[dict[str, Any]]:
    """Static requirement extraction: keep only what can be fixed before the loop."""
    rows = []
    for stat in stats:
        if stat.can_fix_before_loop:
            rows.append({
                "behavior": stat.behavior,
                "evidence_class": stat.evidence_class,
                "slot": list(stat.static_slot),
                "requirement": f"{stat.behavior} must be determined before dynamic execution",
                "run_prevalence": stat.run_prevalence,
                "task_prevalence": stat.task_prevalence,
            })
    return rows


def build_static_contract(task_dir: Path) -> Any:
    """Terminal landing: Discovery -> Intake -> PPTTaskDefinition -> C_static TaskContract."""
    from core.compiler import compile_task
    from core.intake import discover_sources
    from core.model import Task
    from domains import get_domain_pack
    from domains.ppt.intake import KIND_MAP, build_presentation_source_ir

    task_dir = Path(task_dir)
    instruction = ""
    for name in ("instruction.md", "instruction_source.md"):
        path = task_dir / name
        if path.is_file():
            instruction += path.read_text(encoding="utf-8-sig", errors="replace").strip() + "\n"
    if not instruction.strip():
        raise ValueError(f"no instruction found under {task_dir}")

    source_ir = build_presentation_source_ir(task_dir)
    sources = discover_sources([r.path for r in source_ir.sources], kind_map=KIND_MAP)
    output = task_dir / "output" / "final.pptx"
    pack = get_domain_pack("ppt")
    return compile_task(
        Task(id=task_dir.name, instruction=instruction, sources=tuple(s.path for s in sources), output=output),
        pack,
    )


def main(root: Path, out: Path | None = None) -> dict[str, Any]:
    runs = load_runs(root)
    stats = induce(runs)
    requirements = extract_static_requirements(stats)
    report = {
        "schema": "trajectory-guided-domain-specialization-v1",
        "runs": len(runs),
        "behaviors": [stat.__dict__ for stat in stats],
        "static_requirements": requirements,
        "claim_boundary": "EvidenceClass controls claims about competitor internals; C_static controls our non-loop contract.",
    }
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(r"E:\project\agent\ppt-harness\benchmark_v0.1\agent_workspaces\full13"))
    parser.add_argument("--out", type=Path, default=Path(r"E:\project\agent\ppt-harness\benchmark_v0.1\research\trajectory_method_xiaopu.json"))
    args = parser.parse_args()
    print(json.dumps(main(args.root, args.out), ensure_ascii=False)[:800])
