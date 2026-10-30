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
