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
