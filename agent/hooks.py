from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ToolEvent:
    name: str
    arguments: str
    output: str | None = None


PreToolHook = Callable[[ToolEvent], str]
PostToolHook = Callable[[ToolEvent], str]
