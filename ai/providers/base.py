"""The provider interface and the shared HTTP helper.

Messages are plain dicts in one neutral shape, and each provider converts them:
  {"role": "user", "content": str}
  {"role": "assistant", "content": str, "tool_calls": [ToolCall, ...]}
  {"role": "tool", "tool_call_id": str, "name": str, "content": str}
"""

import asyncio
import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

from ai import network

logger = logging.getLogger("hippocampus.ai")


class ProviderError(Exception):
    """A provider could not answer. The router may fall back to another one."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class Reply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    # Tokens the provider billed for this reply (input plus output); 0 when it did not say.
    tokens: int = 0


class NetworkBlocked(ProviderError):
    """A model call the network switch does not allow. Nothing leaves the machine."""


class Provider(Protocol):
    name: str

    async def chat(self, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> Reply: ...


async def post_json(
    url: str, headers: dict[str, str], body: dict[str, Any], timeout: float
) -> dict[str, Any]:
    """POST a JSON body and return the JSON reply. Errors name the host, never the key."""
    return await asyncio.to_thread(_post, url, headers, body, timeout)


def _post(
    url: str, headers: dict[str, str], body: dict[str, Any], timeout: float
) -> dict[str, Any]:
    host = urllib.request.urlsplit(url).netloc
    if not network.allows_model_calls():
        raise NetworkBlocked(f"network is {network.mode().capitalize()}: no call to {host}")
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"{host} answered HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise ProviderError(f"could not reach {host}: {exc}") from exc
    except ValueError as exc:
        raise ProviderError(f"{host} sent a reply that is not JSON") from exc
    if not isinstance(data, dict):
        raise ProviderError(f"{host} sent an unexpected reply")
    return data
