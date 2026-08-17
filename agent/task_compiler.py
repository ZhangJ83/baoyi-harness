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
    capability = facts.get("task_capability", "")
    instruction = facts.get("task_instruction", "")
    text = f"{capability}\n{request}\n{instruction}".strip() or brief
    pack = get_domain_pack("ppt")
    return compile_portable(
        Task(id=facts.get("manifest_task_id", "") or "task", instruction=text),
        pack,
    )


def compile_task(
    request: str,
    facts: dict[str, str] | None = None,
    brief: str = "",
    portable: Any = None,
) -> TaskSpec:
    facts = facts or {}
    instruction = facts.get("task_instruction", "")
    text = f"{request}\n{instruction}\n{brief}".casefold()

    if portable is None:
        try:
            portable = portable_contract_for(request, facts, brief)
        except Exception:
            portable = None

    task_root = facts.get("task_root", "") or facts.get("manifest_task_id", "")
    primary = facts.get("ppt_input_deck", "")
    output = facts.get("required_output_pptx", "")
    source = _slides(f"{request}\n{instruction}".casefold())

    if portable is not None:
        from agent.execution_contract import project_verification_contract

        intent = str(portable.task_type)
        skill = f"ppt.{portable.task_type}"
        verification = tuple(project_verification_contract(portable.verification))
    else:
        intent = "atomic_edit"
        skill = "ppt.atomic_edit"
        verification = ("ppt_structural",)

    if intent in {"template_build", "source_grounded_build"} and not primary:
        mode = "new_deck"
    else:
        mode = "edit_existing" if primary or ".pptx" in text else "new_deck"

    operation = ""
    if intent in {"atomic_edit", "atomic_style"}:
        if any(x in text for x in ("bullet", "项目符号", "要点", "after “", "after \"")):
            operation = "append_bullet"
        elif any(x in text for x in ("replace", "change", "替换", "改为", "修改")):
            operation = "replace"

    if intent == "compose_from_slides" and len(source) >= 2:
        mutation = (max(source) + 1,)
    else:
        mutation = source[:1]

    return TaskSpec(
        task_root=task_root,
        artifact_mode=mode,
        intent=intent,
        skill=skill,
        primary_input=primary,
        output_path=output,
        source_slides=source,
        operation=operation,
        mutation_slides=mutation,
        verification=verification,
        plan=(),
    )


def brief_json(spec: TaskSpec) -> str:
    return json.dumps(spec.to_dict(), ensure_ascii=False, separators=(",", ":"))
