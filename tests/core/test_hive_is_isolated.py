from pathlib import Path

from core import __main__ as sidecar
from core.settings import Settings


def test_a_session_in_a_test_never_points_at_the_real_hive(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    assert Path.home() / ".hippocampus" not in session.hive_path.parents
    assert tmp_path in session.hive_path.parents
