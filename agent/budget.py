"""Shared, auditable execution-budget ledger.

The ledger counts only observable events (provider tokens, tool commands and
agent turns).  Adapters for other agents can emit the same snapshot without
pretending to know vendor-internal reasoning tokens.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class BudgetLedger:
    max_total_tokens: int
    max_tool_calls: int
    max_steps: int
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    steps: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def begin_step(self) -> bool:
        if self.steps >= self.max_steps or self.total_tokens >= self.max_total_tokens:
            return False
        self.steps += 1
        return True

    def record_tokens(self, input_tokens: int, output_tokens: int) -> bool:
        self.input_tokens += max(0, int(input_tokens))
        self.output_tokens += max(0, int(output_tokens))
        return self.total_tokens <= self.max_total_tokens

    def record_tool(self) -> bool:
        if self.tool_calls >= self.max_tool_calls:
            return False
        self.tool_calls += 1
        return True

    def snapshot(self, *, system: str | None = None, **extra: Any) -> dict[str, Any]:
        data = asdict(self)
        data["total_tokens"] = self.total_tokens
        data["within_budget"] = (
            self.total_tokens <= self.max_total_tokens
            and self.tool_calls <= self.max_tool_calls
            and self.steps <= self.max_steps
        )
        if system is not None:
            data["system"] = system
        data.update(extra)
        return data
