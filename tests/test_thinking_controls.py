import os
from unittest.mock import patch

from agent import config
from agent.llm import AssistantMessage, LLM, ProviderRequestCancelled, _retry


def test_deepseek_effort_maps_to_documented_levels():
    with patch.dict(os.environ, {"REASONING_EFFORT": "xhigh"}, clear=False):
        assert config.reasoning_effort() == "max"
    with patch.dict(os.environ, {"REASONING_EFFORT": "low"}, clear=False):
        assert config.reasoning_effort() == "low"


def test_thinking_defaults_on_and_can_be_disabled():
    with patch.dict(os.environ, {"THINKING_ENABLED": "0"}, clear=False):
        assert not config.thinking_enabled()
    with patch.dict(os.environ, {}, clear=True):
        assert config.thinking_enabled()


def test_command_policy_setter_persists_valid_values_only():
    with patch.dict(os.environ, {}, clear=True):
        assert config.command_policy() == "ask"
        config.set_command_policy("deny")
        assert config.command_policy() == "deny"
        config.set_command_policy("bogus")
        assert config.command_policy() == "deny"


def test_raw_reasoning_is_present_in_protocol_message_not_user_content():
    message = AssistantMessage(content="可公开的答案", reasoning_content="private")
    assert message.content == "可公开的答案"
    assert message.reasoning_content == "private"


def test_openai_compatible_request_sends_thinking_and_effort():
    seen = {}

    class Completions:
        def create(self, **kwargs):
            seen.update(kwargs)
            message = type("Message", (), {"content": "ok", "tool_calls": [], "reasoning_content": "r"})()
            usage = type("Usage", (), {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3})()
            return type("Response", (), {"choices": [type("Choice", (), {"message": message})()], "usage": usage})()

    llm = LLM.__new__(LLM)
    llm.model = "deepseek-v4"
    llm._client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    with patch.dict(os.environ, {"THINKING_ENABLED": "1", "REASONING_EFFORT": "max"}, clear=False):
        reply = llm.chat([{"role": "user", "content": "hi"}])
    assert seen["reasoning_effort"] == "max"
    assert seen["extra_body"] == {"thinking": {"type": "enabled"}}
    assert reply.reasoning_chars == 1


def test_openai_tool_continuation_switches_to_execution_mode():
    seen = {}

    class Completions:
        def create(self, **kwargs):
            seen.update(kwargs)
            message = type("Message", (), {"content": "ok", "tool_calls": [], "reasoning_content": None})()
            usage = type("Usage", (), {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})()
            return type("Response", (), {"choices": [type("Choice", (), {"message": message})()], "usage": usage})()

    llm = LLM.__new__(LLM)
    llm.model = "deepseek-v4"
    llm._client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    messages = [
        {"role": "user", "content": "build"},
        {"role": "assistant", "content": "", "reasoning_content": "private", "tool_calls": [{"id": "1", "type": "function", "function": {"name": "open_deck", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "1", "content": "opened"},
    ]
    with patch.dict(os.environ, {"THINKING_ENABLED": "1"}, clear=False):
        llm.chat(messages)
    assert seen["extra_body"] == {"thinking": {"type": "disabled"}}


def test_cancel_current_closes_and_detaches_provider_client():
    closed = []
    llm = LLM.__new__(LLM)
    llm._client = type("Client", (), {"close": lambda self: closed.append(True)})()
    llm.cancel_current()
    assert closed == [True]
    assert llm._client is None


def test_cancelled_request_never_enters_retry_loop():
    attempts = []

    def request():
        attempts.append(True)
        raise ConnectionError("closed")

    try:
        _retry(request, lambda: True)
    except ProviderRequestCancelled:
        pass
    else:
        raise AssertionError("expected cancellation")
    assert attempts == []
