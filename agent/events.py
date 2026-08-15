"""Thread-safe runtime event stream shared by TUI, recorder, and tests."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import threading
from typing import Any, Callable


class EventKind(str, Enum):
    TURN_STARTED = "turn_started"
    TASK_PROFILED = "task_profiled"
    TASK_PLAN = "task_plan"
    GOAL_UPDATED = "goal_updated"
    PLANNING_DECISION = "planning_decision"
    PROGRESS_UPDATED = "progress_updated"
    CONTROLLER_DECISION = "controller_decision"
    MODEL_RESPONSE = "model_response"
    TOOL_STARTED = "tool_started"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    PHASE_CHANGED = "phase_changed"
    TURN_COMPLETED = "turn_completed"
    TURN_INTERRUPTED = "turn_interrupted"


@dataclass(frozen=True)
class RuntimeEvent:
    kind: EventKind
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[Callable[[RuntimeEvent], None]] = []
        self._lock = threading.RLock()

    def subscribe(self, callback: Callable[[RuntimeEvent], None]) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)
        return unsubscribe

    def publish(self, kind: EventKind, **payload: Any) -> RuntimeEvent:
        event = RuntimeEvent(kind, payload)
        with self._lock:
            subscribers = tuple(self._subscribers)
        for callback in subscribers:
            try:
                callback(event)
            except Exception:
                # Observability must never break artifact execution.
                continue
        return event
