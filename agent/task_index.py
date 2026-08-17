"""Workspace-level task package discovery and deterministic ownership ranking."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


IGNORED_PARTS = {".git", ".xiaopu", ".pytest_cache", "__pycache__", "output", "results"}


@dataclass(frozen=True)
class TaskCandidate:
    root: Path
    score: int


def _score(workspace: Path, task: Path) -> int:
    tasks_parent = task.parent
    agent_root = tasks_parent.parent
    score = 0
    if tasks_parent == workspace / "tasks":
        score += 100
    folded = str(agent_root).casefold()
    if any(k in folded for k in ("baoyi", "报一", "xiaopu", "小朴")):
        score += 40
    if any(k in agent_root.name.casefold() for k in ("baoyiharness", "baoyi-harness", "xiaopuharness")):
        score += 15
    if "副本" in agent_root.name or "copy" in agent_root.name.casefold():
        score -= 10
    if (agent_root / "workspace_manifest.csv").is_file():
        score += 20
    if (task / "instruction.md").is_file():
        score += 10
    if (task / "input").is_dir():
        score += 5
    return score


def find_task_candidates(workspace: Path, task_id: str, max_depth: int = 5) -> list[TaskCandidate]:
    workspace = workspace.resolve()
    found: list[TaskCandidate] = []
    direct = workspace / "tasks" / task_id
    if direct.is_dir():
        return [TaskCandidate(direct.resolve(), _score(workspace, direct))]

    # Compatibility bridge onto the generic core discovery. The legacy
    # container rules and ownership scoring stay authoritative; the traversal,
    # marker detection and deterministic ordering now come from core.discovery.
    from core.discovery import DiscoverySpec, discover_tasks

    containers = _task_containers(workspace)

    def scorer(task_dir: Path) -> tuple[float, tuple[str, ...]]:
        evidence = tuple(m for m in ("instruction.md", "task.toml") if (task_dir / m).is_file())
        return float(_score(workspace, task_dir)), evidence

    spec = DiscoverySpec(
        search_roots=tuple(containers),
        marker_files=(),
        excluded_dir_names=tuple(IGNORED_PARTS | {".pytest_cache"}),
        max_depth=2,
        scorer=scorer,
    )
    for candidate in discover_tasks(spec):
        if candidate.task_id != task_id:
            continue
        try:
            relative = candidate.root.parent.relative_to(workspace)
        except ValueError:
            continue
        if len(relative.parts) > max_depth or any(
            part in IGNORED_PARTS or part.startswith(".pytest") for part in relative.parts
        ):
            continue
        found.append(TaskCandidate(candidate.root.resolve(), _score(workspace, candidate.root)))
    return sorted(found, key=lambda item: (-item.score, str(item.root).casefold()))


def _task_containers(workspace: Path) -> list[Path]:
    """Find conventional task containers without traversing artifact trees."""
    candidates = [workspace / "tasks"]
    agents = workspace / "agent_workspaces"
    if agents.is_dir():
        candidates.extend(agents.glob("*/tasks"))
        candidates.extend(agents.glob("*/*/tasks"))
    # Generic projects get a bounded two-level fallback only.
    candidates.extend(workspace.glob("*/tasks"))
    candidates.extend(workspace.glob("*/*/tasks"))
    unique: dict[str, Path] = {}
    for path in candidates:
        try:
            relative_parts = path.relative_to(workspace).parts
        except ValueError:
            continue
        if path.is_dir() and not any(part in IGNORED_PARTS or part.startswith(".pytest") for part in relative_parts):
            unique[str(path.resolve()).casefold()] = path.resolve()
    return list(unique.values())


def resolve_task(workspace: Path, request: str) -> Path | None:
    folded = request.replace("/", "\\").casefold()
    ids: set[str] = set()
    # Collect task ids from every valid task-container directory. A workspace
    # may have a root ``tasks`` plus agent_workspaces containers; the bare
    # task-id contract must resolve across all of them, not only the root one.
    for tasks_dir in _task_containers(workspace):
        try:
            relative = tasks_dir.relative_to(workspace)
        except ValueError:
            continue
        if len(relative.parts) <= 5 and not any(part in IGNORED_PARTS or part.startswith(".pytest") for part in relative.parts):
            try:
                ids.update(path.name for path in tasks_dir.iterdir() if path.is_dir())
            except OSError:
                continue
    mentioned = [task_id for task_id in ids if task_id.casefold() in folded]
    if not mentioned:
        return None
    task_id = max(mentioned, key=len)
    candidates = find_task_candidates(workspace, task_id)
    if not candidates:
        return None
    best = candidates[0]
    tied = [item for item in candidates if item.score == best.score]
    if len(tied) > 1:
        paths = "\n".join(f"- {item.root}" for item in tied)
        raise ValueError(f"任务 {task_id!r} 存在多个同等级工作副本，请先选择具体工作区：\n{paths}")
    return best.root
