"""Terminal-Bench adapter for the Xiaopu command policy.

The adapter deliberately uses Terminal-Bench's BaseAgent/TmuxSession contract
so official task scoring remains responsible for container setup and tests.
It asks the configured benchmark LLM for a small JSON command batch, executes
it in the official session, then asks for one focused follow-up batch.
"""

import json
import os
import time
from pathlib import Path

from pydantic import BaseModel, Field
from terminal_bench.agents.base_agent import AgentResult, BaseAgent
from terminal_bench.agents.failure_mode import FailureMode
from terminal_bench.llms.lite_llm import LiteLLM
from terminal_bench.terminal.tmux_session import TmuxSession
from agent.safety import sensitive_output
from agent.budget import BudgetLedger


class UsageAwareOpenAITextLLM:
    """Small v3 client that retains authoritative provider usage per call."""

    def __init__(self, *, model_name: str, api_base: str | None, temperature: float):
        import openai

        self._client = openai.OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"),
            base_url=api_base,
            timeout=120.0,
            max_retries=0,
        )
        self._model = model_name.split("/", 1)[-1]
        self._temperature = temperature
        self.last_usage: tuple[int, int] | None = None

    def call(self, prompt: str, max_tokens: int) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._temperature,
            max_tokens=max_tokens,
        )
        usage = response.usage
        self.last_usage = (
            int(getattr(usage, "prompt_tokens", 0) or 0),
            int(getattr(usage, "completion_tokens", 0) or 0),
        )
        return response.choices[0].message.content or ""

    @staticmethod
    def count_tokens(messages) -> int:
        # v3 never uses this estimate for ledger accounting. It remains only
        # for BaseLLM-shaped compatibility with test doubles and v2 code.
        return sum(len(str(message.get("content", "")).split()) for message in messages)


class CommandBatch(BaseModel):
    commands: list[str] = Field(default_factory=list)
    done: bool = False


class XiaopuTerminalAgent(BaseAgent):
    def __init__(
        self,
        model_name: str = "openai/deepseek-v4-flash",
        llm=None,
        api_base: str | None = None,
        temperature: float = 0.0,
        max_total_tokens: int = 12_000,
        max_output_tokens: int = 1_500,
        max_tool_calls: int = 60,
        max_steps: int = 3,
        budget_protocol: str = "v2",
        max_cumulative_output_tokens: int = 4_500,
        max_agent_wall_seconds: float = 180.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        # Terminal-Bench's AgentFactory passes model_name/agent kwargs rather
        # than injecting an LLM object.  Keeping the optional llm argument
        # makes the adapter easy to unit-test while matching the official
        # factory contract in real runs.
        self._budget_protocol = str(budget_protocol)
        if self._budget_protocol not in {"v2", "v3"}:
            raise ValueError("budget_protocol must be v2 or v3")
        self._llm = llm or (
            UsageAwareOpenAITextLLM(
                model_name=model_name,
                api_base=api_base,
                temperature=temperature,
            )
            if self._budget_protocol == "v3"
            else LiteLLM(
                model_name=model_name,
                api_base=api_base,
                temperature=temperature,
            )
        )
        self._max_total_tokens = max(1, int(max_total_tokens))
        self._max_output_tokens = max(1, int(max_output_tokens))
        self._max_tool_calls = max(1, int(max_tool_calls))
        self._max_steps = max(1, int(max_steps))
        self._max_cumulative_output_tokens = max(1, int(max_cumulative_output_tokens))
        self._max_agent_wall_seconds = max(1.0, float(max_agent_wall_seconds))

    @staticmethod
    def name() -> str:
        return "xiaopu"

    @staticmethod
    def _sensitive_output(command: str) -> bool:
        """Reject commands that would print likely secrets into the transcript."""
        return sensitive_output(command)

    def perform_task(self, instruction: str, session: TmuxSession, logging_dir: Path | None = None) -> AgentResult:
        agent_started = time.monotonic()
        ledger = BudgetLedger(
            max_total_tokens=(self._max_total_tokens if self._budget_protocol == "v2" else 2**63 - 1),
            max_tool_calls=self._max_tool_calls,
            max_steps=self._max_steps,
        )
        transcript: list[str] = []
        budget_exhausted = False
        audit_errors: list[str] = []

        def record_v3_usage() -> bool:
            usage = getattr(self._llm, "last_usage", None)
            if (
                not isinstance(usage, tuple)
                or len(usage) != 2
                or any(not isinstance(value, int) or value < 0 for value in usage)
            ):
                audit_errors.append("authoritative provider usage missing")
                return False
            ledger.record_tokens(usage[0], usage[1])
            return ledger.output_tokens <= self._max_cumulative_output_tokens

        def finish(failure_mode: FailureMode) -> AgentResult:
            """Persist and return the ledger on every exit path, including errors."""
            if logging_dir is not None:
                logging_dir.mkdir(parents=True, exist_ok=True)
                (logging_dir / "xiaopu_commands.json").write_text(
                    json.dumps(transcript, indent=2), encoding="utf-8"
                )
                if self._budget_protocol == "v3":
                    wall_seconds = time.monotonic() - agent_started
                    v3_ledger = {
                        "schema": "matched-budget-ledger-v3",
                        "system": "xiaopu",
                        "input_tokens": ledger.input_tokens,
                        "output_tokens": ledger.output_tokens,
                        "covered_local_tool_calls": ledger.tool_calls,
                        "denied_local_tool_calls": 0,
                        "system_specific_steps": ledger.steps,
                        "wall_seconds": wall_seconds,
                        "caps": {
                            "max_cumulative_output_tokens": self._max_cumulative_output_tokens,
                            "max_covered_local_tool_calls": self._max_tool_calls,
                            "max_agent_wall_seconds": self._max_agent_wall_seconds,
                        },
                        "enforcement": {
                            "output_tokens": "pre-request cumulative remaining-output rewrite with authoritative provider usage",
                            "covered_local_tools": "pre-execution ledger gate",
                            "wall_time": "Terminal-Bench global agent timeout",
                        },
                        "authoritative_output_matches_result": not audit_errors,
                        "parse_errors": audit_errors,
                        "gateway_violations": [],
                        "within_budget": (
                            not audit_errors
                            and ledger.output_tokens <= self._max_cumulative_output_tokens
                            and ledger.tool_calls <= self._max_tool_calls
                            and wall_seconds <= self._max_agent_wall_seconds + 1.0
                        ),
                        "failure_mode": failure_mode.value,
                    }
                    (logging_dir / "budget_ledger_v3.json").write_text(
                        json.dumps(v3_ledger, indent=2), encoding="utf-8"
                    )
                else:
                    (logging_dir / "budget_ledger.json").write_text(
                        json.dumps(
                            ledger.snapshot(system="xiaopu", failure_mode=failure_mode.value),
                            indent=2,
                        ),
                        encoding="utf-8",
                    )
            return AgentResult(
                total_input_tokens=ledger.input_tokens,
                total_output_tokens=ledger.output_tokens,
                failure_mode=failure_mode,
            )

        for turn in range(self._max_steps):
            if not ledger.begin_step():
                budget_exhausted = True
                break
            try:
                observation = session.capture_pane(capture_entire=False)[-6000:]
            except Exception:
                return finish(FailureMode.UNKNOWN_AGENT_ERROR)
            prompt = (
                "You are Xiaopu operating a Terminal-Bench container.\n"
                "Return JSON only: {\\\"commands\\\":[...],\\\"done\\\":true|false}.\n"
                "Use short, safe shell commands. Complete the task and verify it.\n"
                "Before declaring done, run a task-specific postcondition check: for executable/permission tasks use test -x and invoke the script; for file-creation tasks use test -f plus exact content/size checks; for archive tasks inspect the archive member list, extract only the required member, and test the output path. Then run the provided tests.\n"
                "Keep the JSON compact: emit at most 3 commands per turn. For a permission task, inspect the mode, apply the minimal chmod fix, and invoke the script; do not narrate or emit long shell pipelines.\n"
                "Never print file contents, secrets, or solution text. For sensitive files, use only metadata checks such as test -s, wc -c, sha256sum, or cmp.\n"
                "For archive tasks, extract only the required member and avoid recursive/untrusted paths.\n"
                f"Task: {instruction}\n"
                f"Current terminal output:\n{observation}\n"
                f"This is turn {turn + 1}/{self._max_steps}."
            )
            if self._budget_protocol == "v2":
                input_tokens = self._llm.count_tokens([{"role": "user", "content": prompt}])
                if not ledger.record_tokens(input_tokens, 0):
                    return finish(FailureMode.AGENT_TIMEOUT)
            remaining_output = self._max_cumulative_output_tokens - ledger.output_tokens
            if self._budget_protocol == "v3" and remaining_output <= 0:
                return finish(FailureMode.AGENT_TIMEOUT)
            call_max_tokens = min(
                self._max_output_tokens,
                remaining_output if self._budget_protocol == "v3" else self._max_output_tokens,
            )
            try:
                raw = self._llm.call(prompt, max_tokens=call_max_tokens)
            except TypeError:
                # Keep tiny test doubles compatible with the official BaseLLM
                # contract while enforcing max_tokens for LiteLLM in production.
                try:
                    raw = self._llm.call(prompt)
                except Exception:
                    return finish(FailureMode.UNKNOWN_AGENT_ERROR)
            except Exception:
                return finish(FailureMode.UNKNOWN_AGENT_ERROR)
            if self._budget_protocol == "v3":
                if not record_v3_usage():
                    return finish(FailureMode.AGENT_TIMEOUT if not audit_errors else FailureMode.UNKNOWN_AGENT_ERROR)
            else:
                output_tokens = self._llm.count_tokens([{"role": "assistant", "content": raw}])
                if not ledger.record_tokens(0, output_tokens):
                    return finish(FailureMode.AGENT_TIMEOUT)
            try:
                batch = CommandBatch.model_validate_json(raw)
            except Exception:
                # A provider can truncate a long JSON response even when the
                # requested action was simple. Spend one bounded repair call
                # instead of converting the task immediately into a fatal
                # parse error; the repair prompt forbids narration and asks
                # for a minimal command batch.
                repair_prompt = (
                    "Return only compact valid JSON in exactly this schema: "
                    '{"commands":[],"done":false}. Preserve only the minimal '
                    "commands needed to complete and verify the task. No prose.\n"
                    f"Task: {instruction}\nTerminal output:\n{observation}"
                )
                if self._budget_protocol == "v2":
                    repair_in = self._llm.count_tokens([{"role": "user", "content": repair_prompt}])
                    if not ledger.record_tokens(repair_in, 0):
                        return finish(FailureMode.AGENT_TIMEOUT)
                repair_remaining = self._max_cumulative_output_tokens - ledger.output_tokens
                if self._budget_protocol == "v3" and repair_remaining <= 0:
                    return finish(FailureMode.AGENT_TIMEOUT)
                try:
                    repair_raw = self._llm.call(
                        repair_prompt,
                        max_tokens=min(self._max_output_tokens, 512, repair_remaining),
                    )
                except TypeError:
                    try:
                        repair_raw = self._llm.call(repair_prompt)
                    except Exception:
                        return finish(FailureMode.UNKNOWN_AGENT_ERROR)
                except Exception:
                    return finish(FailureMode.UNKNOWN_AGENT_ERROR)
                if self._budget_protocol == "v3":
                    if not record_v3_usage():
                        return finish(FailureMode.AGENT_TIMEOUT if not audit_errors else FailureMode.UNKNOWN_AGENT_ERROR)
                else:
                    repair_out = self._llm.count_tokens([{"role": "assistant", "content": repair_raw}])
                    if not ledger.record_tokens(0, repair_out):
                        return finish(FailureMode.AGENT_TIMEOUT)
                try:
                    batch = CommandBatch.model_validate_json(repair_raw)
                    raw = repair_raw
                except Exception:
                    return finish(FailureMode.FATAL_LLM_PARSE_ERROR)
            remaining_calls = max(0, self._max_tool_calls - ledger.tool_calls)
            for command in batch.commands[: min(8, remaining_calls)]:
                if not ledger.record_tool():
                    budget_exhausted = True
                    break
                if self._sensitive_output(command):
                    warning = "echo 'BLOCKED: do not print sensitive file contents; use metadata-only verification'"
                    try:
                        session.send_keys([warning, "Enter"], block=True)
                    except Exception:
                        return finish(FailureMode.UNKNOWN_AGENT_ERROR)
                    transcript.append(f"BLOCKED: {command}")
                    continue
                try:
                    session.send_keys([command, "Enter"], block=True)
                except Exception:
                    return finish(FailureMode.UNKNOWN_AGENT_ERROR)
                transcript.append(command)
            if ledger.tool_calls >= self._max_tool_calls or (
                self._budget_protocol == "v2" and ledger.total_tokens >= self._max_total_tokens
            ) or (
                self._budget_protocol == "v3" and ledger.output_tokens >= self._max_cumulative_output_tokens
            ):
                budget_exhausted = True
            if batch.done:
                break
        return finish(FailureMode.AGENT_TIMEOUT if budget_exhausted else FailureMode.NONE)
