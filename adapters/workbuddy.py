"""WorkBuddy adapter: capability resolution -> native PPT tool profile JSON."""
from __future__ import annotations

import json
from typing import Sequence

from core.skill import SkillSpec

from adapters.base import HarnessAdapter
from adapters.implementations import ResolutionContext, resolve_primary


class WorkBuddyAdapter(HarnessAdapter):
    name = "workbuddy"
    context = ResolutionContext(harness="workbuddy", platform="any")

    def render_skill(self, spec: SkillSpec) -> str:
        self.validate(spec)
        tools = sorted({resolve_primary(cap, self.context).tool for cap in spec.capabilities})
        payload = {
            "skill": spec.name,
            "description": spec.description,
            "capabilities": list(spec.capabilities),
            "tools": tools,
            "verification_contract": list(spec.verification_contract),
            "mutation_scope": spec.mutation_scope,
        }
        return json.dumps(payload, indent=2)

    def render_tool_manifest(self, capability_ids: Sequence[str]) -> str:
        payload = [
            {"capability": cap, "tool": resolve_primary(cap, self.context).tool}
            for cap in capability_ids
        ]
        return json.dumps(payload, indent=2)
