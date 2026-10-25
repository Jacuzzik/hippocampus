import asyncio
import io
import json
import urllib.error
import urllib.request
from typing import Any

import pytest

from ai.providers import base
from ai.providers.base import ProviderError, ToolCall, ToolSpec
from ai.providers.claude import ClaudeProvider, parse_claude, to_claude
from ai.providers.ollama import OllamaProvider, parse_ollama, to_ollama

SPEC = ToolSpec("read_note", "Read a note", {"type": "object", "properties": {}})


class FakeHTTP:
    """Stands in for post_json: records the request and returns a canned reply."""

    def __init__(self, reply: dict[str, Any]) -> None:
        self.reply = reply
        self.calls: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    async def __call__(
        self, url: str, headers: dict[str, str], body: dict[str, Any], timeout: float
    ) -> dict[str, Any]:
        self.calls.append((url, headers, body))
        return self.reply


def test_claude_sends_the_key_in_a_header_only(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeHTTP({"content": [{"type": "text", "text": "hi"}]})
    monkeypatch.setattr("ai.providers.claude.post_json", fake)
    provider = ClaudeProvider("sk-secret", "claude-sonnet-5-5")
    reply = asyncio.run(provider.chat([{"role": "user", "content": "hello"}], [SPEC]))
    url, headers, body = fake.calls[0]
    assert reply.text == "hi"
    assert headers["x-api-key"] == "sk-secret"
    assert "sk-secret" not in json.dumps(body) and "sk-secret" not in url
    assert body["tools"][0]["input_schema"] == SPEC.parameters


def test_claude_round_trip_with_a_tool_call() -> None:
    call = ToolCall("tu_1", "read_note", {"path": "a.md"})
    messages = [
        {"role": "user", "content": "read a"},
        {"role": "assistant", "content": "", "tool_calls": [call]},
        {"role": "tool", "tool_call_id": "tu_1", "name": "read_note", "content": "text"},
    ]
    converted = to_claude(messages)
    assert converted[1]["content"] == [
        {"type": "tool_use", "id": "tu_1", "name": "read_note", "input": {"path": "a.md"}}
    ]
    assert converted[2] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "tu_1", "content": "text"}],
    }
    reply = parse_claude(
        {
            "content": [
                {"type": "tool_use", "id": "tu_2", "name": "read_note", "input": {"path": "b.md"}}
            ]
        }
    )
    assert reply.tool_calls == [ToolCall("tu_2", "read_note", {"path": "b.md"})]


def test_claude_malformed_reply_is_a_provider_error() -> None:
    with pytest.raises(ProviderError):
        parse_claude({"content": [{"type": "tool_use"}]})


def test_ollama_chat_and_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeHTTP(
        {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "read_note", "arguments": {"path": "a.md"}}}],
            }
        }
    )
    monkeypatch.setattr("ai.providers.ollama.post_json", fake)
    reply = asyncio.run(
        OllamaProvider("qwen2.5:1.5b").chat([{"role": "user", "content": "x"}], [SPEC])
    )
    url, _, body = fake.calls[0]
    assert url == "http://127.0.0.1:11434/api/chat"
    assert body["stream"] is False and body["tools"][0]["function"]["name"] == "read_note"
    assert reply.tool_calls == [ToolCall("call-0", "read_note", {"path": "a.md"})]


def test_ollama_history_conversion() -> None:
    messages = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [ToolCall("c", "read_note", {"path": "a.md"})],
        },
        {"role": "tool", "tool_call_id": "c", "name": "read_note", "content": "body"},
    ]
    converted = to_ollama(messages)
    assert converted[0]["tool_calls"] == [
        {"function": {"name": "read_note", "arguments": {"path": "a.md"}}}
    ]
    assert converted[1] == {"role": "tool", "content": "body", "tool_name": "read_note"}
    assert parse_ollama({"message": {"content": "ok"}}).text == "ok"


def test_http_error_names_the_host_not_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(request: urllib.request.Request, timeout: float) -> None:
        raise urllib.error.HTTPError(request.full_url, 401, "denied", {}, io.BytesIO(b""))

    monkeypatch.setattr(base.urllib.request, "urlopen", refuse)
    headers = {"x-api-key": "sk-secret"}
    with pytest.raises(ProviderError) as info:
        base._post("https://api.anthropic.com/v1/messages", headers, {}, 1.0)
    assert "HTTP 401" in str(info.value)
    assert "sk-secret" not in str(info.value)


def test_unreachable_host_is_a_provider_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def down(request: urllib.request.Request, timeout: float) -> None:
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(base.urllib.request, "urlopen", down)
    with pytest.raises(ProviderError, match="could not reach 127.0.0.1:11434"):
        base._post("http://127.0.0.1:11434/api/chat", {}, {}, 1.0)
