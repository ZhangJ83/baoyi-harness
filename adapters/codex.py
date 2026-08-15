"""Codex adapter: capability resolution -> AGENTS.md + tools.json.

The Codex sandbox context prefers LibreOffice rendering over Windows COM even
when the same portable capability is rendered elsewhere with COM.
"""
from __future__ import annotations

import json
from typing import Sequence

from core.skill import SkillSpec

from adapters.base import HarnessAdapter
from adapters.implementations import ResolutionContext, resolve_primary


class CodexAdapter(HarnessAdapter):
    name = "codex"
    context = ResolutionContext(harness="codex", platform="linux")

    def render_skill(self, spec: SkillSpec) -> str:
        self.validate(spec)
        tool_manifest = {cap: resolve_primary(cap, self.context).tool for cap in spec.capabilities}
        return "\n".join([
            "# AGENTS.md",
            "",
            f"## Skill: {spec.name}",
            "",
            spec.description,
            "",
            "Required capabilities:",
            "",
            *[f"- {cap}" for cap in spec.capabilities],
            "",
            "# tools.json",
            json.dumps(tool_manifest, indent=2),
            "",
        ])

    def render_tool_manifest(self, capability_ids: Sequence[str]) -> str:
        payload = {cap: resolve_primary(cap, self.context).tool for cap in capability_ids}
        return json.dumps(payload, indent=2)
