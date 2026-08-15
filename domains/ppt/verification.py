"""PPT verification policy: domain kinds and per-task-type contracts.

The per-task contracts are generated from PPTTaskDefinition, the single source
of truth. This module owns only the kind vocabulary.
"""
from __future__ import annotations

from core.verification import VerificationContract

STRUCTURAL = "structural"
RENDER = "render"
VISUAL = "visual"
CONTENT_GROUNDING = "content_grounding"
LAYOUT = "layout"
IMMUTABILITY = "immutability"

ALL_KINDS = (STRUCTURAL, RENDER, VISUAL, CONTENT_GROUNDING, LAYOUT, IMMUTABILITY)


def policy_table() -> dict:
    """Derived policy table; never hand-maintained."""
    from domains.ppt.task_definition import TASK_DEFINITIONS

    return {task_type: definition.verification for task_type, definition in TASK_DEFINITIONS.items()}


def verification_policy(task_type: str) -> VerificationContract:
    """Map a PPT task type to its required evidence kinds."""
    from domains.ppt.task_definition import definition_for

    return definition_for(task_type).to_verification_contract()
