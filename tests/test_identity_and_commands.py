from unittest.mock import patch

from prompt_toolkit.document import Document

from agent.harness import Harness
from agent.tui import COMMANDS, CommandCompleter, XiaopuTerminalUI
from agent.events import EventKind, RuntimeEvent


def test_system_prompt_anchors_xiaopu_identity():
    harness = Harness.__new__(Harness)
    harness.controller_policy = "cegar_h"
    harness.loaded_skills = set()
    text = harness._system_prompt("explain a function")
    assert "(Xiaopu)" in text
    assert "Never identify yourself as Claude" in text
    assert "Task profile / capability catalog" in text


def test_slash_command_menu_exposes_all_supported_commands():
    assert "/doctor" in COMMANDS
    assert "/verify" in COMMANDS
    assert "/exit" in COMMANDS
    assert COMMANDS["/verify"]
    assert "/goal" in COMMANDS


def test_slash_completion_includes_description():
    choices = list(CommandCompleter().get_completions(Document("/ver"), None))
    assert len(choices) == 1
    assert choices[0].text == "/verify"
    assert choices[0].display_meta


def test_prompt_key_bindings_are_constructible():
    ui = XiaopuTerminalUI.__new__(XiaopuTerminalUI)
    ui._mouse_input = False
    captured = {}

    class FakePrompt:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.layout = type("Layout", (), {"current_window": type("Window", (), {})()})()

    with patch("agent.tui.PromptSession", FakePrompt):
        assert ui._make_prompt() is not None
    assert captured["reserve_space_for_menu"] == 0


def test_repeated_identical_tool_errors_render_only_once():
    ui = XiaopuTerminalUI.__new__(XiaopuTerminalUI)
    ui._reasoning_view = "summary"
    ui._latest_activity = []
    ui._last_tool_error = None
    output = "TOOL ERROR (Example): failed"
    with patch("agent.tui.console") as fake_console:
        ui._on_tool("read_file", '{"path":"x.md"}', output)
        ui._on_tool("read_file", '{"path":"x.md"}', output)
    assert fake_console.print.call_count == 3
    assert len(ui._latest_activity) == 1
    assert "动作：读取" in ui._latest_activity[0]


def test_tui_constructs_harness_in_interactive_mode():
    fake_harness = type(
        "FakeHarness",
        (),
        {
            "llm": type("LLM", (), {"model": "fake"})(),
            "attach_printer": lambda self, printer: None,
            "subscribe": lambda self, callback: None,
        },
    )()
    with (
        patch("agent.tui.Harness", return_value=fake_harness) as harness_cls,
        patch("agent.tui.config.provider_api_key", return_value="key"),
        patch.object(XiaopuTerminalUI, "_make_prompt", return_value=object()),
    ):
        XiaopuTerminalUI()
    harness_cls.assert_called_once_with(model=None, interactive=True)


def test_tui_renders_plan_and_counts_canonical_ppt_check():
    ui = XiaopuTerminalUI.__new__(XiaopuTerminalUI)
    ui._reasoning_view = "summary"
    ui._latest_activity = []
    ui._stream_counts = {"decisions": 0, "tools": 0, "verifications": 0, "repairs": 0}
    with patch("agent.tui.console") as fake_console:
        ui._on_event(RuntimeEvent(EventKind.TASK_PLAN, {"items": [
            {"id": "1", "content": "保存最终 PPTX", "status": "in_progress"}
        ]}))
        ui._on_event(RuntimeEvent(EventKind.TOOL_COMPLETED, {"tool": "ppt_check"}))
    assert fake_console.print.called
    assert "计划与进度" in ui._latest_activity[-1]
    assert ui._stream_counts["verifications"] == 1


def test_operational_plan_remains_visible_when_process_details_are_hidden():
    ui = XiaopuTerminalUI.__new__(XiaopuTerminalUI)
    ui._reasoning_view = "hidden"
    ui._latest_activity = []
    ui._stream_counts = {"decisions": 0, "tools": 0, "verifications": 0, "repairs": 0}
    with patch("agent.tui.console") as fake_console:
        ui._on_event(RuntimeEvent(EventKind.TASK_PLAN, {"items": [
            {"id": "1", "content": "定位目标并执行最小修改", "status": "in_progress"}
        ]}))
    assert fake_console.print.called
