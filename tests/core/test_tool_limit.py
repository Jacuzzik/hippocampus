from pathlib import Path
from typing import Any

import pytest

from ai.providers.base import Reply, ToolCall
from ai.router import Router
from core import __main__ as sidecar
from core.settings import Settings, load_settings


class Steps:
    """A provider that answers from a script and records how many messages each call saw."""

    name = "steps"

    def __init__(self, *steps: Reply) -> None:
        self.steps = list(steps)
        self.seen: list[int] = []

    async def chat(self, messages: list[dict[str, Any]], tools: list[Any]) -> Reply:
        self.seen.append(len(messages))
        return self.steps.pop(0)


def _calls(*ids: str) -> Reply:
    # No vault is open in these tests, so each call is answered with "no tool" and still counts.
    return Reply("", [ToolCall(i, "missing", {}) for i in ids])


def _session(
    storage: Path, provider: Steps, limit: int, monkeypatch: pytest.MonkeyPatch
) -> sidecar.Session:
    monkeypatch.setattr(sidecar, "build_router", lambda settings, key, agent="hippo": Router(None, provider))
    return sidecar.Session(storage, Settings(max_tool_calls=limit))


def test_chat_pauses_at_the_tool_limit_and_continue_resumes(
    storage: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = Steps(_calls("a", "b"), Reply("all done"))
    session = _session(storage, provider, 2, monkeypatch)
    paused = session.chat({"chat": 1, "text": "do many things"})
    assert paused == {"reply": "", "stopped": False, "limit": 2}
    done = session.chat({"chat": 1, "text": "Continue.", "continue": True})
    assert done == {"reply": "all done", "stopped": False}
    # The second request carried on from the first: user, assistant, two tool results, new turn.
    assert provider.seen[1] == 5


def test_calls_past_the_limit_are_not_run(storage: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = Steps(_calls("a", "b", "c"))
    session = _session(storage, provider, 2, monkeypatch)
    assert session.chat({"chat": 1, "text": "go"})["limit"] == 2
    assert session.paused is not None
    results = [m["content"] for m in session.paused if m["role"] == "tool"]
    assert results[2].startswith("Not run")


def test_continue_needs_a_paused_request(storage: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session(storage, Steps(), 2, monkeypatch)
    with pytest.raises(ValueError, match="nothing is paused"):
        session.chat({"chat": 1, "text": "Continue.", "continue": True})


def test_max_tool_calls_comes_from_config(tmp_path: Path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    path = config / "settings.toml"
    path.write_text("[ai]\nmax_tool_calls = 5\n", encoding="utf-8")
    assert load_settings(path).max_tool_calls == 5
    assert Settings().max_tool_calls == 20
    path.write_text("[ai]\nmax_tool_calls = 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="max_tool_calls"):
        load_settings(path)
