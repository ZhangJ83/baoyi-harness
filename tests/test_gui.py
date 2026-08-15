from agent.gui import AgentGUI, build_parser


def test_gui_has_independent_native_entry():
    parser = build_parser()
    assert parser.prog == "agent-gui"
    args = parser.parse_args(["--workspace", "demo", "--model", "m"])
    assert args.workspace == "demo"
    assert args.model == "m"


def test_gui_tool_start_event_appends_to_timeline():
    gui = AgentGUI.__new__(AgentGUI)
    gui.activity_visible = True
    gui.tool_log_lines = []
    gui._trajectory = []
    gui.tool_started_count = 0
    gui.tool_completed_count = 0
    gui.tool_failed_count = 0
    gui.live_action = type("Value", (), {"set": lambda self, value: None})()
    gui.live_phase = type("Value", (), {"set": lambda self, value: None})()
    gui.live_counts = type("Value", (), {"set": lambda self, value: None})()
    gui.trajectory_box = type("Box", (), {
        "configure": lambda self, *a, **kw: None,
        "insert": lambda self, *a, **kw: None,
        "see": lambda self, *a: None,
    })()

    from agent.events import EventKind, RuntimeEvent
    gui._show_event(RuntimeEvent(EventKind.TOOL_STARTED, {"tool": "list_dir", "arguments": "{}"}))
    assert "▸ list_dir" in gui.tool_log_lines[0]
    assert "▸ list_dir" in gui._trajectory[0]


def test_gui_live_counts_report_current_execution_state():
    gui = AgentGUI.__new__(AgentGUI)
    gui.tool_started_count = 3
    gui.tool_completed_count = 2
    gui.tool_failed_count = 1
    captured = {}
    gui.live_counts = type("Value", (), {"set": lambda self, value: captured.setdefault("value", value)})()
    gui._refresh_counts()
    assert captured["value"] == "工具 3 · 完成 2 · 失败 1"


def test_readonly_output_allows_copy_and_blocks_typing():
    bindings = {}
    widget = type("Widget", (), {
        "bind": lambda self, name, callback: bindings.setdefault(name, callback),
        "tag_add": lambda self, *args: None,
    })()
    AgentGUI._make_readonly_selectable(widget)
    event = type("Event", (), {})()
    event.state, event.keysym = 0, "x"
    assert bindings["<KeyPress>"](event) == "break"
    event.state, event.keysym = 4, "c"
    assert bindings["<KeyPress>"](event) is None


def test_send_requires_text_and_uses_worker_thread():
    from unittest.mock import patch

    gui = AgentGUI.__new__(AgentGUI)
    gui.running = False
    gui.input = type("Input", (), {
        "get": lambda self, *a: "   ",
        "delete": lambda self, *a: None,
    })()
    gui._append_chat = lambda *a, **kw: None
    gui._set_running = lambda *a: None
    with patch("agent.gui.threading.Thread") as thread:
        gui._send()
        thread.assert_not_called()
