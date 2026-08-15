"""Harness adapter contract and capability binding helpers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

from core.capability import get_capability
from core.skill import SkillSpec


@dataclass(frozen=True)
class CapabilityBinding:
    capability_id: str
    tool: str
    config: dict = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "config", dict(self.config or {}))


def resolve_bindings(
    capability_ids: Sequence[str], binding_table: Dict[str, Tuple[str, ...]]
) -> Tuple[CapabilityBinding, ...]:
    """Resolve capability ids through a vendor binding table, erroring on gaps."""
    bindings = []
    for cap_id in capability_ids:
        if cap_id not in binding_table:
            raise KeyError(f"no binding for capability {cap_id!r}")
        tools = binding_table[cap_id]
        if len(tools) == 1:
            bindings.append(CapabilityBinding(cap_id, tools[0]))
        else:
            bindings.append(CapabilityBinding(cap_id, tools[0], {"alternates": list(tools[1:])}))
    return tuple(bindings)


class HarnessAdapter(ABC):
    """Maps portable specs to one concrete harness's formats and tools."""

    name: str = "base"

    @abstractmethod
    def render_skill(self, spec: SkillSpec) -> str:
        ...

    @abstractmethod
    def render_tool_manifest(self, capability_ids: Sequence[str]) -> str:
        ...

    def validate(self, spec: SkillSpec) -> None:
        """Every required capability must exist in the generic registry."""
        for cap_id in (*spec.capabilities, *spec.allowed_capabilities):
            get_capability(cap_id)
