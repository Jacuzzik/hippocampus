import tomllib
from pathlib import Path

import pytest

from core.settings import Settings, load_settings


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


def test_repo_settings_file_has_no_secret_field() -> None:
    data = tomllib.loads(
        (Path(__file__).parents[2] / "config" / "settings.toml").read_text("utf-8")
    )
    names = [name for section in data.values() for name in section]
    assert not [
        n for n in names if any(word in n for word in ("key", "secret", "token", "password"))
    ]


def test_env_vault_overrides_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config"
    config.mkdir()
    (config / "settings.toml").write_text('[vault]\npath = "brains/mine"\n', encoding="utf-8")
    monkeypatch.setenv("HIPPOCAMPUS_VAULT", str(tmp_path / "elsewhere"))
    assert load_settings(config / "settings.toml").vault == tmp_path / "elsewhere"
