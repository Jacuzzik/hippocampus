import pytest

from core import terminal


def test_unknown_provider_is_refused() -> None:
    assert "does not run" in terminal.engine_problem("nope")


def test_missing_cli_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(terminal.shutil, "which", lambda name: None)
    assert "claude is not installed" in terminal.engine_problem("claude")


def test_key_provider_without_saved_key_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    import ai.keys

    monkeypatch.setattr(terminal.shutil, "which", lambda name: "/bin/opencode")
    monkeypatch.setattr(ai.keys, "get_key", lambda provider: None)
    assert "No openai key is saved" in terminal.engine_problem("openai")


def test_key_provider_with_key_and_opencode_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    import ai.keys

    monkeypatch.setattr(terminal.shutil, "which", lambda name: "/bin/opencode")
    monkeypatch.setattr(ai.keys, "get_key", lambda provider: "sk-test")
    assert terminal.engine_problem("openai") is None


def test_ollama_must_be_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(terminal.shutil, "which", lambda name: "/bin/ollama")
    monkeypatch.setattr(terminal, "_ollama_running", lambda: False)
    assert "Ollama is not running" in terminal.engine_problem("ollama")
    monkeypatch.setattr(terminal, "_ollama_running", lambda: True)
    assert terminal.engine_problem("ollama") is None
