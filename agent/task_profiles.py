"""Task profiles and capability routing for the Xiaopu harness.

The catalog is intentionally small and evidence-oriented.  It borrows the
useful separation found in Claude Code's local skill system (a task-facing
description, a when-to-use rule, and an allowed capability set) without
claiming to reproduce any proprietary implementation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TaskProfile:
    name: str
    label: str
    description: str
    capabilities: tuple[str, ...]
    verification: tuple[str, ...]
    design_policy: str
    markers: tuple[str, ...]

    def catalog_line(self) -> str:
        return f"{self.label}: {self.description}; capabilities={', '.join(self.capabilities)}; verification={', '.join(self.verification)}"


TASK_PROFILES: tuple[TaskProfile, ...] = (
    TaskProfile(
        "edit_existing", "Existing-deck edit", "Make a targeted change while preserving unrelated slides and source files.",
        ("workspace_discovery", "scoped_read", "shape_targeting", "native_edit", "artifact_preservation"),
        ("ppt_structural", "ppt_render", "ppt_visual"),
        "preserve-template; inspect-affected-scope; minimal-mutation",
        ("existing", "modify", "edit", "change", "replace", "resize", "add bullet", "修改", "编辑", "替换", "字号", "颜色", "标题", "项目符号"),
    ),
    TaskProfile(
        "create_deck", "New-deck generation", "Create a concise deck with semantic slide layouts and a clear audience-facing hierarchy.",
        ("workspace_discovery", "source_read", "semantic_layout", "content_compose", "artifact_provenance"),
        ("ppt_structural", "ppt_render", "ppt_visual", "ppt_provenance"),
        "content-rich; 3-8 substantive points per slide; use semantic layouts (flowchart/quadrant/comparison)",
        ("create", "generate", "new deck", "presentation", "workshop", "deck", "生成", "创建", "制作", "演示文稿", "幻灯片", "PPT", "pptx", "ppt", "页", "page", "slides"),
    ),
    TaskProfile(
        "layout_reflow", "Layout reflow", "Recompose an existing page to improve hierarchy, density, and spatial balance without losing content.",
        ("scoped_read", "shape_targeting", "geometry_edit", "layout_compose", "overlap_repair"),
        ("ppt_structural", "ppt_geometry", "ppt_render", "ppt_visual"),
        "content-first; preserve-all-required-content; repair-overlap-before-shrinking-type",
        ("layout", "reflow", "two-column", "overlap", "space", "position", "checklist", "排版", "重排", "双栏", "重叠", "位置", "清单"),
    ),
    TaskProfile(
        "source_grounded", "Source-grounded synthesis", "Synthesize supplied HTML/XLSX/JSON/notes into a traceable PPT without inventing unsupported claims.",
        ("multi_source_read", "content_ir", "provenance_binding", "semantic_layout", "source_notes"),
        ("ppt_structural", "ppt_render", "ppt_visual", "ppt_provenance", "content_binding"),
        "source-bound; restrained executive layout; claims-and-citations stay traceable",
        ("source", "html", "xlsx", "workbook", "quadrant", "actuals", "provenance", "traceability", "来源", "资料", "四象限", "数据", "溯源"),
    ),
    TaskProfile(
        "repair_deck", "PPT repair", "Diagnose a concrete slide defect, apply a bounded repair, and rerun the affected check.",
        ("targeted_diagnosis", "geometry_edit", "render_inspection", "bounded_repair", "reverification"),
        ("ppt_structural", "ppt_geometry", "ppt_render", "ppt_visual"),
        "evidence-driven; one defect scope per repair; no speculative restyling",
        ("repair", "fix", "broken", "overflow", "clip", "defect", "reverify", "修复", "故障", "溢出", "裁切", "缺陷", "重验证"),
    ),
)


# Profiles describe semantic capabilities; this table is their only binding to
# the model-facing tool surface.  The facade stays deliberately small while
# the lifecycle owns rendering, provenance capture, and final delivery.
PPT_OBSERVE = frozenset({"ppt_open", "ppt_inspect"})
PPT_EDIT = frozenset({"ppt_edit_text", "ppt_style", "ppt_metadata", "ppt_notes"})
PPT_COMPOSE = frozenset({"ppt_compose"})
PPT_ARRANGE = frozenset({"ppt_arrange"})
PPT_COMMIT = frozenset({"ppt_save"})
PPT_VERIFY = frozenset({"ppt_check"})


# General PPT capability catalog. Task classification no longer selects a
# task-specific bundle; every PPT project gets the same small, auditable
# capability set and the model plans which capability to use inside each phase.
GENERAL_PPT_CAPABILITY_GROUPS: dict[str, frozenset[str]] = {
    "workspace_read": frozenset({"discover_workspace", "list_dir", "glob_files", "search_text"}),
    "source_read": frozenset({"read_file", "read_many", "search_text", "list_dir"}),
    "deck_observe": PPT_OBSERVE,
    "text_edit": PPT_EDIT,
    "compose": PPT_COMPOSE,
    "arrange": PPT_ARRANGE,
    "commit": PPT_COMMIT,
    "verify": PPT_VERIFY,
}

# Compatibility surface for legacy profile/contract code. New routing uses
# GENERAL_PPT_CAPABILITY_GROUPS; these names are retained only so older tests
# and diagnostics keep stable identifiers.
CAPABILITY_TOOL_GROUPS: dict[str, frozenset[str]] = {
    "workspace_discovery": GENERAL_PPT_CAPABILITY_GROUPS["workspace_read"],
    "scoped_read": GENERAL_PPT_CAPABILITY_GROUPS["source_read"] | GENERAL_PPT_CAPABILITY_GROUPS["deck_observe"],
    "source_read": GENERAL_PPT_CAPABILITY_GROUPS["source_read"],
    "multi_source_read": GENERAL_PPT_CAPABILITY_GROUPS["source_read"],
    "content_ir": GENERAL_PPT_CAPABILITY_GROUPS["source_read"],
    "shape_targeting": GENERAL_PPT_CAPABILITY_GROUPS["deck_observe"],
    "targeted_diagnosis": GENERAL_PPT_CAPABILITY_GROUPS["deck_observe"] | GENERAL_PPT_CAPABILITY_GROUPS["verify"],
    "native_edit": GENERAL_PPT_CAPABILITY_GROUPS["text_edit"] | GENERAL_PPT_CAPABILITY_GROUPS["compose"] | GENERAL_PPT_CAPABILITY_GROUPS["arrange"] | GENERAL_PPT_CAPABILITY_GROUPS["commit"],
    "geometry_edit": GENERAL_PPT_CAPABILITY_GROUPS["arrange"] | GENERAL_PPT_CAPABILITY_GROUPS["commit"],
    "layout_compose": GENERAL_PPT_CAPABILITY_GROUPS["compose"] | GENERAL_PPT_CAPABILITY_GROUPS["arrange"],
    "semantic_layout": GENERAL_PPT_CAPABILITY_GROUPS["compose"] | GENERAL_PPT_CAPABILITY_GROUPS["arrange"],
    "content_compose": GENERAL_PPT_CAPABILITY_GROUPS["compose"],
    "overlap_repair": GENERAL_PPT_CAPABILITY_GROUPS["arrange"],
    "artifact_preservation": GENERAL_PPT_CAPABILITY_GROUPS["commit"],
    "artifact_provenance": GENERAL_PPT_CAPABILITY_GROUPS["compose"] | GENERAL_PPT_CAPABILITY_GROUPS["commit"],
    "provenance_binding": frozenset({"ppt_metadata"}) | GENERAL_PPT_CAPABILITY_GROUPS["commit"],
    "source_notes": GENERAL_PPT_CAPABILITY_GROUPS["commit"],
    "ppt_structural": GENERAL_PPT_CAPABILITY_GROUPS["verify"],
    "ppt_geometry": GENERAL_PPT_CAPABILITY_GROUPS["verify"],
    "ppt_render": GENERAL_PPT_CAPABILITY_GROUPS["verify"],
    "render_inspection": GENERAL_PPT_CAPABILITY_GROUPS["verify"],
    "ppt_visual": GENERAL_PPT_CAPABILITY_GROUPS["verify"],
    "ppt_provenance": GENERAL_PPT_CAPABILITY_GROUPS["verify"],
    "content_binding": GENERAL_PPT_CAPABILITY_GROUPS["verify"],
    "reverification": GENERAL_PPT_CAPABILITY_GROUPS["verify"],
    "bounded_repair": GENERAL_PPT_CAPABILITY_GROUPS["text_edit"] | GENERAL_PPT_CAPABILITY_GROUPS["compose"] | GENERAL_PPT_CAPABILITY_GROUPS["arrange"] | GENERAL_PPT_CAPABILITY_GROUPS["commit"],
}


# Legacy names kept for diagnostics only. tools_for_skill now returns the
# general PPT catalog so the model owns capability selection and planning.
SKILL_CAPABILITY_GROUPS: dict[str, frozenset[str]] = {
    "ppt.atomic_edit": frozenset({"scoped_read", "shape_targeting", "native_edit", "artifact_preservation", "ppt_structural"}),
    "ppt.atomic_style": frozenset({"scoped_read", "shape_targeting", "native_edit", "artifact_preservation", "ppt_structural"}),
    "ppt.compose_from_slides": frozenset({"scoped_read", "shape_targeting", "content_compose", "artifact_preservation", "ppt_structural"}),
    "ppt.diagram_composition": frozenset({"scoped_read", "shape_targeting", "content_compose", "artifact_preservation", "ppt_structural"}),
    "ppt.content_and_layout": frozenset({"scoped_read", "shape_targeting", "native_edit", "geometry_edit", "artifact_preservation", "ppt_structural"}),
    "ppt.element_creation": frozenset({"scoped_read", "shape_targeting", "content_compose", "artifact_preservation", "ppt_structural"}),
    "ppt.layout_reflow": frozenset({"scoped_read", "shape_targeting", "geometry_edit", "layout_compose", "artifact_preservation", "ppt_structural"}),
    "ppt.source_sync": frozenset({"scoped_read", "shape_targeting", "native_edit", "artifact_preservation", "ppt_structural"}),
    "ppt.source_grounded_build": frozenset({"multi_source_read", "content_ir", "semantic_layout", "provenance_binding", "source_notes", "ppt_structural"}),
    "ppt.template_build": frozenset({"scoped_read", "content_ir", "semantic_layout", "artifact_preservation", "ppt_structural"}),
}


def tools_for_skill(skill: str) -> set[str]:
    """Canonical model-facing PPT tools for any PPT project.

    The compiler no longer picks a task-specific bundle. Every PPT skill
    receives the same general capability catalog; phase scoping and the
    delivery gates still constrain when each capability may be used.
    """
    tools: set[str] = set(PPT_OBSERVE) | set(PPT_COMMIT) | set(PPT_VERIFY)
    for group in GENERAL_PPT_CAPABILITY_GROUPS.values():
        tools.update(group)
    for name in tuple(tools):
        tools.update(_LEGACY_TOOL_ALIASES.get(name, ()))
    return tools


# Old phase controllers intersect profile tools with legacy executor names.
# Keep that compatibility here, behind the canonical catalog, instead of
# leaking implementation primitives back into CAPABILITY_TOOL_GROUPS.
_LEGACY_TOOL_ALIASES: dict[str, frozenset[str]] = {
    "ppt_open": frozenset({"open_deck"}),
    "ppt_inspect": frozenset({"deck_info", "shape_inventory"}),
    "ppt_edit_text": frozenset({"replace_shape_text", "replace_text", "append_bullet"}),
    "ppt_style": frozenset({"set_text_style", "set_shape_fill"}),
    "ppt_compose": frozenset({
        "new_deck", "add_slide", "add_two_column_slide", "add_metric_slide",
        "add_table_slide", "add_process_slide", "add_image_slide",
        "compose_quadrant_slide", "add_textbox", "add_textbox_to_slide",
        "add_flowchart", "set_speaker_notes",
    }),
    "ppt_arrange": frozenset({
        "set_shape_geometry", "delete_shape", "delete_slide", "move_slide",
    }),
    "ppt_save": frozenset({"save_deck"}),
    "ppt_check": frozenset({
        "ppt_verify", "ppt_quality_check", "render_deck",
        "inspect_rendered_deck", "run_task_evaluator",
    }),
}


def tools_for_profile(profile: TaskProfile) -> set[str]:
    """Return canonical tools plus an isolated legacy-controller shim."""
    tools: set[str] = set()
    for capability in profile.capabilities:
        tools.update(CAPABILITY_TOOL_GROUPS.get(capability, ()))
    for verification in profile.verification:
        tools.update(CAPABILITY_TOOL_GROUPS.get(verification, ()))
    for name in tuple(tools):
        tools.update(_LEGACY_TOOL_ALIASES.get(name, ()))
    return tools


def _matches(profile: TaskProfile, text: str) -> int:
    lowered = text.lower()
    score = 0
    for marker in profile.markers:
        if re.fullmatch(r"[a-z0-9 ]+", marker):
            # Word-boundary match so "edit" never matches "editorial", "deck"
            # never matches "deck.pptx", etc.
            if re.search(r"(?<![a-z0-9])" + re.escape(marker) + r"(?![a-z0-9])", lowered):
                score += 1
        else:
            if marker in lowered:
                score += 1
    return score


def classify_task(task: str) -> TaskProfile:
    """Choose the best task profile, with conservative PPT defaults."""
    candidates = sorted(
        ((_matches(profile, task), index, profile) for index, profile in enumerate(TASK_PROFILES)),
        key=lambda item: (-item[0], item[1]),
    )
    score, _, profile = candidates[0]
    if score == 0:
        # Default to create_deck for PPT tasks instead of edit_existing
        ppt_keywords = ('ppt', 'pptx', 'powerpoint', '幻灯片', '演示文稿', '制作', 'slide', '页')
        if any(kw in task.lower() for kw in ppt_keywords):
            return next((p for p in TASK_PROFILES if p.name == 'create_deck'), TASK_PROFILES[0])
        return TASK_PROFILES[0]
    # A concrete repair request wins over broad create/edit markers.
    repair = next((item for item in TASK_PROFILES if item.name == "repair_deck"), None)
    if repair and _matches(repair, task) >= 2:
        return repair
    return profile


def capability_catalog(profiles: Iterable[TaskProfile] = TASK_PROFILES) -> str:
    return "\n".join(f"- {profile.catalog_line()}" for profile in profiles)


def profile_for_name(name: str) -> TaskProfile:
    return next((profile for profile in TASK_PROFILES if profile.name == name), TASK_PROFILES[0])
