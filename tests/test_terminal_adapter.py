import pytest

from agent.safety import sensitive_output

try:
    from agent.terminal_bench_adapter import XiaopuTerminalAgent
    from terminal_bench.agents.failure_mode import FailureMode
    _ADAPTER_IMPORT_ERROR = None
except ModuleNotFoundError as exc:
    XiaopuTerminalAgent = None
    FailureMode = None
    _ADAPTER_IMPORT_ERROR = exc


def test_sensitive_output_guard_blocks_solution_content():
    assert sensitive_output("cat /app/solution.txt")
    assert sensitive_output("grep password /tmp/.env")


def test_sensitive_output_guard_allows_metadata_checks():
    assert not sensitive_output("wc -c /app/solution.txt")
    assert not sensitive_output("sha256sum /app/solution.txt")
    assert not sensitive_output("ls -l /app/archive.tar")


class _FakeLLM:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def call(self, prompt, **kwargs):
        self.calls += 1
        return self.payload

    def count_tokens(self, messages):
        return 10


class _SequenceLLM(_FakeLLM):
    def __init__(self, payloads):
        super().__init__(payloads[0])
        self.payloads = list(payloads)

    def call(self, prompt, **kwargs):
        self.calls += 1
        return self.payloads[min(self.calls - 1, len(self.payloads) - 1)]


class _FakeSession:
    def __init__(self):
        self.commands = []

    def capture_pane(self, capture_entire=False):
        return ""

    def send_keys(self, keys, block=True):
        self.commands.append(keys[0])


class _FailingLLM(_FakeLLM):
    def call(self, prompt, **kwargs):
        self.calls += 1
        raise RuntimeError("provider unavailable")


class _UsageFakeLLM(_FakeLLM):
    def __init__(self, payload, usage):
        super().__init__(payload)
        self.usage = usage
        self.last_usage = None

    def call(self, prompt, **kwargs):
        self.calls += 1
        self.last_usage = self.usage
        return self.payload


@pytest.mark.skipif(XiaopuTerminalAgent is None, reason="official terminal-bench dependency is not installed in host test env")
def test_adapter_enforces_total_token_budget_offline():
    llm = _FakeLLM('{"commands":["echo ok"],"done":false}')
    session = _FakeSession()
    agent = XiaopuTerminalAgent(llm=llm, max_total_tokens=15, max_steps=5)
    result = agent.perform_task("do a safe task", session)
    assert result.failure_mode == FailureMode.AGENT_TIMEOUT
    assert llm.calls == 1


@pytest.mark.skipif(XiaopuTerminalAgent is None, reason="official terminal-bench dependency is not installed in host test env")
def test_adapter_enforces_tool_call_budget_offline():
    llm = _FakeLLM('{"commands":["echo a","echo b","echo c"],"done":false}')
    session = _FakeSession()
    agent = XiaopuTerminalAgent(llm=llm, max_total_tokens=1000, max_tool_calls=2, max_steps=5)
    result = agent.perform_task("do a safe task", session)
    assert result.failure_mode == FailureMode.AGENT_TIMEOUT
    assert session.commands == ["echo a", "echo b"]


@pytest.mark.skipif(XiaopuTerminalAgent is None, reason="official terminal-bench dependency is not installed in host test env")
def test_adapter_repairs_truncated_json_once():
    llm = _SequenceLLM(["{\"commands\":[", '{"commands":["echo repaired"],"done":true}'])
    session = _FakeSession()
    agent = XiaopuTerminalAgent(llm=llm, max_total_tokens=1000, max_steps=1)
    result = agent.perform_task("do a safe task", session)
    assert result.failure_mode == FailureMode.NONE
    assert llm.calls == 2
    assert session.commands == ["echo repaired"]


@pytest.mark.skipif(XiaopuTerminalAgent is None, reason="official terminal-bench dependency is not installed in host test env")
def test_adapter_preserves_ledger_on_fatal_parse(tmp_path):
    llm = _SequenceLLM(["not json", "still not json"])
    agent = XiaopuTerminalAgent(llm=llm, max_total_tokens=1000, max_steps=1)
    result = agent.perform_task("do a safe task", _FakeSession(), logging_dir=tmp_path)
    assert result.failure_mode == FailureMode.FATAL_LLM_PARSE_ERROR
    assert result.total_input_tokens == 20
    assert result.total_output_tokens == 20
    ledger = __import__("json").loads((tmp_path / "budget_ledger.json").read_text())
    assert ledger["failure_mode"] == FailureMode.FATAL_LLM_PARSE_ERROR.value
    assert ledger["total_tokens"] == 40


@pytest.mark.skipif(XiaopuTerminalAgent is None, reason="official terminal-bench dependency is not installed in host test env")
def test_adapter_preserves_input_ledger_on_provider_error(tmp_path):
    llm = _FailingLLM("")
    agent = XiaopuTerminalAgent(llm=llm, max_total_tokens=1000, max_steps=1)
    result = agent.perform_task("do a safe task", _FakeSession(), logging_dir=tmp_path)
    assert result.failure_mode == FailureMode.UNKNOWN_AGENT_ERROR
    assert result.total_input_tokens == 10
    assert result.total_output_tokens == 0
    assert (tmp_path / "budget_ledger.json").is_file()


@pytest.mark.skipif(XiaopuTerminalAgent is None, reason="official terminal-bench dependency is not installed in host test env")
def test_v3_adapter_uses_authoritative_usage_and_emits_common_ledger(tmp_path):
    llm = _UsageFakeLLM('{"commands":["echo ok"],"done":true}', (12, 4))
    agent = XiaopuTerminalAgent(
        llm=llm,
        budget_protocol="v3",
        max_cumulative_output_tokens=10,
        max_tool_calls=2,
        max_steps=3,
        max_agent_wall_seconds=5,
    )
    result = agent.perform_task("do a safe task", _FakeSession(), logging_dir=tmp_path)
    assert result.failure_mode == FailureMode.NONE
    assert result.total_input_tokens == 12
    assert result.total_output_tokens == 4
    ledger = __import__("json").loads((tmp_path / "budget_ledger_v3.json").read_text())
    assert ledger["within_budget"] is True
    assert ledger["authoritative_output_matches_result"] is True
    assert ledger["enforcement"]["covered_local_tools"] == "pre-execution ledger gate"
