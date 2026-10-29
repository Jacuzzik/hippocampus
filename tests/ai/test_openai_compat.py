import asyncio
import json
from typing import Any

import pytest

from ai.providers.base import ProviderError, ToolCall, ToolSpec
from ai.providers.openai_compat import PRESETS, OpenAICompatProvider, parse_openai, to_openai

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


def test_request_goes_to_the_preset_url_with_the_key_in_a_header_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeHTTP({"choices": [{"message": {"content": "hi"}}]})
    monkeypatch.setattr("ai.providers.openai_compat.post_json", fake)
    provider = OpenAICompatProvider("groq", "https://api.groq.com/openai/v1/", "m1", "gsk-secret")
    reply = asyncio.run(provider.chat([{"role": "user", "content": "hello"}], [SPEC]))
    url, headers, body = fake.calls[0]
    assert reply.text == "hi"
    assert url == "https://api.groq.com/openai/v1/chat/completions"
    assert headers["authorization"] == "Bearer gsk-secret"
    assert "gsk-secret" not in json.dumps(body) and "gsk-secret" not in url
    assert body["model"] == "m1"
    assert body["tools"][0]["function"]["parameters"] == SPEC.parameters


def test_local_preset_sends_no_authorization_header(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeHTTP({"choices": [{"message": {"content": "hi"}}]})
    monkeypatch.setattr("ai.providers.openai_compat.post_json", fake)
    provider = OpenAICompatProvider("lmstudio", "http://127.0.0.1:1234/v1", "local", None)
    asyncio.run(provider.chat([{"role": "user", "content": "x"}], []))
    _, headers, body = fake.calls[0]
    assert "authorization" not in headers and "tools" not in body


def test_tool_call_round_trip() -> None:
    call = ToolCall("call_1", "read_note", {"path": "a.md"})
    messages = [
        {"role": "user", "content": "read a"},
        {"role": "assistant", "content": "", "tool_calls": [call]},
        {"role": "tool", "tool_call_id": "call_1", "name": "read_note", "content": "text"},
    ]
    converted = to_openai(messages)
    assert converted[1]["content"] is None
    assert converted[1]["tool_calls"][0]["function"] == {
        "name": "read_note",
        "arguments": '{"path": "a.md"}',
    }
    assert converted[2] == {"role": "tool", "tool_call_id": "call_1", "content": "text"}

    reply = parse_openai(
        {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_2",
                                "type": "function",
                                "function": {"name": "read_note", "arguments": '{"path": "b.md"}'},
                            }
                        ],
                    }
                }
            ]
        }
    )
    assert reply.text == ""
    assert reply.tool_calls == [ToolCall("call_2", "read_note", {"path": "b.md"})]


@pytest.mark.parametrize(
    "data",
    [
        {"choices": []},
        {"nope": 1},
        {
            "choices": [
                {
                    "message": {
                        "tool_calls": [{"id": "x", "function": {"name": "n", "arguments": "[1]"}}]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "message": {
                        "tool_calls": [{"id": "x", "function": {"name": "n", "arguments": "{bad"}}]
                    }
                }
            ]
        },
    ],
)
def test_unexpected_reply_is_a_provider_error(data: dict[str, Any]) -> None:
    with pytest.raises(ProviderError, match="unexpected shape"):
        parse_openai(data)


def test_catalog_offers_twenty_or_more_models() -> None:
    assert sum(len(p.models) for p in PRESETS.values()) >= 20
    for name, preset in PRESETS.items():
        assert preset.base_url.startswith(("https://", "http://127.0.0.1")), name
