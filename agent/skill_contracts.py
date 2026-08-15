"""Runtime loader for trajectory-derived Skill contracts."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "analysis" / "trajectory_reverse_engineering" / "skill_contracts.json"
)


@lru_cache(maxsize=1)
def load_contracts() -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        skills = payload.get("skills", {})
        return skills if isinstance(skills, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def contract_for(skill: str) -> dict[str, Any]:
    return load_contracts().get(skill, {})


def visible_tools_for(skill: str, phase: str, repairing: bool = False) -> set[str]:
    contract = contract_for(skill)
    tools = set(contract.get("visible_tools") or ())
    if not tools:
        return set()
    if phase in {"intake", "understand"}:
        return tools & {"ppt_open", "ppt_inspect", "finish"}
    if phase == "verify" and not repairing:
        return tools & {"ppt_save", "ppt_check", "finish"}
    if phase in {"deliver", "stopped"}:
        return {"finish"}
    return tools

