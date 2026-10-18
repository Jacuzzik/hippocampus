from pathlib import Path
from typing import Any

import pytest

from fixtures.make_sample_vault import generate


@pytest.fixture
def sample_vault(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    vault = tmp_path / "vault"
    return vault, generate(vault)


@pytest.fixture
def storage(tmp_path: Path) -> Path:
    return tmp_path / "storage"
