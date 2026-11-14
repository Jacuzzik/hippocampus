"""Settings: the whole-number settings a page may change are checked, written and used at once."""

import tomllib
from pathlib import Path

import pytest

from core.settings import NUMBER_FIELDS, NUMBER_LIMITS, SCHEMA_KEYS, load_settings, save_number


def test_every_changeable_number_is_a_known_setting() -> None:
    assert set(NUMBER_LIMITS) == set(NUMBER_FIELDS)
    assert set(NUMBER_LIMITS) <= SCHEMA_KEYS


def test_a_number_is_written_and_the_rest_of_the_file_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "config" / "settings.toml"
    path.parent.mkdir()
    path.write_text('[ai]\nprovider = "claude"\nmax_tool_calls = 20\n', encoding="utf-8")
    save_number("ai.max_tool_calls", 35, path)
    save_number("inbox.delivery_seconds", 10, path)  # the table is not in the file yet
    save_number("memory.max_bytes", 64000, path)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["ai"] == {"provider": "claude", "max_tool_calls": 35}
    loaded = load_settings(path)
    assert (loaded.max_tool_calls, loaded.delivery_seconds, loaded.memory_max_bytes) == (
        35,
        10,
        64000,
    )


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("ai.max_tool_calls", 0),
        ("ai.max_tool_calls", 201),
        ("inbox.delivery_seconds", 61),
        ("memory.max_bytes", 999),
        ("memory.max_bytes", True),
        ("memory.max_bytes", "64000"),
        ("vault.path", 3),
    ],
)
def test_a_bad_number_is_refused_and_nothing_is_written(
    tmp_path: Path, key: str, value: object
) -> None:
    path = tmp_path / "config" / "settings.toml"
    path.parent.mkdir()
    path.write_text("[ai]\nmax_tool_calls = 20\n", encoding="utf-8")
    with pytest.raises(ValueError):
        save_number(key, value, path)
    assert path.read_text(encoding="utf-8") == "[ai]\nmax_tool_calls = 20\n"


def test_a_delivery_interval_out_of_range_in_the_file_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "config" / "settings.toml"
    path.parent.mkdir()
    path.write_text("[inbox]\ndelivery_seconds = 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="inbox.delivery_seconds"):
        load_settings(path)


def test_the_call_changes_the_running_settings_and_the_view(tmp_path: Path) -> None:
    import core.__main__ as sidecar
    from core.settings import Settings

    path = tmp_path / "config" / "settings.toml"
    path.parent.mkdir()
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None, settings_path=path)
    done = session.dispatch({"method": "set_number", "key": "inbox.delivery_seconds", "value": 9})
    assert done == {"key": "inbox.delivery_seconds", "value": 9}
    view = session.dispatch({"method": "settings"})
    assert view["inbox"] == {"delivery_seconds": 9}
    assert view["limits"]["inbox.delivery_seconds"] == [1, 60]
    assert load_settings(path).delivery_seconds == 9
    with pytest.raises(ValueError, match="from 1 to 60"):
        session.dispatch({"method": "set_number", "key": "inbox.delivery_seconds", "value": 600})
