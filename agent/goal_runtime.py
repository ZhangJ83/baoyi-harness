"""Durable long-horizon goals, separate from one-turn prompts and research logs."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4


@dataclass
class Goal:
    objective: str
    milestones: list[str]
    required_certificates: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex)
    status: str = "active"
    completed_milestones: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def complete(self, milestone: str) -> None:
        if milestone in self.milestones and milestone not in self.completed_milestones:
            self.completed_milestones.append(milestone)
            self.updated_at = datetime.now(timezone.utc).isoformat()


class GoalStore:
    def __init__(self, workspace: Path):
        self.path = workspace / ".xiaopu" / "goal.json"

    def load(self) -> Goal | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return Goal(**data)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def save(self, goal: Goal) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(goal), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()


def goal_from_contract(objective: str, contract) -> Goal:
    milestones = [stage.label for stage in getattr(contract, "stages", ())] + ["交付并确认完成条件"]
    return Goal(
        objective=objective.strip(),
        milestones=milestones,
        required_certificates=sorted(getattr(contract, "finish_certificates", ())),
    )

