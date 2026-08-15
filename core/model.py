"""Generic harness core: domain-free models shared by every domain pack."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Task:
    """One unit of work. The core knows nothing about what an artifact is made of."""

    id: str
    instruction: str
    sources: tuple = field(default_factory=tuple)
    output: Optional[Path] = None

    def __post_init__(self) -> None:
        self.sources = tuple(Path(s) for s in self.sources)
        if self.output is not None:
            self.output = Path(self.output)


@dataclass
class Artifact:
    """A produced or consumed file. ``ir`` is filled by registered domain builders."""

    path: Path
    kind: str = ""
    ir: Any = None
