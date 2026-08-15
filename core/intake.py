"""Generic source intake: registration, hashing, and budgeted briefing.

The core registers *sources*. Interpreting what a binary source means (a
document tree, a workbook, a hierarchy) is a domain pack's job.
"""
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Optional, Sequence

DEFAULT_KIND_MAP: Dict[str, str] = {
    ".md": "text",
    ".txt": "text",
    ".json": "text",
    ".yaml": "text",
    ".yml": "text",
    ".csv": "text",
    ".html": "text",
}


@dataclass
class SourceRegistration:
    path: Path
    sha256: str
    kind: str
    size: int
    text: str = ""


@dataclass
class IntakePolicy:
    max_total_chars: int = 12000
    max_per_source: int = 4000


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def discover_sources(paths: Iterable[Path], kind_map: Optional[Dict[str, str]] = None) -> list[SourceRegistration]:
    """Register files. Text kinds get extracted content; everything gets a hash."""
    effective_map = dict(DEFAULT_KIND_MAP)
    if kind_map:
        effective_map.update(kind_map)
    registrations: list[SourceRegistration] = []
    seen: set[str] = set()
    for raw in paths:
        path = Path(raw)
        if not path.is_file():
            continue
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        data = path.read_bytes()
        kind = effective_map.get(path.suffix.lower(), "binary")
        text = ""
        if kind == "text":
            text = data.decode("utf-8", errors="replace")
        registrations.append(SourceRegistration(path=path, sha256=_sha256(data),
                                                kind=kind, size=len(data), text=text))
    registrations.sort(key=lambda r: (r.path.name.lower(), str(r.path).lower()))
    return registrations


def balance_brief(regs: Sequence[SourceRegistration], policy: Optional[IntakePolicy] = None) -> str:
    """Deterministic budgeted excerpt of all text sources.

    Each source is capped by ``max_per_source``; the joined brief is capped by
    ``max_total_chars``. Binary sources are represented by a single metadata line.
    """
    policy = policy or IntakePolicy()
    parts: list[str] = []
    for reg in regs:
        if reg.text:
            body = reg.text if len(reg.text) <= policy.max_per_source \
                else reg.text[: policy.max_per_source] + "\n...(per-source limit)"
            parts.append(f"## {reg.path.name}\n{body}\n")
        else:
            parts.append(f"## {reg.path.name} [{reg.kind}, {reg.size} bytes]\n")
    brief = "\n".join(parts)
    if len(brief) > policy.max_total_chars:
        suffix = "\n...(brief budget reached)"
        brief = brief[: max(0, policy.max_total_chars - len(suffix))] + suffix
    return brief
