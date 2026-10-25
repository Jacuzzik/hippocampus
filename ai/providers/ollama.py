"""Ollama on this machine: the free, offline fallback."""

from typing import Any

from ai.providers.base import ProviderError, Reply, ToolCall, ToolSpec, post_json


class OllamaProvider:
    name = "ollama"

    def __init__(
        self, model: str, host: str = "http://127.0.0.1:11434", timeout: float = 120.0
    ) -> None:
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    async def chat(self, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> Reply:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": to_ollama(messages),
            "stream": False,
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
        headers = {"content-type": "application/json"}
        return parse_ollama(await post_json(f"{self.host}/api/chat", headers, body, self.timeout))


def to_ollama(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for message in messages:
        role = message["role"]
        if role == "assistant":
            entry: dict[str, Any] = {"role": "assistant", "content": message["content"]}
            calls = message.get("tool_calls", [])
            if calls:
                entry["tool_calls"] = [
                    {"function": {"name": c.name, "arguments": c.args}} for c in calls
                ]
            out.append(entry)
        elif role == "tool":
            out.append(
                {"role": "tool", "content": message["content"], "tool_name": message["name"]}
            )
        else:
            out.append({"role": "user", "content": message["content"]})
    return out


def parse_ollama(data: dict[str, Any]) -> Reply:
    try:
        message = data["message"]
        calls = [
            ToolCall(
                id=f"call-{i}",
                name=c["function"]["name"],
                args=dict(c["function"].get("arguments") or {}),
            )
            for i, c in enumerate(message.get("tool_calls") or [])
        ]
        text = message.get("content") or ""
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderError("Ollama sent a reply in an unexpected shape") from exc
    return Reply(text=text, tool_calls=calls)
