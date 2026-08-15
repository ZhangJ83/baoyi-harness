"""PPT profiles: family-level views generated from the task definitions.

``profile_for(task_type)`` returns the authoritative per-task profile derived
from PPTTaskDefinition. The five family profiles are unions of their member
task definitions, computed once -- no hand-maintained capability lists.
"""
from __future__ import annotations

from core.compiler import DomainProfile

from domains.ppt.task_definition import PROFILE_SPECS, TASK_DEFINITIONS

FAMILY_MEMBERS = {
    "edit_existing": ("atomic_edit", "atomic_style"),
    "create_deck": ("element_creation", "diagram_composition", "compose_from_slides", "template_build"),
    "layout_reflow": ("layout_reflow",),
    "source_grounded": ("source_grounded_build",),
    # Reserved family: every task whose contract includes immutability feeds it.
    "repair_deck": tuple(
        t for t, d in TASK_DEFINITIONS.items() if "immutability" in d.verification
    ),
}

PROFILE_FOR_TASK_TYPE = {t: d.profile_name for t, d in TASK_DEFINITIONS.items()}


def _union_capabilities(members) -> tuple:
    caps: list[str] = []
    for member in members:
        for cap in TASK_DEFINITIONS[member].required_capabilities:
            if cap not in caps:
                caps.append(cap)
    return tuple(caps)


def _union_verification(members) -> tuple:
    kinds: list[str] = []
    for member in members:
        for kind in TASK_DEFINITIONS[member].verification:
            if kind not in kinds:
                kinds.append(kind)
    return tuple(kinds)


PROFILES = {
    family: DomainProfile(
        name=family,
        capabilities=_union_capabilities(members),
        verification=_union_verification(members),
    )
    for family, members in FAMILY_MEMBERS.items()
}


def profile_for(task_type: str) -> DomainProfile:
    """Authoritative per-task profile, generated from the task definition."""
    try:
        return PROFILE_SPECS[task_type]
    except KeyError:
        raise KeyError(f"unknown PPT task type: {task_type}") from None


def family_profile(family: str) -> DomainProfile:
    try:
        return PROFILES[family]
    except KeyError:
        raise KeyError(f"unknown PPT profile family: {family}") from None
