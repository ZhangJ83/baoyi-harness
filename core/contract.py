"""Task and output contracts produced by the generic compiler."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from core.verification import VerificationContract


@dataclass
class OutputContract:
    path: Optional[Path] = None
    required: bool = True


@dataclass
class TaskContract:
    task_type: str
    capabilities: tuple
    profile: Any
    output: OutputContract
    verification: VerificationContract
    mutation: Any = None  # domain-specialized scope/policy; fixed before execution
    metadata: Dict[str, Any] = field(default_factory=dict)
