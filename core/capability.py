"""Namespaced capability registry.

Capabilities are vendor-neutral identifiers. Only adapters know what concrete
tool satisfies a capability in a given harness.
"""
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Capability:
    id: str
    description: str = ""


_CAPABILITIES: Dict[str, Capability] = {}


def register_capability(cap: Capability) -> None:
    if cap.id in _CAPABILITIES:
        raise ValueError(f"capability already registered: {cap.id}")
    _CAPABILITIES[cap.id] = cap


def get_capability(cap_id: str) -> Capability:
    try:
        return _CAPABILITIES[cap_id]
    except KeyError:
        raise KeyError(f"unknown capability: {cap_id}") from None


def all_capabilities() -> tuple:
    return tuple(sorted(_CAPABILITIES.values(), key=lambda c: c.id))
