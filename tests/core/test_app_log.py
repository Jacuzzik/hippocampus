import logging
from pathlib import Path

import pytest

from core import __main__ as sidecar
from core import app_log
from core.settings import Settings


def test_log_lines_reach_the_file_and_come_back_oldest_first(tmp_path: Path) -> None:
    detach = app_log.attach(tmp_path)
    try:
        log = logging.getLogger("hippocampus.test")
        log.info("first line")
        log.warning("second line")
    finally:
        detach()
    lines = app_log.tail(tmp_path)
    assert [line.split(": ", 1)[1] for line in lines] == ["first line", "second line"]
    assert "WARNING hippocampus.test" in lines[1]


def test_keys_are_masked_before_they_are_written(tmp_path: Path) -> None:
    detach = app_log.attach(tmp_path)
    try:
        logging.getLogger("hippocampus.test").info(
            "key %s and Bearer abcdefghijklmnop123", "sk-ant-abcdef1234567890"
        )
    finally:
        detach()
    text = app_log.path(tmp_path).read_text(encoding="utf-8")
    assert "sk-ant" not in text and "abcdefghijklmnop123" not in text
    assert text.count("[key hidden]") == 2


def test_tail_keeps_only_the_newest_lines_and_an_absent_file_is_empty(tmp_path: Path) -> None:
    assert app_log.tail(tmp_path) == []
    file = app_log.path(tmp_path)
    file.parent.mkdir(parents=True)
    file.write_text("".join(f"line {n}\n" for n in range(500)), encoding="utf-8")
    assert app_log.tail(tmp_path, 3) == ["line 497", "line 498", "line 499"]
    assert len(app_log.tail(tmp_path, 10**9)) == 500  # capped at TAIL_MAX, and the file has fewer


def test_the_logs_method_returns_the_path_and_lines(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    file = app_log.path(tmp_path)
    file.parent.mkdir(parents=True)
    file.write_text("a\nb\n", encoding="utf-8")
    assert session.dispatch({"method": "logs", "limit": 1}) == {"path": str(file), "lines": ["b"]}
    with pytest.raises(ValueError):
        session.dispatch({"method": "logs", "limit": "many"})
