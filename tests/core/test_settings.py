import tomllib
from pathlib import Path

import pytest

from core.settings import Settings, load_settings, save_vault


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    settings = load_settings(tmp_path / "config" / "settings.toml")
    assert settings == Settings()
    assert settings.vault is None


def test_vault_path_is_relative_to_the_repo_root(tmp_path: Path) -> None:
    config = tmp_path / "config"
    config.mkdir()
    (config / "settings.toml").write_text(
        '[vault]\npath = "brains/mine"\n[ai]\nollama_model = "llama3.2:3b"\n', encoding="utf-8"
    )
    settings = load_settings(config / "settings.toml")
    assert settings.vault == (tmp_path / "brains" / "mine").resolve()
    assert settings.ollama_model == "llama3.2:3b"
    assert settings.claude_model == Settings().claude_model


def test_unknown_settings_version_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "settings.toml").write_text("settings_version = 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="settings_version must be 1"):
        load_settings(tmp_path / "settings.toml")


def test_repo_settings_file_has_no_secret_field() -> None:
    data = tomllib.loads(
        (Path(__file__).parents[2] / "config" / "settings.toml").read_text("utf-8")
    )
    names = [name for section in data.values() if isinstance(section, dict) for name in section]
    assert not [
        n for n in names if any(word in n for word in ("key", "secret", "token", "password"))
    ]


def test_env_vault_overrides_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config"
    config.mkdir()
    (config / "settings.toml").write_text('[vault]\npath = "brains/mine"\n', encoding="utf-8")
    monkeypatch.setenv("HIPPOCAMPUS_VAULT", str(tmp_path / "elsewhere"))
    assert load_settings(config / "settings.toml").vault == tmp_path / "elsewhere"


def test_provider_defaults_to_claude_and_rejects_unknown_names(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    assert load_settings(config).provider == "claude"
    config.write_text('[ai]\nprovider = "groq"\nprovider_model = "llama-3.1-8b-instant"\n', "utf-8")
    settings = load_settings(config)
    assert (settings.provider, settings.provider_model) == ("groq", "llama-3.1-8b-instant")
    config.write_text('[ai]\nprovider = "nope"\n', "utf-8")
    with pytest.raises(ValueError, match="ai.provider"):
        load_settings(config)


def test_save_vault_writes_the_path_and_keeps_other_sections(tmp_path: Path) -> None:
    path = tmp_path / "config" / "settings.toml"
    path.parent.mkdir()
    path.write_text('[vault]\npath = "brains/old"\n\n[ai]\nprovider = "claude"\n', encoding="utf-8")
    folder = tmp_path / 'My "brain"'
    save_vault(folder, path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["vault"] == {"path": str(folder)}
    assert data["ai"] == {"provider": "claude"}
    assert load_settings(path).vault == folder.resolve()


def test_engine_switch_refuses_unknown_provider_and_model(tmp_path: Path) -> None:
    from core.settings import save_engine

    path = tmp_path / "settings.toml"
    path.write_text(
        '[ai]\nprovider = "claude"\nclaude_model = "claude-sonnet-5-5"\n', encoding="utf-8"
    )
    before = path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="not a provider"):
        save_engine("nope", "x", path)
    with pytest.raises(ValueError, match="not a model"):
        save_engine("claude", "made-up-model", path)
    assert path.read_text(encoding="utf-8") == before
    save_engine("claude", "claude-haiku-5-5", path)
    assert (
        tomllib.loads(path.read_text(encoding="utf-8"))["ai"]["claude_model"] == "claude-haiku-5-5"
    )


def test_engine_models_match_the_app_list() -> None:
    import re

    from core.settings import ENGINE_MODELS

    source = (
        Path(__file__).resolve().parents[2] / "app" / "ui" / "control" / "model.ts"
    ).read_text(encoding="utf-8")
    block = source.split("export const AGENT_MODELS", 1)[1].split("\n};", 1)[0]
    listed: dict[str, tuple[str, ...]] = {}
    # A list may be wrapped over several lines by the formatter, so match across lines.
    for key, items in re.findall(r'^\s*"?([\w.-]+)"?:\s*\[(.*?)\]', block, re.M | re.S):
        listed[key] = tuple(re.findall(r'"([^"]*)"', items))
    assert listed == ENGINE_MODELS


def test_every_key_in_the_real_settings_file_is_in_the_schema() -> None:
    import tomllib

    from core.settings import SETTINGS_PATH, unknown_keys

    data = tomllib.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    assert unknown_keys(data) == []


def test_every_settings_field_has_a_schema_row_and_defaults_agree() -> None:
    from dataclasses import fields

    from core.settings import SCHEMA, Settings

    keys = {str(row["key"]): row for row in SCHEMA}
    assert all(row["help"] and row["type"] for row in SCHEMA)
    defaults = Settings()
    # Settings field -> the keys that carry it in the file.
    by_field = {
        "settings_version": ["settings_version"],
        "vault": ["vault.path"],
        "provider": ["ai.provider"],
        "provider_model": ["ai.provider_model"],
        "claude_model": ["ai.claude_model"],
        "ollama_host": ["ai.ollama_host"],
        "ollama_model": ["ai.ollama_model"],
        "max_tool_calls": ["ai.max_tool_calls"],
        "allowed_tools": ["ai.allowed_tools"],
        "network_mode": ["network.mode"],
        "budget": [k for k in keys if k.startswith("budget.") and "assistant" not in k],
        "assistant_budget": [k for k in keys if k.startswith("budget.assistant.")],
        "memory_max_bytes": ["memory.max_bytes"],
        "agent_shell": ["agents.shell"],
    }
    assert set(by_field) == {f.name for f in fields(Settings)}, (
        "a new Settings field needs a schema row"
    )
    for field, rows in by_field.items():
        assert rows and all(k in keys for k in rows), field
    for field in (
        "provider",
        "claude_model",
        "ollama_host",
        "max_tool_calls",
        "memory_max_bytes",
        "agent_shell",
        "network_mode",
    ):
        key = by_field[field][0]
        assert keys[key]["default"] == getattr(defaults, field), key


def test_an_unknown_key_is_warned_about_not_fatal(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "settings.toml"
    path.write_text('[ai]\nprovider = "claude"\ncolour = "red"\n', encoding="utf-8")
    with caplog.at_level("WARNING"):
        assert load_settings(path).provider == "claude"
    assert "ai.colour is not a setting" in caplog.text


def test_the_settings_call_returns_the_schema(tmp_path: Path) -> None:
    from core.__main__ import Session

    session = Session(
        storage=tmp_path / "s", settings=Settings(), settings_path=tmp_path / "x.toml"
    )
    schema = session.settings_view()["schema"]
    assert {"key": "agents.shell", "type": "bool", "default": False}.items() <= next(
        r for r in schema if r["key"] == "agents.shell"
    ).items()
    session.close()
