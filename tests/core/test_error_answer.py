import subprocess

from core.__main__ import ERROR_HINTS, error_answer
from core.memory import NotSetUp


def test_every_failure_has_a_message_and_a_code() -> None:
    answer = error_answer(3, ValueError("no webhook with id 'x'"))
    assert answer == {"id": 3, "error": "no webhook with id 'x'", "code": "ValueError"}


def test_a_known_failure_also_says_what_to_do_next() -> None:
    answer = error_answer(4, NotSetUp("memory search needs an embedding model"))
    assert answer["code"] == "NotSetUp"
    assert answer["hint"] == ERROR_HINTS["NotSetUp"]


def test_a_kind_of_a_known_failure_gets_the_same_next_step() -> None:
    # A timed-out program is a subclass of SubprocessError; the hint is found through the class chain.
    answer = error_answer(5, subprocess.TimeoutExpired(["gh"], 30))
    assert answer["hint"] == ERROR_HINTS["TimeoutExpired"]
