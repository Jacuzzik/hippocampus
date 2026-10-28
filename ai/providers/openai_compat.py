"""OpenAI-style chat endpoints. One provider class serves every service that speaks this API.

Each preset is a service with its base URL and model IDs the user can pick. The IDs are
defaults, not a guarantee: a model the service has retired fails with its HTTP error.
"""

import json
from dataclasses import dataclass
from typing import Any

from ai.providers.base import ProviderError, Reply, ToolCall, ToolSpec, post_json


@dataclass(frozen=True)
class Preset:
    label: str
    base_url: str
    models: tuple[str, ...]
    needs_key: bool = True


PRESETS: dict[str, Preset] = {
    "openai": Preset(
        "OpenAI",
        "https://api.openai.com/v1",
        ("gpt-4.1", "gpt-4.1-mini", "gpt-4o", "gpt-4o-mini", "o3-mini"),
    ),
    "xai": Preset("xAI Grok", "https://api.x.ai/v1", ("grok-3", "grok-3-mini", "grok-2-latest")),
    "moonshot": Preset(
        "Moonshot Kimi", "https://api.moonshot.ai/v1", ("kimi-k2-0905-preview", "moonshot-v1-8k")
    ),
    "gemini": Preset(
        "Google Gemini",
        "https://generativelanguage.googleapis.com/v1beta/openai",
        ("gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"),
    ),
    "qwen": Preset(
        "Alibaba Qwen",
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        ("qwen-max", "qwen-plus", "qwen-turbo"),
    ),
    "deepseek": Preset(
        "DeepSeek", "https://api.deepseek.com/v1", ("deepseek-chat", "deepseek-reasoner")
    ),
    "mistral": Preset(
        "Mistral",
        "https://api.mistral.ai/v1",
        ("mistral-large-latest", "mistral-small-latest", "codestral-latest"),
    ),
    "groq": Preset(
        "Groq",
        "https://api.groq.com/openai/v1",
        ("llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b"),
    ),
    "openrouter": Preset(
        "OpenRouter",
        "https://openrouter.ai/api/v1",
        (
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-4o",
            "google/gemini-2.5-pro",
            "meta-llama/llama-3.3-70b-instruct",
        ),
    ),
    "lmstudio": Preset("LM Studio (local)", "http://127.0.0.1:1234/v1", (), needs_key=False),
    "vllm": Preset("vLLM (local)", "http://127.0.0.1:8000/v1", (), needs_key=False),
}


class OpenAICompatProvider:
    def __init__(
        self, name: str, base_url: str, model: str, api_key: str | None, timeout: float = 60.0
    ) -> None:
        self.name = name
        self.model = model
        self.url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key  # never logged, never in an error message
        self.timeout = timeout

    async def chat(self, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> Reply:
        body: dict[str, Any] = {"model": self.model, "messages": to_openai(messages)}
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
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"
        return parse_openai(await post_json(self.url, headers, body, self.timeout))


def to_openai(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for message in messages:
        role = message["role"]
        if role == "assistant":
            entry: dict[str, Any] = {"role": "assistant", "content": message["content"] or None}
            calls = message.get("tool_calls", [])
            if calls:
                entry["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(c.args)},
                    }
                    for c in calls
                ]
            out.append(entry)
        elif role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": message["tool_call_id"],
                    "content": message["content"],
                }
            )
        else:
            out.append({"role": "user", "content": message["content"]})
    return out


def parse_openai(data: dict[str, Any]) -> Reply:
    try:
        message = data["choices"][0]["message"]
        calls = []
        for c in message.get("tool_calls") or []:
            args = json.loads(c["function"].get("arguments") or "{}")
            if not isinstance(args, dict):
                raise ValueError("tool arguments are not an object")
            calls.append(ToolCall(id=c["id"], name=c["function"]["name"], args=args))
        text = message.get("content") or ""
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderError("the model provider sent a reply in an unexpected shape") from exc
    tokens = int((data.get("usage") or {}).get("total_tokens") or 0)
    return Reply(text=text, tool_calls=calls, tokens=tokens)
