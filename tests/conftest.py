from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from ai import network
from fixtures.make_sample_vault import generate


@pytest.fixture
def sample_vault(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    vault = tmp_path / "vault"
    return vault, generate(vault)


@pytest.fixture
def storage(tmp_path: Path) -> Path:
    return tmp_path / "storage"


@pytest.fixture(autouse=True)
def network_open() -> Iterator[None]:
    """Provider tests reach the HTTP helper. The network switch tests set their own mode."""
    network.set_mode("open")
    yield
    network.set_mode("off")


@pytest.fixture(autouse=True)
def own_hive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Every test gets its own hive folder. Without this a Session reads and writes the real
    ~/.hippocampus/hive, so a test could send messages to the user's running agents."""
    from core import __main__ as sidecar
    from core import settings

    hive = tmp_path / "hive-home" / "hive"
    # A backend started as a separate process by a test reads the folder from the environment.
    monkeypatch.setenv("HIPPOCAMPUS_HIVE", str(hive))
    monkeypatch.setattr(settings, "HIVE_DIR", hive)
    monkeypatch.setattr(sidecar, "HIVE_DIR", hive)
    return hive
