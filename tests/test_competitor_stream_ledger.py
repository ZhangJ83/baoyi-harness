import json

from agent.competitor_stream_ledger import normalize_claude, normalize_codex


def line(payload):
    return json.dumps(payload)


def test_claude_stream_has_complete_observable_ledger():
    rows = [
        line({"type": "assistant", "message": {"usage": {"input_tokens": 10, "output_tokens": 3}, "content": [{"type": "tool_use", "id": "t1"}]}}),
        line({"type": "assistant", "message": {"usage": {"input_tokens": 7, "output_tokens": 2}, "content": [{"type": "text", "text": "done"}]}}),
        line({"type": "result", "usage": {"input_tokens": 17, "output_tokens": 5}}),
    ]
    result = normalize_claude(rows)
    assert result["input_tokens"] == 17
    assert result["output_tokens"] == 5
    assert result["tool_calls"] == 1
    assert result["steps"] == 2
    assert result["complete"] is True


def test_claude_stream_fails_closed_on_malformed_or_unfinished_output():
    result = normalize_claude(["not-json"])
    assert result["complete"] is False
    assert result["parse_errors"]
    assert "no final result event" in result["observability_gaps"]


def test_codex_stream_records_tokens_and_tools_but_not_hidden_steps():
    rows = [
        line({"type": "turn.started"}),
        line({"type": "item.started", "item": {"id": "1", "type": "command_execution"}}),
        line({"type": "item.completed", "item": {"id": "1", "type": "command_execution"}}),
        line({"type": "turn.completed", "usage": {"input_tokens": 23, "cached_input_tokens": 4, "output_tokens": 6}}),
    ]
    result = normalize_codex(rows)
    assert result["input_tokens"] == 23
    assert result["output_tokens"] == 6
    assert result["tool_calls"] == 1
    assert result["steps"] is None
    assert result["complete"] is False
    assert any("step count" in gap for gap in result["observability_gaps"])


def test_codex_stream_rejects_missing_final_usage():
    result = normalize_codex([line({"type": "turn.started"})])
    assert result["complete"] is False
    assert "no turn.completed usage event" in result["observability_gaps"]
