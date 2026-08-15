"""Generic transactional primitives.

The core defines baseline/allowed-mutation/postcondition and certificates.
What a scope field or a delta entry *means* is defined by domain packs.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Protocol, Tuple


@dataclass
class Baseline:
    artifact: Any
    digest: Optional[str] = None


@dataclass
class MutationScope:
    label: str = ""
    fields: Tuple[str, ...] = ()


@dataclass
class ImmutabilityPolicy:
    """What a mutation may touch and what it must never touch."""

    allow: Tuple[str, ...] = ()
    deny: Tuple[str, ...] = ()


@dataclass
class AllowedMutation:
    scope: MutationScope
    policy: Optional[ImmutabilityPolicy] = None


@dataclass
class Postcondition:
    description: str = ""
    predicate: Optional[Callable[[Any], bool]] = None

    def holds(self, artifact: Any) -> bool:
        if self.predicate is None:
            return True
        return bool(self.predicate(artifact))


class Delta(ABC):
    kind: str = "generic"

    @abstractmethod
    def summarize(self) -> str:
        ...


@dataclass
class Certificate:
    kind: str
    artifact_ref: str = ""
    epoch: int = 0
    passed: bool = True
    detail: Dict[str, Any] = field(default_factory=dict)

    def is_fresh(self, current_epoch: int) -> bool:
        return self.epoch == current_epoch


class Transaction(Protocol):
    def begin(self) -> None:
        ...

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
        ...
