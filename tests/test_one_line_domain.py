import os
from pathlib import Path

from agent.harness import Harness


def test_task_path_alone_is_classified_from_task_package(tmp_path, monkeypatch):
    task = tmp_path / "tasks" / "3-002"
    task.mkdir(parents=True)
    (task / "3.pptx").write_bytes(b"ppt-package-marker")
    (task / "task_card.md").write_text(
        "SOURCE: PPT-Eval\nCAPABILITY: precise text editing\n", encoding="utf-8"
    )
    monkeypatch.setenv("WORKSPACE", str(tmp_path))
    harness = object.__new__(Harness)
    harness.deck = None
    assert harness._is_ppt_task(r"完成 tasks\3-002") is True


def test_bare_task_id_is_classified_from_package_facts(tmp_path, monkeypatch):
    task = tmp_path / "tasks" / "style-task"
    task.mkdir(parents=True)
    (task / "deck.pptx").write_bytes(b"ppt-package-marker")
    monkeypatch.setenv("WORKSPACE", str(tmp_path))
    harness = object.__new__(Harness)
    harness.deck = None
    assert harness._is_ppt_task("style-task完成这个任务") is True


def test_binding_new_task_resets_stale_execution_state(tmp_path, monkeypatch):
    task = tmp_path / "tasks" / "style-task"
    task.mkdir(parents=True)
    (task / "deck.pptx").write_bytes(b"ppt-package-marker")
    monkeypatch.setenv("WORKSPACE", str(tmp_path))
    harness = object.__new__(Harness)
    from agent.events import EventBus
    from agent.runtime import RuntimeController
    from agent.session import Session
    from agent.state import RunState, RuntimePhase

    harness.state = RunState()
    harness.state.tool_calls = 159
    harness.state.phase = RuntimePhase.PRODUCE
    harness.messages = [{"role": "user", "content": "old task"}]
    harness.deck = object()
    harness.started = True
    harness.loaded_skills = {"old"}
    harness.skill_allowed_tools = set()
    harness.recorder = None
    harness._run_control = None
    harness.runtime = RuntimeController()
    harness.task_profile = None
    harness._last_planning_signature = None
    harness.controller_policy = "cegar_h"
    harness.events = EventBus()
    harness.session = Session()

    effective = harness._bind_task_context("style-task完成这个任务")
    assert effective.startswith("完成 tasks\\style-task")
    assert harness.state.tool_calls == 0
    assert harness.state.phase == RuntimePhase.INTAKE
    assert harness.deck is None
    assert harness.cancel_requested() is False
