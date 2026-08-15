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
        "editorial-minimal; one-message-per-slide; no decorative density",
        ("create", "generate", "new deck", "presentation", "workshop", "deck", "生成", "创建", "制作", "演示文稿", "幻灯片"),
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
PPT_EDIT = frozenset({"ppt_edit_text", "ppt_style", "ppt_metadata"})
PPT_COMPOSE = frozenset({"ppt_compose"})
PPT_ARRANGE = frozenset({"ppt_arrange"})
PPT_COMMIT = frozenset({"ppt_save"})
PPT_VERIFY = frozenset({"ppt_check"})


CAPABILITY_TOOL_GROUPS: dict[str, frozenset[str]] = {
    "workspace_discovery": frozenset({"discover_workspace", "list_dir", "glob_files", "search_text"}),
    "scoped_read": frozenset({"read_file", "read_many"}) | PPT_OBSERVE,
    "source_read": frozenset({"read_file", "read_many", "search_text", "list_dir"}),
    "multi_source_read": frozenset({"read_file", "read_many", "search_text", "list_dir"}),
    "content_ir": frozenset({"read_many", "read_file", "search_text"}),
    "shape_targeting": PPT_OBSERVE,
    "targeted_diagnosis": PPT_OBSERVE | PPT_VERIFY,
    "native_edit": PPT_EDIT | PPT_COMPOSE | PPT_ARRANGE | PPT_COMMIT,
    "geometry_edit": PPT_ARRANGE | PPT_COMMIT,
    "layout_compose": PPT_COMPOSE | PPT_ARRANGE,
    "semantic_layout": PPT_COMPOSE | PPT_ARRANGE,
    "content_compose": PPT_COMPOSE,
    "overlap_repair": PPT_ARRANGE,
    "artifact_preservation": PPT_COMMIT,
    "artifact_provenance": PPT_COMPOSE | PPT_COMMIT,
    "provenance_binding": frozenset({"ppt_metadata"}) | PPT_COMMIT,
    "source_notes": PPT_COMMIT,
    "ppt_structural": PPT_VERIFY,
    "ppt_geometry": PPT_VERIFY,
    "ppt_render": PPT_VERIFY,
    "render_inspection": PPT_VERIFY,
    "ppt_visual": PPT_VERIFY,
    "ppt_provenance": PPT_VERIFY,
    "content_binding": PPT_VERIFY,
    "reverification": PPT_VERIFY,
    "bounded_repair": PPT_EDIT | PPT_COMPOSE | PPT_ARRANGE | PPT_COMMIT,
}


# Skill-level composition table. Each PPT skill is a named bundle of the
# capability groups above; ``tools_for_skill`` is the single source used by
# ExecutionContract so capability-to-tool-surface routing stays in one place.
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
    """Canonical model-facing PPT tools for a compiled skill.

    This is the single binding used by ExecutionContract; it composes
    ``CAPABILITY_TOOL_GROUPS`` only, plus the always-available observe/commit/
    verify facade.
    """
    tools: set[str] = set(PPT_OBSERVE) | set(PPT_COMMIT) | set(PPT_VERIFY)
    for capability in SKILL_CAPABILITY_GROUPS.get(skill, ()):
        tools.update(CAPABILITY_TOOL_GROUPS.get(capability, ()))
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
