"""OpenCode adapter: capability resolution -> OpenCode-style skill file."""
from __future__ import annotations

from typing import Sequence

from core.skill import SkillSpec

from adapters.base import HarnessAdapter
from adapters.implementations import ResolutionContext, resolve_implementations


class OpenCodeAdapter(HarnessAdapter):
    name = "opencode"
    context = ResolutionContext(harness="opencode", platform="windows")

    def _resolved_tools(self, capability_ids: Sequence[str]) -> set:
        tools: set = set()
        for cap_id in capability_ids:
            for impl in resolve_implementations(cap_id, self.context):
                tools.add(impl.tool)
        return tools

    def render_skill(self, spec: SkillSpec) -> str:
        self.validate(spec)
        tools = sorted(self._resolved_tools(spec.capabilities))
        lines = [
            "---",
            f"name: {spec.name}",
            f"description: {spec.description}",
            "tools: " + (", ".join(tools) if tools else "[]"),
            "---",
            "",
            f"# {spec.name}",
            "",
            spec.description,
            "",
        ]
        lines += [f"- capability: {cap}" for cap in spec.capabilities]
        if spec.verification_contract:
            lines += ["- verification: " + ", ".join(spec.verification_contract)]
        lines.append("")
        return "\n".join(lines)

    def render_tool_manifest(self, capability_ids: Sequence[str]) -> str:
        lines = ["tools:"]
        for cap_id in capability_ids:
            impls = resolve_implementations(cap_id, self.context)
            lines.append(f"  - {cap_id}: {impls[0].tool}")
        return "\n".join(lines)
