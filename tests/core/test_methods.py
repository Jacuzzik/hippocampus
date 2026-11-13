from pathlib import Path

import pytest

from core.__main__ import Session
from core.methods import METHODS
from core.settings import Settings


def session(tmp_path: Path) -> Session:
    return Session(
        storage=tmp_path / "storage", settings=Settings(), settings_path=tmp_path / "settings.toml"
    )


def test_the_table_and_the_handlers_name_the_same_methods(tmp_path: Path) -> None:
    handlers = set(session(tmp_path).handlers())
    assert handlers - set(METHODS) == set(), "a handler is missing from core/methods.py"
    assert set(METHODS) - handlers == set(), "core/methods.py names a method with no handler"


def test_every_method_has_a_line_of_help() -> None:
    for name, method in METHODS.items():
        assert method.text.strip().endswith("."), f"{name} needs one plain sentence of help"


def test_an_unknown_method_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown method: 'nope'"):
        session(tmp_path).dispatch({"method": "nope"})
    with pytest.raises(ValueError, match="unknown method: None"):
        session(tmp_path).dispatch({})


@pytest.mark.parametrize(
    ("method", "words"),
    [
        ("open", '"open" needs a "vault" folder path'),
        ("chat_history", '"chat_history" needs an "agent" id'),
        ("terminal_resize", '"terminal_resize" needs an "agent" id'),
        ("new_session", '"new_session" needs an "agent" id'),
    ],
)
def test_a_missing_key_is_refused_before_anything_runs(
    tmp_path: Path, method: str, words: str
) -> None:
    one = session(tmp_path)
    with pytest.raises(ValueError, match=words):
        one.dispatch({"method": method})
    with pytest.raises(ValueError, match=words):
        one.dispatch({"method": method, "agent": 3, "vault": ""})


def test_a_method_with_its_keys_runs(tmp_path: Path) -> None:
    assert session(tmp_path).dispatch({"method": "engine"})["provider"]
