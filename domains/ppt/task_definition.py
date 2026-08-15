"""Single source of truth for every PPT task type.

One PPTTaskDefinition fully describes what a task type requires and forbids.
Profile, SkillSpec, VerificationContract, and mutation policy are all
*generated* from it -- nothing is hand-maintained in a second table.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

from core.compiler import DomainProfile
from core.skill import SkillSpec
from core.transaction import ImmutabilityPolicy
from core.verification import VerificationContract

from domains.ppt.verification import (
    CONTENT_GROUNDING,
    IMMUTABILITY,
    LAYOUT,
    RENDER,
    STRUCTURAL,
    VISUAL,
)

READ = "presentation.read"
EDIT = "presentation.edit"
STYLE = "presentation.style"
RENDER_CAP = "presentation.render"
VISUAL_INSPECT = "presentation.visual_inspect"
STRUCTURE_INSPECT = "presentation.structure_inspect"
ARRANGE = "presentation.arrange"

_OBJECT_SCOPE = ImmutabilityPolicy(
    allow=("slides", "shapes", "properties"),
    deny=("theme", "master", "animations", "transitions"),
)
_LAYOUT_SCOPE = ImmutabilityPolicy(
    allow=("slides", "shapes", "properties"),
    deny=("content_text", "theme", "master", "animations", "transitions"),
)
_DECK_SCOPE = ImmutabilityPolicy(
    allow=("slides", "shapes"),
    deny=("theme", "master", "animations", "transitions"),
)


@dataclass(frozen=True)
class PPTTaskDefinition:
    task_type: str
    description: str
    profile_name: str
    required_capabilities: Tuple[str, ...]
    allowed_capabilities: Tuple[str, ...] = ()
    verification: Tuple[str, ...] = ()
    mutation_scope: str = "slides/shapes/properties"
    mutation_policy: ImmutabilityPolicy = field(default_factory=lambda: _OBJECT_SCOPE)

    def to_skill(self) -> SkillSpec:
        return SkillSpec(
            name=self.task_type,
            description=self.description,
            capabilities=self.required_capabilities,
            allowed_capabilities=self.allowed_capabilities,
            required_inputs=("binary",) if self.task_type != "source_grounded_build" else ("binary", "text"),
            verification_contract=self.verification,
            mutation_scope=self.mutation_scope,
        )

    def to_profile(self) -> DomainProfile:
        return DomainProfile(
            name=self.profile_name,
            capabilities=self.required_capabilities,
            verification=self.verification,
        )

    def to_verification_contract(self) -> VerificationContract:
        return VerificationContract.from_kinds(self.verification)

    def to_mutation_policy(self) -> ImmutabilityPolicy:
        return self.mutation_policy


TASK_DEFINITIONS: Dict[str, PPTTaskDefinition] = {
    "atomic_edit": PPTTaskDefinition(
        task_type="atomic_edit",
        description="single-target text or list edit with minimal change discipline",
        profile_name="edit_existing",
        required_capabilities=(READ, EDIT),
        allowed_capabilities=(READ, EDIT),
        verification=(STRUCTURAL, IMMUTABILITY),
    ),
    "atomic_style": PPTTaskDefinition(
        task_type="atomic_style",
        description="single-target style change such as font size or object color",
        profile_name="edit_existing",
        required_capabilities=(READ, STYLE),
        allowed_capabilities=(READ, STYLE),
        verification=(STRUCTURAL, IMMUTABILITY),
    ),
    "element_creation": PPTTaskDefinition(
        task_type="element_creation",
        description="create one new object and position it precisely",
        profile_name="create_deck",
        required_capabilities=(READ, EDIT, STRUCTURE_INSPECT),
        allowed_capabilities=(READ, EDIT),
        verification=(STRUCTURAL, LAYOUT),
    ),
    "layout_reflow": PPTTaskDefinition(
        task_type="layout_reflow",
        description="reorganize existing content into a new spatial arrangement",
        profile_name="layout_reflow",
        required_capabilities=(READ, EDIT, ARRANGE),
        allowed_capabilities=(READ, EDIT, ARRANGE),
        verification=(STRUCTURAL, RENDER, VISUAL),
        mutation_policy=_LAYOUT_SCOPE,
    ),
    "diagram_composition": PPTTaskDefinition(
        task_type="diagram_composition",
        description="compose a diagram from primitives with connectors and labels",
        profile_name="create_deck",
        required_capabilities=(READ, EDIT, ARRANGE, STRUCTURE_INSPECT),
        allowed_capabilities=(READ, EDIT, ARRANGE),
        verification=(STRUCTURAL, LAYOUT, RENDER),
    ),
    "compose_from_slides": PPTTaskDefinition(
        task_type="compose_from_slides",
        description="synthesize a new section from multiple existing sections while preserving originals",
        profile_name="create_deck",
        required_capabilities=(READ, EDIT, ARRANGE, STRUCTURE_INSPECT),
        allowed_capabilities=(READ, EDIT, ARRANGE),
        verification=(STRUCTURAL, LAYOUT, RENDER, IMMUTABILITY),
        mutation_policy=_LAYOUT_SCOPE,
    ),
    "source_grounded_build": PPTTaskDefinition(
        task_type="source_grounded_build",
        description="build an artifact grounded in multiple sources with traceable bindings",
        profile_name="source_grounded",
        required_capabilities=(READ, EDIT, STRUCTURE_INSPECT, RENDER_CAP, VISUAL_INSPECT),
        allowed_capabilities=(READ, EDIT),
        verification=(CONTENT_GROUNDING, STRUCTURAL, RENDER, VISUAL),
        mutation_scope="deck",
        mutation_policy=_DECK_SCOPE,
    ),
    "template_build": PPTTaskDefinition(
        task_type="template_build",
        description="generate a full artifact following a supplied template and reference style",
        profile_name="create_deck",
        required_capabilities=(READ, EDIT, ARRANGE, RENDER_CAP, VISUAL_INSPECT),
        allowed_capabilities=(READ, EDIT),
        verification=(STRUCTURAL, RENDER, VISUAL),
        mutation_scope="deck",
        mutation_policy=_DECK_SCOPE,
    ),
}

SKILL_SPECS: Dict[str, SkillSpec] = {t: d.to_skill() for t, d in TASK_DEFINITIONS.items()}
PROFILE_SPECS: Dict[str, DomainProfile] = {t: d.to_profile() for t, d in TASK_DEFINITIONS.items()}


def definition_for(task_type: str) -> PPTTaskDefinition:
    try:
        return TASK_DEFINITIONS[task_type]
    except KeyError:
        raise KeyError(f"unknown PPT task type: {task_type}") from None


__all__ = [
    "PPTTaskDefinition", "TASK_DEFINITIONS", "SKILL_SPECS", "PROFILE_SPECS",
    "definition_for", "READ", "EDIT", "STYLE", "RENDER_CAP", "VISUAL_INSPECT",
    "STRUCTURE_INSPECT", "ARRANGE",
]
