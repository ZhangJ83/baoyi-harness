import json
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from . import config


@dataclass
class ToolFn:
    name: str
    arguments: str


@dataclass
class ToolCall:
    id: str
    function: ToolFn


@dataclass
class AssistantMessage:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    # Retained only for provider-required continuation of a tool-use turn.
    # The terminal deliberately never renders this raw private reasoning.
    reasoning_content: str | None = None


@dataclass
class _Choice:
    message: AssistantMessage


@dataclass
class LLMReply:
    choices: list[_Choice] = field(default_factory=list)
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    usage_authoritative: bool = False
    reasoning_chars: int = 0

    @classmethod
    def from_message(cls, msg: AssistantMessage, total_tokens: int = 0, input_tokens: int = 0, output_tokens: int = 0, usage_authoritative: bool = False) -> "LLMReply":
        return cls(choices=[_Choice(message=msg)], total_tokens=total_tokens, input_tokens=input_tokens, output_tokens=output_tokens, usage_authoritative=usage_authoritative, reasoning_chars=len(msg.reasoning_content or ""))


class ProviderRequestCancelled(RuntimeError):
    """Raised when the UI aborts the active provider request."""


def _retry(call, cancelled=None):
    last = None
    for attempt in range(config.api_retries() + 1):
        if cancelled and cancelled():
            raise ProviderRequestCancelled("provider request cancelled")
        try:
            return call()
        except Exception as exc:
            if cancelled and cancelled():
                raise ProviderRequestCancelled("provider request cancelled") from exc
            last = exc
            status = getattr(exc, "status_code", None)
            retryable = status in {408, 409, 429, 500, 502, 503, 504} or isinstance(exc, (TimeoutError, ConnectionError))
            # OpenAI SDK transport errors are their own exception classes and
            # are not ConnectionError subclasses. Observed in real runs as
            # APIConnectionError after a long tool turn; retry them like the
            # transport errors they are.
            try:
                import openai
                if isinstance(exc, openai.APIConnectionError):
                    retryable = True
            except Exception:
                pass
            if not retryable or attempt >= config.api_retries():
                raise
            time.sleep(min(8.0, (2 ** attempt) + random.random() * 0.25))
    raise last  # pragma: no cover


class LLM:
    """OpenAI-compatible client (OpenAI, DeepSeek, local servers, ...)."""

    def __init__(self, model: str | None = None):
        self._cancelled = threading.Event()
        self._client = self._create_client()
        self.model = model or config.model()
    @staticmethod
    def _create_client():
        import openai

        return openai.OpenAI(
            api_key=config.api_key() or "EMPTY",
            base_url=config.api_base(),
            timeout=config.api_timeout(),
            max_retries=0,
        )

    def cancel_current(self) -> None:
        """Abort an in-flight HTTP request, like Claude Code's AbortController."""
        event = getattr(self, "_cancelled", None)
        if event is None:
            event = self._cancelled = threading.Event()
        event.set()
        client = getattr(self, "_client", None)
        self._client = None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    def chat(self, messages: list[dict[str, Any]], tools: list[dict] | None = None,
             stream: bool = False, on_token=None, on_reasoning=None) -> LLMReply:
        event = getattr(self, "_cancelled", None)
        if event is None:
            event = self._cancelled = threading.Event()
        event.clear()
        if self._client is None:
            self._client = self._create_client()
        client = self._client
        # DeepSeek thinking continuations require an exact private reasoning
        # payload across every tool turn. That coupling becomes brittle after
        # history compaction and batched tool calls. Use thinking for the
        # initial semantic decision, then a normal execution continuation once
        # tool results exist. The private payload is still retained for audit.
        executing_tool_chain = any(message.get("role") == "tool" for message in messages)
        eff = config.reasoning_effort()
        thinking = config.thinking_enabled() and (eff != "off") and not executing_tool_chain
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": config.max_output_tokens(),
            "extra_body": {"thinking": {"type": "enabled" if thinking else "disabled"}},
        }
        if eff != "off":
            kwargs["reasoning_effort"] = eff
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if stream and on_token is not None and not tools:
            kwargs["stream"] = True
            kwargs["stream_options"] = {"include_usage": True}
            resp = _retry(lambda: client.chat.completions.create(**kwargs), event.is_set)
            content_parts: list[str] = []
            reasoning_parts: list[str] = []
            usage_tokens = (0, 0, 0)
            for chunk in resp:
                if not getattr(chunk, "choices", None):
                    usage = getattr(chunk, "usage", None)
                    if usage is not None:
                        usage_tokens = (getattr(usage, "prompt_tokens", 0) or 0,
                                        getattr(usage, "completion_tokens", 0) or 0,
                                        getattr(usage, "total_tokens", 0) or 0)
                    continue
                delta = chunk.choices[0].delta
                piece = getattr(delta, "content", None)
                if piece:
                    content_parts.append(piece)
                    on_token(piece)
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    reasoning_parts.append(reasoning)
                    if on_reasoning is not None:
                        on_reasoning(reasoning)
            input_tokens, output_tokens, total_tokens = usage_tokens
            total_tokens = total_tokens or input_tokens + output_tokens
            return LLMReply.from_message(
                AssistantMessage(content="".join(content_parts), reasoning_content="".join(reasoning_parts) or None),
                total_tokens, input_tokens, output_tokens, total_tokens > 0,
            )
        resp = _retry(lambda: client.chat.completions.create(**kwargs), event.is_set)
        msg = resp.choices[0].message
        tcs = [ToolCall(id=tc.id, function=ToolFn(name=tc.function.name, arguments=tc.function.arguments))
               for tc in (msg.tool_calls or [])]
        usage = getattr(resp, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        total_tokens = getattr(usage, "total_tokens", 0) or input_tokens + output_tokens
        return LLMReply.from_message(
            AssistantMessage(
                content=msg.content or "",
                tool_calls=tcs,
                reasoning_content=getattr(msg, "reasoning_content", None),
            ),
            total_tokens, input_tokens, output_tokens, usage is not None,
        )


def _get_json(s: str) -> dict:
    try:
        return json.loads(s or "{}")
    except json.JSONDecodeError:
        return {}


def _convert_openai_messages(messages: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
    """Convert harness history (OpenAI shape) to Anthropic shape.

    Anthropic has no `system` role; system + instructions become one first user message.
    Consecutive tool results get merged into a single user message, because Anthropic
    requires alternating user/assistant turns.
    """
    system_parts: list[str] = []
    api_messages: list[dict[str, Any]] = []

    def push_user(content: str) -> None:
        if api_messages and api_messages[-1]["role"] == "user":
            prev = api_messages[-1]["content"]
            if isinstance(prev, str):
                api_messages[-1]["content"] = prev + "\n\n" + content
            else:
                api_messages[-1]["content"] = prev + [{"type": "text", "text": content}]
        else:
            api_messages.append({"role": "user", "content": content})

    for m in messages:
        role = m.get("role")
        if role == "system":
            system_parts.append(m.get("content", ""))
            continue
        if role == "user":
            push_user(m.get("content", ""))
        elif role == "assistant":
            content: list[dict[str, Any]] = []
            if m.get("content"):
                content.append({"type": "text", "text": m["content"]})
            for tc in m.get("tool_calls") or []:
                content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": _get_json(tc["function"]["arguments"]),
                })
            api_messages.append({"role": "assistant", "content": content})
        elif role == "tool":
            result: dict[str, Any] = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m.get("content", "")}
            if api_messages and api_messages[-1]["role"] == "user":
                prev = api_messages[-1]["content"]
                if isinstance(prev, str):
                    api_messages[-1]["content"] = [{"type": "text", "text": prev}, result]
                else:
                    prev.append(result)
            else:
                api_messages.append({"role": "user", "content": [result]})
    return ("".join(system_parts) or None, api_messages)


def _convert_tools(tools: list[dict]) -> list[dict]:
    """Anthropic tools schema: name/description/input_schema (no function wrapper)."""
    out = []
    for t in tools:
        f = t["function"]
        out.append({"name": f["name"], "description": f["description"], "input_schema": f["parameters"]})
    return out


class AnthropicLLM:
    def __init__(self, model: str | None = None):
        self._cancelled = threading.Event()
        self._client = self._create_client()
        self.model = model or config.anthropic_model()

    @staticmethod
    def _create_client():
        import anthropic

        return anthropic.Anthropic(
            api_key=config.anthropic_api_key(),
            base_url=config.anthropic_api_base(),
            timeout=config.api_timeout(),
            max_retries=0,
        )

    def cancel_current(self) -> None:
        event = getattr(self, "_cancelled", None)
        if event is None:
            event = self._cancelled = threading.Event()
        event.set()
        client = getattr(self, "_client", None)
        self._client = None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    def chat(self, messages: list[dict[str, Any]], tools: list[dict] | None = None,
             stream: bool = False, on_token=None, on_reasoning=None) -> LLMReply:
        # Anthropic transport currently streams lazily per message; the OpenAI-
        # compatible client above is the token-streaming path used in practice.
        del stream, on_token, on_reasoning
        event = getattr(self, "_cancelled", None)
        if event is None:
            event = self._cancelled = threading.Event()
        event.clear()
        if self._client is None:
            self._client = self._create_client()
        client = self._client
        system, api_messages = _convert_openai_messages(messages)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": config.anthropic_max_tokens(),
            "messages": api_messages,
            "output_config": {"effort": config.reasoning_effort()},
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = _convert_tools(tools)
        resp = _retry(lambda: client.messages.create(**kwargs), event.is_set)
        text_parts: list[str] = []
        tcs: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tcs.append(ToolCall(id=block.id, function=ToolFn(name=block.name, arguments=json.dumps(block.input))))
        usage = getattr(resp, "usage", None)
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        total = input_tokens + output_tokens
        return LLMReply.from_message(AssistantMessage(content="".join(text_parts), tool_calls=tcs), total, input_tokens, output_tokens, usage is not None)


def make_client(model: str | None = None) -> LLM:  # type: ignore[return-value]
    if config.provider() == "anthropic":
        return AnthropicLLM(model)
    return LLM(model)
