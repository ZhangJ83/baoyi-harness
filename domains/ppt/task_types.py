"""PPT task ontology: exactly the eight portable task types.

Legacy labels from the frozen benchmark (xlsx source-sync, content+layout
overlap repair) map onto canonical types so no existing coverage is lost, but
the ontology itself stays the eight portable entries.
"""
from __future__ import annotations

from enum import Enum


class PPTTaskType(str, Enum):
    ATOMIC_EDIT = "atomic_edit"
    ATOMIC_STYLE = "atomic_style"
    ELEMENT_CREATION = "element_creation"
    LAYOUT_REFLOW = "layout_reflow"
    DIAGRAM_COMPOSITION = "diagram_composition"
    COMPOSE_FROM_SLIDES = "compose_from_slides"
    SOURCE_GROUNDED_BUILD = "source_grounded_build"
    TEMPLATE_BUILD = "template_build"


def classify_ppt_task(text: str) -> PPTTaskType:
    """Classify one instruction into the canonical PPT task ontology.

    Rule order is intentional: compound instructions are classified by their
    most distinctive operation, never silently dropped to a text edit.
    """
    t = (text or "").lower()
    has = lambda *needles: any(n in t for n in needles)  # noqa: E731

    # Task card explicit capabilities first
    if has("precise text editing", "text structure editing", "global cross-slide text replacement"):
        return PPTTaskType.ATOMIC_EDIT
    if has("shape/color editing", "font formatting"):
        return PPTTaskType.ATOMIC_STYLE
    if has("cross-slide synthesis and composite generation"):
        return PPTTaskType.COMPOSE_FROM_SLIDES
    if has("diagram generation"):
        return PPTTaskType.DIAGRAM_COMPOSITION
    if has("content editing plus overlap repair"):
        return PPTTaskType.LAYOUT_REFLOW
    if has("element creation and spatial positioning"):
        return PPTTaskType.ELEMENT_CREATION
    if has("pptx update from xlsx source; consistency editing", "source-grounded one-slide synthesis; four-quadrant layout; provenance"):
        return PPTTaskType.SOURCE_GROUNDED_BUILD
    if has("structured deck generation from mindmap; template following"):
        return PPTTaskType.TEMPLATE_BUILD

    # Legacy xlsx source-sync -> canonical source-grounded build.
    if has("xlsx", "登记簿", "register", "source sync", "同步", "workbook", "工作簿"):
        return PPTTaskType.SOURCE_GROUNDED_BUILD

    if has("combine", "合并", "compose_from_slides", "into a single", "into one"):
        return PPTTaskType.COMPOSE_FROM_SLIDES

    if has("flowchart", "流程图", "diagram", "smartart", "graphic"):
        return PPTTaskType.DIAGRAM_COMPOSITION

    if has("two-column", "two column", "两栏", "两列", "2 column", "reflow", "重排", "layout"):
        return PPTTaskType.LAYOUT_REFLOW

    if has("template", "模板", "xmind", "导图", "mindmap"):
        return PPTTaskType.TEMPLATE_BUILD

    if has("html", "四象限", "quadrant", "source-grounded", "grounded"):
        return PPTTaskType.SOURCE_GROUNDED_BUILD

    if has("overlap", "重叠", "avoid overlap", "resize"):
        return PPTTaskType.LAYOUT_REFLOW

    if has("color", "颜色", "font", "字号", "size", "style", "bold", "italic"):
        return PPTTaskType.ATOMIC_STYLE

    if has("text box", "文本框", "caption", "add a new slide", "new slide", "create a slide"):
        return PPTTaskType.ELEMENT_CREATION

    return PPTTaskType.ATOMIC_EDIT
