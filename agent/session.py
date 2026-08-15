"""Typed session/turn results layered behind the backward-compatible Harness."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class StopReason(str, Enum):
    END_TURN = "end_turn"
    FINISHED = "finished"
    INTERRUPTED = "interrupted"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NO_PROGRESS = "no_progress"
    MAX_STEPS = "max_steps"
    ERROR = "error"


@dataclass(frozen=True)
class TurnOutcome:
    text: str
    stop_reason: StopReason
    turn_id: str = field(default_factory=lambda: uuid4().hex)
    tool_calls: int = 0
    total_tokens: int = 0
    mutation_epoch: int = 0
    phase: str = "intake"
    artifact: str | None = None


@dataclass
class Session:
    id: str = field(default_factory=lambda: uuid4().hex)
    turns: list[TurnOutcome] = field(default_factory=list)

    def append(self, outcome: TurnOutcome) -> None:
        self.turns.append(outcome)
