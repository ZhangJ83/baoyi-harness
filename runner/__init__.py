"""Composition root: assemble a portable harness from core + a domain pack + a vendor adapter.

The runner never knows PPT specifics. It wires the three layers through the
public contracts and leaves concrete vendor mapping to the adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core import (
    DomainPack,
    SkillSpec,
    Task,
    TaskContract,
    compile_task,
)
from adapters.base import HarnessAdapter
from .runtime import CompiledRuntimeTask, compile_runtime_task


@dataclass
class HarnessAssembly:
    """Fully assembled portable harness for one domain and one vendor adapter."""

    domain_pack: DomainPack
    adapter: HarnessAdapter
    skills: dict[str, SkillSpec] = field(default_factory=dict)
    contracts: dict[str, TaskContract] = field(default_factory=dict)

    def compile(self, task: Task) -> TaskContract:
        contract = compile_task(task, self.domain_pack)
        self.contracts[task.id] = contract
        return contract

    def render_skill(self, name: str) -> str:
        return self.adapter.render_skill(self.skills[name])

    def render_tool_manifest(self, capability_ids: tuple[str, ...]) -> str:
        return self.adapter.render_tool_manifest(capability_ids)


def assemble(domain: str = "ppt", adapter: str = "claude_code") -> HarnessAssembly:
    """Build an assembly for a registered domain pack and adapter.

    Domain packs and adapters are looked up through the registries maintained by
    :mod:`domains` and :mod:`adapters`. Imports are deferred so this module has
    no static domain knowledge.
    """
    from core.skill import SKILLS
    from adapters import get_adapter
    from domains import get_domain_pack

    return HarnessAssembly(
        domain_pack=get_domain_pack(domain),
        adapter=get_adapter(adapter),
        skills=dict(SKILLS),
    )
