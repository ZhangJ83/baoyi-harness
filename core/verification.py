"""Generic verification requirements, evidence, and freshness semantics."""
from dataclasses import dataclass, field
from typing import Any, Dict, Tuple


@dataclass
class VerificationRequirement:
    kind: str
    critical: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Evidence:
    kind: str
    epoch: int
    passed: bool
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationContract:
    requirements: Tuple[VerificationRequirement, ...] = ()

    def required_kinds(self) -> tuple:
        return tuple(r.kind for r in self.requirements)

    @classmethod
    def from_kinds(cls, kinds) -> "VerificationContract":
        return cls(tuple(VerificationRequirement(kind=k) for k in kinds))


def is_fresh(evidence: Evidence, current_epoch: int) -> bool:
    """Freshness is epoch identity: anything from an older epoch is stale."""
    return evidence.epoch == current_epoch
