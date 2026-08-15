from unittest.mock import patch

from prompt_toolkit.document import Document

from agent.cli import COMMANDS, CommandCompleter, XiaopuCLI
from agent.events import EventKind, RuntimeEvent
from agent.harness import Harness


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


def test_prompt_session_is_constructible():
    cli = XiaopuCLI.__new__(XiaopuCLI)
    cli._theme = "dark"
    captured = {}

    class FakePrompt:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    with patch("agent.cli.PromptSession", FakePrompt):
        assert cli._make_prompt() is not None
    assert captured["multiline"] is True


def test_repeated_identical_tool_errors_render_only_once():
    cli = XiaopuCLI.__new__(XiaopuCLI)
    cli._process_view = "balanced"
    cli._latest_activity = []
    cli._trajectory = []
    cli._last_tool_error = None
    output = "TOOL ERROR (Example): failed"
    with patch("agent.cli.console") as fake_console:
        cli._on_tool("read_file", '{"path":"x.md"}', output)
        cli._on_tool("read_file", '{"path":"x.md"}', output)
    assert len(cli._latest_activity) == 1


def test_cli_constructs_harness_in_interactive_mode():
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
        patch("agent.cli.Harness", return_value=fake_harness) as harness_cls,
        patch("agent.cli.config.provider_api_key", return_value="key"),
        patch.object(XiaopuCLI, "_make_prompt", return_value=object()),
    ):
        XiaopuCLI()
    harness_cls.assert_called_once_with(model=None, interactive=True)


def test_cli_renders_plan_and_counts_canonical_ppt_check():
    cli = XiaopuCLI.__new__(XiaopuCLI)
    cli._process_view = "balanced"
    cli._latest_activity = []
    cli._stream_counts = {"decisions": 0, "tools": 0, "verifications": 0}
    with patch("agent.cli.console") as fake_console:
        cli._on_event(RuntimeEvent(EventKind.TASK_PLAN, {"items": [
            {"id": "1", "content": "保存最终 PPTX", "status": "in_progress"}
        ]}))
        cli._on_event(RuntimeEvent(EventKind.TOOL_COMPLETED, {"tool": "ppt_check"}))
    assert fake_console.print.called
    assert any("计划与进度" in line for line in cli._latest_activity)
    assert cli._stream_counts["verifications"] == 1


def test_operational_plan_stays_visible_in_quiet_mode():
    cli = XiaopuCLI.__new__(XiaopuCLI)
    cli._process_view = "quiet"
    cli._latest_activity = []
    cli._stream_counts = {"decisions": 0, "tools": 0, "verifications": 0}
    cli._on_event(RuntimeEvent(EventKind.TASK_PLAN, {"items": [
        {"id": "1", "content": "定位目标并执行最小修改", "status": "in_progress"}
    ]}))
    assert any("计划与进度" in line for line in cli._latest_activity)
