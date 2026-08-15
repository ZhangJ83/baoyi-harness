"""Artifact-level indirection: the core only knows an artifact *may* have a domain IR."""
from pathlib import Path
from typing import Any, Callable, Dict, Protocol, runtime_checkable

from core.model import Artifact


@runtime_checkable
class ArtifactIR(Protocol):
    """A domain-specific structured view of an artifact."""

    kind: str

    def summary(self) -> str:
        ...


IR_BUILDERS: Dict[str, Callable[[Path], Any]] = {}


def register_ir_builder(kind: str, builder: Callable[[Path], Any]) -> None:
    """Register a domain IR builder. Duplicate kinds are rejected."""
    if kind in IR_BUILDERS:
        raise ValueError(f"IR builder already registered for kind {kind!r}")
    IR_BUILDERS[kind] = builder


def build_ir(artifact: Artifact) -> Any:
    """Build the domain IR for an artifact, or ``None`` when no builder is registered."""
    builder = IR_BUILDERS.get(artifact.kind)
    if builder is None:
        return None
    artifact.ir = builder(artifact.path)
    return artifact.ir
