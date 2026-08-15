"""Controlled workspace discovery. The core knows markers and scoring, not task domains."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Tuple


@dataclass
class TaskCandidate:
    task_id: str
    root: Path
    confidence: float
    evidence: Tuple[str, ...] = ()


@dataclass
class DiscoverySpec:
    search_roots: Tuple[Path, ...]
    marker_files: Tuple[str, ...] = ("instruction.md", "task.toml")
    excluded_dir_names: Tuple[str, ...] = ()
    max_depth: Optional[int] = 6
    scorer: Optional[Callable[[Path], Tuple[float, Tuple[str, ...]]]] = None


def _walk(root: Path, spec: DiscoverySpec) -> list[Path]:
    """Recursive but bounded walk that prunes excluded container names."""
    hits: list[Path] = []
    stack = [(root, 0)]
    seen: set[str] = set()
    while stack:
        current, depth = stack.pop()
        try:
            resolved = str(current.resolve())
        except OSError:
            resolved = str(current)
        if resolved in seen:
            continue
        seen.add(resolved)
        if spec.max_depth is not None and depth > spec.max_depth:
            continue
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue
        if spec.marker_files:
            has_marker = any((current / m).is_file() for m in spec.marker_files)
        else:
            # An empty marker list means "every directory is a candidate".
            has_marker = True
        if has_marker:
            hits.append(current)
        for entry in entries:
            if not entry.is_dir():
                continue
            if entry.name in spec.excluded_dir_names:
                continue
            stack.append((entry, depth + 1))
    return hits


def discover_tasks(spec: DiscoverySpec) -> list[TaskCandidate]:
    """Discover candidate task containers and return them deterministically ordered."""
    candidates: list[TaskCandidate] = []
    for root in spec.search_roots:
        if not root.is_dir():
            continue
        for task_dir in _walk(root, spec):
            evidence: Tuple[str, ...] = tuple(m for m in spec.marker_files if (task_dir / m).is_file())
            if spec.scorer is not None:
                confidence, extra_evidence = spec.scorer(task_dir)
                evidence = tuple(dict.fromkeys((*evidence, *extra_evidence)))
            else:
                confidence = 1.0
            task_id = task_dir.name
            candidates.append(TaskCandidate(task_id=task_id, root=task_dir,
                                            confidence=confidence, evidence=evidence))
    candidates.sort(key=lambda c: (c.task_id.lower(), str(c.root).lower()))
    return candidates
