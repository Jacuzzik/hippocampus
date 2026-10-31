import json
from pathlib import Path
from typing import Any

import pytest

from ai.providers.base import Reply
from ai.router import Router
from core import __main__ as sidecar
from core.settings import Settings


class Recorder:
    """A non-Claude provider stand-in that records the messages it is sent."""

    name = "fake-ollama"

    def __init__(self) -> None:
        self.sent: list[list[dict[str, Any]]] = []

    async def chat(self, messages: list[dict[str, Any]], tools: list[Any]) -> Reply:
        self.sent.append([dict(m) for m in messages])
        return Reply(text="ok")


def test_saved_chat_turns_reach_a_non_claude_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorder = Recorder()
    monkeypatch.setattr(
        sidecar, "build_router", lambda settings, key, agent="hippo": Router(None, recorder)
    )
    monkeypatch.setattr(sidecar, "get_api_key", lambda: None)
    session = sidecar.Session(
        tmp_path, settings=Settings(), settings_path=tmp_path / "settings.toml"
    )

    turns = [
        {"role": "user", "text": "first question"},
        {"role": "assistant", "text": "first answer"},
        {"role": "user", "text": "second question"},
        {"role": "assistant", "text": "second answer"},
    ]
    saved = sidecar.handle(
        session,
        json.dumps(
            {
                "id": 1,
                "method": "chat_history_save",
                "agent": "hippo",
                "sessions": [{"session": "s1", "messages": turns}],
            }
        ),
    )
    assert saved == {"id": 1, "result": {"saved": True}}

    answer = sidecar.handle(
        session, json.dumps({"id": 2, "method": "chat", "agent": "hippo", "text": "third question"})
    )
    assert answer["result"]["reply"] == "ok"

    sent = recorder.sent[-1]
    assert sent[:4] == [{"role": t["role"], "content": t["text"]} for t in turns]
    assert sent[4] == {"role": "user", "content": "third question"}
