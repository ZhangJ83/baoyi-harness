from pathlib import Path

import pytest

from agent.task_index import resolve_task


def _task(root: Path, agent: str, task_id: str) -> Path:
    task = root / "agent_workspaces" / "full13" / agent / "tasks" / task_id
    task.mkdir(parents=True)
    (task / "instruction.md").write_text("do it", encoding="utf-8")
    (task.parent.parent / "workspace_manifest.csv").write_text("task_id\n" + task_id, encoding="utf-8")
    return task


def test_workspace_index_prefers_owned_canonical_agent_workspace(tmp_path):
    _task(tmp_path, "claude-code", "demo-task")
    expected = _task(tmp_path, "xiaopuharness", "demo-task")
    _task(tmp_path, "xiaopuharness - 副本", "demo-task")
    assert resolve_task(tmp_path, "demo-task 完成这个task") == expected


def test_workspace_index_rejects_equal_ambiguous_candidates(tmp_path):
    _task(tmp_path, "alpha", "demo-task")
    _task(tmp_path, "beta", "demo-task")
    with pytest.raises(ValueError, match="多个同等级工作副本"):
        resolve_task(tmp_path, "demo-task")
