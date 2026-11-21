"""B.06: start-up time and memory are measured per release and held to a budget."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import measure_startup  # noqa: E402

from core import __version__  # noqa: E402

# Loose on purpose: a busy computer must not fail the test; a real regression (ten times slower) will.
FIRST_ANSWER_MS = 5000
MEMORY_MB = 200


def test_every_release_has_a_measurement_file() -> None:
    saved = json.loads((ROOT / "docs" / "perf" / f"{__version__}.json").read_text(encoding="utf-8"))
    assert saved["version"] == __version__
    assert saved["backend_first_answer_ms"]["median"] > 0


@pytest.mark.skipif(sys.platform != "linux", reason="the memory number reads /proc")
def test_the_backend_answers_its_first_call_within_the_budget() -> None:
    took, memory = measure_startup.one_run()
    assert took < FIRST_ANSWER_MS, f"first answer took {took} ms"
    assert memory is not None and memory < MEMORY_MB, f"backend holds {memory} MB"
