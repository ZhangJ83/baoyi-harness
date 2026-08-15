"""Claude Code adapter: capability resolution -> SKILL.md frontmatter.

Resolution is harness/context aware: on Windows the render candidates prefer
PowerPoint COM; ``available_backends`` can override the preference.
"""
from __future__ import annotations

from typing import Sequence

from core.skill import SkillSpec

from adapters.base import HarnessAdapter
from adapters.implementations import ResolutionContext, resolve_implementations


class ClaudeCodeAdapter(HarnessAdapter):
    name = "claude_code"
    context = ResolutionContext(harness="claude_code", platform="windows")

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
            "allowed-tools: " + (", ".join(tools) if tools else "[]"),
            "---",
            "",
            f"# {spec.name}",
            "",
            spec.description,
            "",
            "## Required capabilities",
            "",
        ]
        lines += [f"- {cap}" for cap in spec.capabilities]
        if spec.verification_contract:
            lines += ["", "## Verification contract", "", "- " + ", ".join(spec.verification_contract)]
        if spec.mutation_scope:
            lines += ["", f"Mutation scope: {spec.mutation_scope}"]
        lines.append("")
        return "\n".join(lines)

    def render_tool_manifest(self, capability_ids: Sequence[str]) -> str:
        lines = ["Capability -> resolved tools", ""]
        for cap_id in capability_ids:
            impls = resolve_implementations(cap_id, self.context)
            primary = impls[0].tool
            alternates = ", ".join(i.tool for i in impls[1:])
            suffix = f" (alternates: {alternates})" if alternates else ""
            lines.append(f"- {cap_id} -> {primary}{suffix}")
        return "\n".join(lines)
