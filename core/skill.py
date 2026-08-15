"""Portable skill specification.

``SkillSpec`` is the internal standard. Vendor formats (frontmatter, config
files) are produced exclusively by adapters, never by the core or domain packs.
"""
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class SkillSpec:
    name: str
    description: str
    capabilities: tuple
    allowed_capabilities: tuple = ()
    required_inputs: tuple = ()
    verification_contract: tuple = ()
    mutation_scope: str = "artifact"
    metadata: Dict[str, Any] = field(default_factory=dict)


SKILLS: Dict[str, SkillSpec] = {}


def register_skill(spec: SkillSpec) -> None:
    if spec.name in SKILLS:
        raise ValueError(f"skill already registered: {spec.name}")
    SKILLS[spec.name] = spec


def get_skill(name: str) -> SkillSpec:
    try:
        return SKILLS[name]
    except KeyError:
        raise KeyError(f"unknown skill: {name}") from None
