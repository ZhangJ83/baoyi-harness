"""PPT SkillSpec registry generated from the single task-definition source."""
from __future__ import annotations

from typing import Dict

from core.skill import SkillSpec, register_skill
from domains.ppt.skills.atomic_edit import ATOMIC_EDIT
from domains.ppt.skills.atomic_style import ATOMIC_STYLE
from domains.ppt.skills.compose_from_slides import COMPOSE_FROM_SLIDES
from domains.ppt.skills.diagram_composition import DIAGRAM_COMPOSITION
from domains.ppt.skills.element_creation import ELEMENT_CREATION
from domains.ppt.skills.layout_reflow import LAYOUT_REFLOW
from domains.ppt.skills.source_grounded_build import SOURCE_GROUNDED_BUILD
from domains.ppt.skills.template_build import TEMPLATE_BUILD

PPT_SKILLS: Dict[str, SkillSpec] = {}


def register_ppt_skills() -> None:
    for spec in (ATOMIC_EDIT, ATOMIC_STYLE, ELEMENT_CREATION, LAYOUT_REFLOW,
                 DIAGRAM_COMPOSITION, COMPOSE_FROM_SLIDES,
                 SOURCE_GROUNDED_BUILD, TEMPLATE_BUILD):
        PPT_SKILLS[spec.name] = spec
        register_skill(spec)


register_ppt_skills()

__all__ = ["PPT_SKILLS", "register_ppt_skills"]
