from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from pathlib import PurePosixPath


class Decision(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class PermissionResult:
    decision: Decision
    reason: str


_DESTRUCTIVE = re.compile(
    r"(^|[;&|]\s*)(rm\s+-(?:r|f|rf|fr)\b|del\s+/[sqf]|rmdir\s+/s|Remove-Item\b.*-(?:Recurse|Force)|format\b|shutdown\b|git\s+(?:reset\s+--hard|clean\s+-[a-z]*f))",
    re.IGNORECASE,
)
_EXTERNAL_WRITE = re.compile(r"\bgit\s+push\b", re.IGNORECASE)
_NETWORK = re.compile(r"\b(curl|wget|Invoke-WebRequest|git\s+(pull|fetch)|pip\s+install|npm\s+install|apt(?:-get)?\s+install)\b", re.IGNORECASE)


def path_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _safe_isolated_delete(command: str) -> bool:
    if any(operator in command for operator in (";", "&&", "||", "|", ">", "<")):
        return False
    try:
        parts = shlex.split(command, posix=True)
    except ValueError:
        return False
    if not parts or parts[0] != "rm":
        return False
    targets = [part for part in parts[1:] if not part.startswith("-")]
    if not targets:
        return False
    for target in targets:
        path = Path(target)
        posix = PurePosixPath(target.replace("\\", "/"))
        if path.is_absolute() or posix.is_absolute() or re.match(r"^[A-Za-z]:", target) or target in {".", "..", "~", ""} or ".." in posix.parts:
            return False
        if any(char in target for char in ("*", "?", "[", "]", "{", "}")):
            return False
    return True


def evaluate_shell(command: str, policy: str = "ask", isolated: bool = False) -> PermissionResult:
    if not command.strip():
        return PermissionResult(Decision.DENY, "empty command")
    if _DESTRUCTIVE.search(command):
        if not (isolated and policy == "allow" and _safe_isolated_delete(command)):
            return PermissionResult(Decision.DENY, "destructive command blocked")
        return PermissionResult(Decision.ALLOW, "scoped relative delete allowed inside isolated benchmark")
    if _EXTERNAL_WRITE.search(command):
        return PermissionResult(Decision.ASK, "external repository mutation requires approval")
    if _NETWORK.search(command) and not isolated:
        return PermissionResult(Decision.ASK, "network or package mutation requires approval")
    if policy == "deny":
        return PermissionResult(Decision.DENY, "shell disabled by policy")
    if policy == "ask":
        return PermissionResult(Decision.ASK, "shell execution requires approval")
    return PermissionResult(Decision.ALLOW, "allowed by command policy")
