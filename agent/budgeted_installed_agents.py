"""Terminal-Bench installed-agent adapters for the prospective v3 protocol."""
from __future__ import annotations

import base64
import json
import os
import shlex
from pathlib import Path

from terminal_bench.agents.base_agent import AgentResult
from terminal_bench.agents.failure_mode import FailureMode
from terminal_bench.agents.installed_agents.abstract_installed_agent import AbstractInstalledAgent
from terminal_bench.terminal.models import TerminalCommand
from terminal_bench.terminal.tmux_session import TmuxSession

from agent.competitor_stream_ledger import normalize


AGENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AGENT_DIR.parent
HOOK_CONFIG = PROJECT_ROOT / "benchmarks" / "hooks" / "local_tool_budget_hooks.json"
EMBEDDED_MODULES = [
    "generation_budget_gateway.py",
    "generation_budget_proxy.py",
    "budgeted_cli_runner.py",
    "tool_budget_hook.py",
]


def _b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


class _BudgetedInstalledAgent(AbstractInstalledAgent):
    stream_provider: str
    system_name: str
    upstream_base: str
    setup_template: str

    def __init__(
        self,
        model_name: str,
        *,
        max_cumulative_output_tokens: int = 4500,
        max_covered_local_tool_calls: int = 60,
        max_agent_wall_seconds: float = 180.0,
        version: str = "latest",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._model_name = model_name.split("/")[-1]
        self._max_output = max(1, int(max_cumulative_output_tokens))
        self._max_tools = max(1, int(max_covered_local_tool_calls))
        self._max_wall = max(1.0, float(max_agent_wall_seconds))
        self._version = version

    def _get_template_variables(self) -> dict[str, str]:
        variables = {"version": self._version, "hook_config_b64": _b64(HOOK_CONFIG)}
        for name in EMBEDDED_MODULES:
            variables[name.replace(".py", "_b64")] = _b64(AGENT_DIR / name)
        variables["init_b64"] = _b64(AGENT_DIR / "__init__.py")
        return variables

    @property
    def _install_agent_script_path(self) -> Path:
        return self._get_templated_script_path(self.setup_template)

    def _runner_command(self, cli_command: str) -> str:
        log_root = self.CONTAINER_AGENT_LOGS_PATH
        return " ".join(
            [
                "PYTHONPATH=/installed-agent",
                "python3 -m agent.budgeted_cli_runner",
                "--upstream-base",
                shlex.quote(self.upstream_base),
                "--gateway-state",
                shlex.quote(f"{log_root}/generation_budget_gateway.json"),
                "--stream-log",
                shlex.quote(f"{log_root}/cli_stream.jsonl"),
                "--timing",
                shlex.quote(f"{log_root}/agent_timing.json"),
                "--output-cap",
                str(self._max_output),
                "--wall-seconds",
                str(self._max_wall),
                "--",
                cli_command,
            ]
        )

    def _finalize(self, logging_dir: Path) -> AgentResult:
        def read_json(name: str) -> dict:
            path = logging_dir / name
            return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}

        stream_path = logging_dir / "cli_stream.jsonl"
        stream = (
            normalize(self.stream_provider, stream_path.read_text(encoding="utf-8").splitlines())
            if stream_path.is_file()
            else {
                "input_tokens": 0,
                "output_tokens": 0,
                "tool_calls": 0,
                "steps": None,
                "final_event_seen": False,
                "parse_errors": ["missing cli stream"],
                "observability_gaps": [],
            }
        )
        gateway = read_json("generation_budget_gateway.json")
        tools = read_json("tool_budget_hook.json")
        timing = read_json("agent_timing.json")
        allowed_tools = len(tools.get("allowed", []))
        denied_tools = len(tools.get("denied", []))
        gateway_output = gateway.get("committed_output_tokens")
        output_match = isinstance(gateway_output, int) and gateway_output == stream["output_tokens"]
        wall_seconds = timing.get("wall_seconds")
        within = bool(
            stream.get("final_event_seen")
            and not stream.get("parse_errors")
            and output_match
            and not gateway.get("violations")
            and stream["output_tokens"] <= self._max_output
            and allowed_tools <= self._max_tools
            and isinstance(wall_seconds, (int, float))
            and wall_seconds <= self._max_wall + 1.0
            and timing.get("timed_out") is False
            and timing.get("child_returncode") == 0
        )
        ledger = {
            "schema": "matched-budget-ledger-v3",
            "system": self.system_name,
            "input_tokens": stream["input_tokens"],
            "output_tokens": stream["output_tokens"],
            "covered_local_tool_calls": allowed_tools,
            "denied_local_tool_calls": denied_tools,
            "system_specific_steps": stream.get("steps"),
            "wall_seconds": wall_seconds,
            "caps": {
                "max_cumulative_output_tokens": self._max_output,
                "max_covered_local_tool_calls": self._max_tools,
                "max_agent_wall_seconds": self._max_wall,
            },
            "enforcement": {
                "output_tokens": "pre-request gateway reservation and provider max-output rewrite",
                "covered_local_tools": "blocking PreToolUse hook",
                "wall_time": "supervisor deadline",
            },
            "gateway_output_matches_cli_stream": output_match,
            "stream_observability_gaps": stream.get("observability_gaps", []),
            "parse_errors": stream.get("parse_errors", []),
            "gateway_violations": gateway.get("violations", []),
            "within_budget": within,
        }
        (logging_dir / "budget_ledger_v3.json").write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if timing.get("timed_out") is True:
            failure_mode = FailureMode.AGENT_TIMEOUT
        elif within:
            failure_mode = FailureMode.NONE
        else:
            failure_mode = FailureMode.UNKNOWN_AGENT_ERROR
        return AgentResult(
            total_input_tokens=int(stream["input_tokens"]),
            total_output_tokens=int(stream["output_tokens"]),
            failure_mode=failure_mode,
        )

    def perform_task(
        self, instruction: str, session: TmuxSession, logging_dir: Path | None = None
    ) -> AgentResult:
        result = super().perform_task(instruction, session, logging_dir)
        if result.failure_mode == FailureMode.AGENT_INSTALLATION_FAILED or logging_dir is None:
            return result
        return self._finalize(logging_dir)


class BudgetedClaudeCodeAgent(_BudgetedInstalledAgent):
    stream_provider = "claude_code"
    system_name = "claude_code"
    upstream_base = "https://api.deepseek.com/anthropic"
    setup_template = "budgeted_claude_setup.sh.j2"

    @staticmethod
    def name() -> str:
        return "budgeted-claude-code"

    @property
    def _env(self) -> dict[str, str]:
        return {
            "ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"],
            "ANTHROPIC_MODEL": self._model_name,
            "XIAOPU_MAX_TOOL_CALLS": str(self._max_tools),
            "XIAOPU_TOOL_BUDGET_STATE": f"{self.CONTAINER_AGENT_LOGS_PATH}/tool_budget_hook.json",
        }

    def _run_agent_commands(self, instruction: str) -> list[TerminalCommand]:
        cli = " ".join(
            [
                "claude --verbose --output-format stream-json -p",
                shlex.quote(instruction),
                "--allowedTools Bash Edit Write Read Glob Grep LS",
            ]
        )
        return [TerminalCommand(command=self._runner_command(cli), min_timeout_sec=0.0, max_timeout_sec=self._max_wall + 30, block=True, append_enter=True)]


class BudgetedCodexAgent(_BudgetedInstalledAgent):
    stream_provider = "codex"
    system_name = "codex"
    upstream_base = "https://api.deepseek.com"
    setup_template = "budgeted_codex_setup.sh.j2"

    @staticmethod
    def name() -> str:
        return "budgeted-codex"

    @property
    def _env(self) -> dict[str, str]:
        return {
            "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
            "OPENAI_MODEL": self._model_name,
            "XIAOPU_MAX_TOOL_CALLS": str(self._max_tools),
            "XIAOPU_TOOL_BUDGET_STATE": f"{self.CONTAINER_AGENT_LOGS_PATH}/tool_budget_hook.json",
        }

    def _run_agent_commands(self, instruction: str) -> list[TerminalCommand]:
        cli = " ".join(
            [
                "codex exec --sandbox danger-full-access --skip-git-repo-check",
                "--dangerously-bypass-hook-trust --json --model",
                shlex.quote(self._model_name),
                "--",
                shlex.quote(instruction),
            ]
        )
        return [TerminalCommand(command=self._runner_command(cli), min_timeout_sec=0.0, max_timeout_sec=self._max_wall + 30, block=True, append_enter=True)]
