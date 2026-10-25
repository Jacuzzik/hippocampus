"""Claude over the Anthropic Messages API, with the user's own API key."""

from typing import Any

from ai.providers.base import ProviderError, Reply, ToolCall, ToolSpec, post_json

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
MAX_TOKENS = 1024


class ClaudeProvider:
    name = "claude"

    def __init__(self, api_key: str, model: str, url: str = API_URL, timeout: float = 60.0) -> None:
        self._api_key = api_key  # never logged, never in an error message
        self.model = model
        self.url = url
        self.timeout = timeout

    async def chat(self, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> Reply:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "messages": to_claude(messages),
        }
        if tools:
            body["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ]
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }
        return parse_claude(await post_json(self.url, headers, body, self.timeout))


def to_claude(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for message in messages:
        role = message["role"]
        if role == "user":
            out.append({"role": "user", "content": message["content"]})
        elif role == "assistant":
            blocks: list[dict[str, Any]] = []
            if message["content"]:
                blocks.append({"type": "text", "text": message["content"]})
            for call in message.get("tool_calls", []):
                blocks.append(
                    {"type": "tool_use", "id": call.id, "name": call.name, "input": call.args}
                )
            out.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            result = {
                "type": "tool_result",
                "tool_use_id": message["tool_call_id"],
                "content": message["content"],
            }
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                out[-1]["content"].append(result)
            else:
                out.append({"role": "user", "content": [result]})
    return out


def parse_claude(data: dict[str, Any]) -> Reply:
    try:
        blocks = data["content"]
        text = "".join(b.get("text", "") for b in blocks if b["type"] == "text")
        calls = [
            ToolCall(id=b["id"], name=b["name"], args=dict(b["input"]))
            for b in blocks
            if b["type"] == "tool_use"
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderError("Claude sent a reply in an unexpected shape") from exc
    return Reply(text=text, tool_calls=calls)
