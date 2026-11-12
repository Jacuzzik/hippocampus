import time
from pathlib import Path

from core import __main__ as sidecar
from core.settings import Settings
from core.vault.changes import ChangeFlag


def wait_for(check, seconds: float = 5.0) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        if check():
            return True
        time.sleep(0.05)
    return False


def test_the_flag_is_up_once_then_down_until_a_file_changes(tmp_path: Path) -> None:
    flag = ChangeFlag(tmp_path, debounce_ms=50, step_ms=20)
    try:
        assert flag.take() is True  # the first look always syncs
        assert flag.take() is False  # nothing changed since
        time.sleep(0.3)  # let the watch start
        (tmp_path / "new.md").write_text("# New\n", encoding="utf-8")
        assert wait_for(flag.take), "a new note did not raise the flag"
        assert flag.take() is False
    finally:
        flag.stop()


def test_a_broken_watch_keeps_the_flag_up(tmp_path: Path) -> None:
    flag = ChangeFlag(tmp_path / "missing")  # the watch cannot start on a folder that is not there
    assert wait_for(lambda: flag.broken or not flag._thread.is_alive())
    assert (
        flag.take() is True and flag.take() is True
    )  # every look syncs, as before the watch existed


def test_the_graph_walks_the_vault_only_after_a_change(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("# A\n", encoding="utf-8")
    session = sidecar.Session(tmp_path / "storage", Settings(), emit=lambda e: None)
    session.open(vault)
    try:
        calls = {"n": 0}
        real = session.indexer.full_sync

        def counted():
            calls["n"] += 1
            return real()

        session.indexer.full_sync = counted  # type: ignore[method-assign]
        session.graph()
        first = calls["n"]
        session.graph()
        session.graph()
        assert calls["n"] == first, "an unchanged vault was walked again"
        time.sleep(0.3)
        (vault / "b.md").write_text("# B\n", encoding="utf-8")
        assert wait_for(lambda: len(session.graph()["nodes"]) == 2), (
            "a new note never reached the graph"
        )
    finally:
        session.close()
