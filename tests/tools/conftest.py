import threading
from pathlib import Path

import pytest

from core.vault import Indexer, open_index


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    (root / "projects").mkdir(parents=True)
    (root / "projects" / "alpha.md").write_text("# Alpha\n\nLinks to [[beta]].\n", encoding="utf-8")
    (root / "beta.md").write_text("# Beta\n", encoding="utf-8")
    return root


@pytest.fixture
def indexer(vault: Path, tmp_path: Path) -> Indexer:
    index = open_index(vault, tmp_path / "storage")
    index.full_sync()
    yield index
    index.store.close()


@pytest.fixture
def lock() -> threading.RLock:
    return threading.RLock()
