"""PPT Domain Pack public API and import-time registration."""
from __future__ import annotations

from domains.ppt.ir import (
    ChartIR,
    ImageIR,
    PresentationIR,
    ShapeIR,
    SlideIR,
    TableIR,
    TextBoxIR,
    from_pptx,
)
from domains.ppt.intake import (
    KIND_MAP,
    PresentationSourceIR,
    WorkbookSheet,
    build_presentation_source_ir,
    normalize_html,
    normalize_image,
    normalize_pptx,
    normalize_xlsx,
    normalize_xmind,
)
from domains.ppt.provenance import SourceBinding, collect_bindings
from domains.ppt.skills import PPT_SKILLS, register_ppt_skills
from domains.ppt.task_definition import (
    PPTTaskDefinition,
    PROFILE_SPECS,
    SKILL_SPECS,
    TASK_DEFINITIONS,
    definition_for,
)
from domains.ppt.task_types import PPTTaskType, classify_ppt_task
from domains.ppt.tools import PPT_TOOL_FACADE, register_ppt_capabilities, register_ppt_tools
from domains.ppt.transaction import (
    PptAttributeChange,
    PptDelta,
    PptImmutabilityCertificate,
    PptMutationScope,
    delta_within_mutation,
    diff_decks,
    verify_immutability,
)
from domains.ppt.verification import (
    ALL_KINDS,
    CONTENT_GROUNDING,
    IMMUTABILITY,
    LAYOUT,
    RENDER,
    STRUCTURAL,
    VISUAL,
    verification_policy,
)


def _register_ppt_domain() -> None:
    from core.artifact import register_ir_builder

    register_pptx_builder = True
    try:
        register_ir_builder("pptx", from_pptx)
    except ValueError:
        register_pptx_builder = False
    _ = register_pptx_builder
    try:
        register_ppt_capabilities()
    except ValueError:
        pass
    try:
        register_ppt_tools()
    except ValueError:
        pass
    try:
        register_ppt_skills()
    except ValueError:
        pass


_register_ppt_domain()

__all__ = [
    "ALL_KINDS", "CONTENT_GROUNDING", "IMMUTABILITY", "LAYOUT", "RENDER",
    "STRUCTURAL", "VISUAL", "verification_policy",
    "PPTTaskType", "classify_ppt_task",
    "PPTTaskDefinition", "TASK_DEFINITIONS", "SKILL_SPECS", "PROFILE_SPECS", "definition_for",
    "PresentationIR", "SlideIR", "ShapeIR", "TextBoxIR", "ImageIR", "TableIR",
    "ChartIR", "from_pptx",
    "PresentationSourceIR", "WorkbookSheet", "KIND_MAP",
    "build_presentation_source_ir", "normalize_pptx", "normalize_xlsx",
    "normalize_xmind", "normalize_html", "normalize_image",
    "SourceBinding", "collect_bindings",
    "PPT_SKILLS", "register_ppt_skills",
    "PPT_TOOL_FACADE", "register_ppt_capabilities",
    "PptMutationScope", "PptAttributeChange", "PptDelta", "PptImmutabilityCertificate",
    "diff_decks", "delta_within_mutation", "verify_immutability",
]
