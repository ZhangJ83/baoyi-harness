import json

import pytest

pytest.importorskip("terminal_bench")

from agent.budgeted_installed_agents import HOOK_CONFIG, BudgetedClaudeCodeAgent, BudgetedCodexAgent
from terminal_bench.agents.failure_mode import FailureMode


def write_common(logs, output_tokens=3):
    (logs / "generation_budget_gateway.json").write_text(
        json.dumps({"committed_output_tokens": output_tokens, "violations": []}), encoding="utf-8"
    )
    (logs / "tool_budget_hook.json").write_text(
        json.dumps({"allowed": [{"tool_use_id": "t1"}], "denied": []}), encoding="utf-8"
    )
    (logs / "agent_timing.json").write_text(
        json.dumps({"wall_seconds": 0.5, "timed_out": False, "child_returncode": 0}), encoding="utf-8"
    )


@pytest.mark.parametrize(
    "agent_cls,stream",
    [
        (
            BudgetedClaudeCodeAgent,
            [
                {"type": "assistant", "message": {"usage": {"input_tokens": 5, "output_tokens": 3}, "content": []}},
                {"type": "result"},
            ],
        ),
        (
            BudgetedCodexAgent,
            [{"type": "turn.completed", "usage": {"input_tokens": 5, "output_tokens": 3}}],
        ),
    ],
)
def test_finalize_accepts_complete_v3_ledgers_without_requiring_common_steps(tmp_path, agent_cls, stream):
    write_common(tmp_path)
    (tmp_path / "cli_stream.jsonl").write_text(
        "\n".join(json.dumps(row) for row in stream), encoding="utf-8"
    )
    agent = agent_cls("provider/deepseek-v4-flash", max_cumulative_output_tokens=10)
    result = agent._finalize(tmp_path)
    assert result.failure_mode == FailureMode.NONE
    ledger = json.loads((tmp_path / "budget_ledger_v3.json").read_text(encoding="utf-8"))
    assert ledger["within_budget"] is True
    assert ledger["gateway_output_matches_cli_stream"] is True


def test_finalize_fails_closed_on_gateway_stream_mismatch(tmp_path):
    write_common(tmp_path, output_tokens=2)
    (tmp_path / "cli_stream.jsonl").write_text(
        json.dumps({"type": "turn.completed", "usage": {"input_tokens": 5, "output_tokens": 3}}),
        encoding="utf-8",
    )
    agent = BudgetedCodexAgent("openai/deepseek-v4-flash", max_cumulative_output_tokens=10)
    result = agent._finalize(tmp_path)
    assert result.failure_mode == FailureMode.UNKNOWN_AGENT_ERROR
    ledger = json.loads((tmp_path / "budget_ledger_v3.json").read_text(encoding="utf-8"))
    assert ledger["within_budget"] is False


def test_setup_templates_install_shared_hook_and_enable_codex_feature():
    claude = BudgetedClaudeCodeAgent("anthropic/deepseek-v4-flash", version="2.1.224")
    codex = BudgetedCodexAgent("openai/deepseek-v4-flash", version="0.146.1")
    claude_script = claude._install_agent_script_path.read_text(encoding="utf-8")
    codex_script = codex._install_agent_script_path.read_text(encoding="utf-8")
    assert '$HOME/.claude/settings.json' in claude_script
    assert '$HOME/.codex/hooks.json' in codex_script
    assert 'hooks = true' in codex_script
    shared = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))
    assert shared["hooks"]["PreToolUse"][0]["matcher"] == ".*"
