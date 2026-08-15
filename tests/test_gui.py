from agent.gui import AgentGUI, build_parser


def test_gui_has_independent_native_entry():
    parser = build_parser()
    assert parser.prog == "agent-gui"
    args = parser.parse_args(["--workspace", "demo", "--model", "m"])
    assert args.workspace == "demo"
    assert args.model == "m"


def test_gui_tool_event_uses_runtime_tool_field_not_missing_name():
    gui = AgentGUI.__new__(AgentGUI)
    gui.tool_rows = {}
    gui.tool_payloads = {}
    observed = {}
    gui.tool_tree = type("Tree", (), {
        "insert": lambda self, *a, **kw: observed.setdefault("values", kw["values"]) or "row",
        "selection": lambda self: (),
    })()
    gui._upsert_tool({"call_id": "1", "tool": "list_dir", "arguments": "{}"}, "运行中")
    assert observed["values"] == ("运行中", "list_dir")


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
