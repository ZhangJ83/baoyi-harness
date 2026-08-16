"""Deterministic one-line task compiler.

The compiler turns a short user request plus the authoritative task brief into
an auditable execution contract.  It does not decide content; it decides the
artifact mode, primary PPT skill, scope hints, plan envelope, and evidence
contract that the runtime must enforce.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import re
from pathlib import Path


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


@dataclass(frozen=True)
class TaskSpec:
    task_root: str = ""
    artifact_mode: str = "edit_existing"
    intent: str = "atomic_edit"
    skill: str = "ppt.atomic_edit"
    primary_input: str = ""
    output_path: str = ""
    operation: str = ""
    source_slides: tuple[int, ...] = ()
    mutation_slides: tuple[int, ...] = ()
    verification: tuple[str, ...] = ("ppt_structural",)
    plan: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self) | {
            "source_slides": list(self.source_slides),
            "mutation_slides": list(self.mutation_slides),
            "verification": list(self.verification),
            "plan": list(self.plan),
        }


def _slides(text: str) -> tuple[int, ...]:
    found: set[int] = set()
    for m in re.finditer(r"(?:slide|page)\s*(\d+)", text, re.I):
        found.add(int(m.group(1)))
    for m in re.finditer(r"(?:slides?|pages?)\s*(\d+)\s*(?:and|,|&)\s*(\d+)", text, re.I):
        found.update({int(m.group(1)), int(m.group(2))})
    for m in re.finditer(r"第\s*(\d+)\s*[、,和及]\s*(\d+)\s*页", text):
        found.update({int(m.group(1)), int(m.group(2))})
    return tuple(sorted(found))


def portable_contract_for(request: str, facts: dict[str, str] | None = None, brief: str = ""):
    """Compatibility bridge onto the new portable stack.

    Produces the same TaskContract the future runtime will execute against,
    without changing the legacy TaskSpec returned by :func:`compile_task`.
    """
    from core.compiler import compile_task as compile_portable
    from core.model import Task
    from domains import get_domain_pack

    facts = facts or {}
    instruction = facts.get("task_instruction", "")
    text = f"{request}\n{instruction}\n{brief}"
    pack = get_domain_pack("ppt")
    return compile_portable(
        Task(id=facts.get("manifest_task_id", "") or "task", instruction=text),
        pack,
    )


def compile_task(request: str, facts: dict[str, str] | None = None, brief: str = "") -> TaskSpec:
    facts = facts or {}
    instruction = facts.get("task_instruction", "")
    text = f"{request}\n{instruction}\n{brief}".casefold()
    # New portable contract is computed first so real runs traverse
    # Discovery -> Intake -> PPTTaskDefinition -> TaskContract. Legacy output
    # below remains the compatibility-facing TaskSpec.
    try:
        portable = portable_contract_for(request, facts, brief)
    except Exception:
        portable = None
    task_root = facts.get("task_root", "") or facts.get("manifest_task_id", "")
    primary = facts.get("ppt_input_deck", "")
    output = facts.get("required_output_pptx", "")
    # Never infer page scope from the full ContentIR: source JSON and prior
    # trajectory text often contain every slide number.  Scope comes from the
    # user's request or authoritative instruction only.
    source = _slides(f"{request}\n{instruction}".casefold())
    capability = facts.get("task_capability", "").casefold().strip()
    # A template deck is source material for a NEW deck, not an artifact to
    # edit in place. Keyword-driven template/xmind/outline builds must not be
    # downgraded to edit_existing merely because intake bound the template as
    # the discovered input deck. An explicit task-card capability always wins
    # over noisy keywords in instruction/brief text.
    template_build_requested = bool(not capability) and any(
        marker in text for marker in ("template", "xmind", "outline", "模板", "大纲")
    )
    mode = (
        "new_deck"
        if template_build_requested
        else ("edit_existing" if primary or ".pptx" in text else "new_deck")
    )
    intent = "atomic_edit"
    skill = "ppt.atomic_edit"
    # Task cards may carry more than one capability (``;``, ``/``, ``、`` or
    # ``+`` separated).  Each segment is matched against the frozen table so a
    # compound capability resolves to the first supported PPT skill.
    contract_skill = ""
    if capability:
        segments = [part.strip() for part in re.split(r"[;+、]|,|/", capability) if part.strip()]
        for segment in segments:
            if segment in SKILL_BY_CAPABILITY:
                contract_skill = SKILL_BY_CAPABILITY[segment]
                break
        if not contract_skill and segments[0] in SKILL_BY_CAPABILITY:
            contract_skill = SKILL_BY_CAPABILITY[segments[0]]
    if contract_skill:
        skill = contract_skill
        intent = skill.removeprefix("ppt.")
        if skill == "ppt.template_build":
            mode = "new_deck"
    elif any(x in text for x in ("xlsx", "source_sync", "源数据", "数据更新", "同步到", "excel")):
        intent, skill = "source_sync", "ppt.source_sync"
    elif any(x in text for x in ("overlap", "overlap repair", "图片重叠", "内容修改并修复")):
        intent, skill = "content_and_layout", "ppt.content_and_layout"
    elif any(x in text for x in ("cross-slide", "composite", "combine", "merge", "合并", "合成", "插入一张新")):
        intent, skill = "compose_from_slides", "ppt.compose_from_slides"
    elif any(x in text for x in ("quadrant", "html", "source-grounded", "多来源", "四象限")):
        intent, skill = "source_grounded_build", "ppt.source_grounded_build"
    elif any(x in text for x in ("template", "xmind", "outline", "模板")):
        intent, skill = "template_build", "ppt.template_build"
    elif any(x in text for x in ("reflow", "two-column", "layout", "geometry", "排版", "分栏")):
        intent, skill = "layout_reflow", "ppt.layout_reflow"
    elif any(x in text for x in ("diagram", "flowchart", "process", "流程图")):
        intent, skill = "diagram_composition", "ppt.diagram_composition"
    elif any(x in text for x in ("font", "color", "fill", "字号", "字体", "颜色")):
        intent, skill = "atomic_style", "ppt.atomic_style"
    elif any(x in text for x in ("textbox", "text box", "add element", "文本框")):
        intent, skill = "element_creation", "ppt.element_creation"
    if mode == "new_deck" and skill == "ppt.atomic_edit":
        skill, intent = "ppt.template_build", "template_build"
    operation = ""
    if skill == "ppt.atomic_edit":
        if any(x in text for x in ("bullet", "项目符号", "要点", "after “", "after \"")):
            operation = "append_bullet"
        elif any(x in text for x in ("replace", "change", "替换", "改为", "修改")):
            operation = "replace"
    if intent == "compose_from_slides" and len(source) >= 2:
        mutation = (max(source) + 1,)
    else:
        mutation = source[:1]
    verification = ["ppt_structural"]
    if skill not in {"ppt.atomic_edit", "ppt.atomic_style"}:
        verification += ["ppt_render", "ppt_visual"]
    # The compiler no longer emits a fixed step-by-step plan. It only records
    # the coarse artifact route and contract fields; sequencing decisions
    # belong to the model inside the Loop.
    # Reconciliation with the portable contract: when the legacy decision and
    # the PPTTaskDefinition agree on a canonical type, the portable type wins.
    # Legacy-only types (source_sync / content_and_layout) stay authoritative
    # for backward compatibility.
    if (
        portable is not None
        and not contract_skill
        and skill not in {"ppt.source_sync", "ppt.content_and_layout"}
        and not (mode == "new_deck" and skill == "ppt.template_build")
    ):
        portable_skill = f"ppt.{portable.task_type}"
        if portable_skill.startswith("ppt."):
            skill, intent = portable_skill, portable.task_type
    return TaskSpec(task_root=task_root, artifact_mode=mode, intent=intent, skill=skill,
                    primary_input=primary, output_path=output, source_slides=source,
                    operation=operation, mutation_slides=mutation,
                    verification=tuple(verification), plan=())


def brief_json(spec: TaskSpec) -> str:
    return json.dumps(spec.to_dict(), ensure_ascii=False, separators=(",", ":"))
