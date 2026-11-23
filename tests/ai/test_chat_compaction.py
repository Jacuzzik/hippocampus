"""Context compaction: a long chat keeps its newest turns and folds the older ones into a digest."""

from ai import chat_history


def _turns(n: int, size: int = 10) -> list[dict[str, str]]:
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i} " + "x" * size}
        for i in range(n)
    ]


def test_a_short_chat_goes_to_the_model_as_it_is() -> None:
    turns = _turns(6)
    assert chat_history.compact(turns) == turns


def test_a_long_chat_keeps_the_newest_turns_and_a_digest_of_the_rest() -> None:
    turns = _turns(60)
    out = chat_history.compact(turns)
    assert len(out) <= chat_history.TURNS
    assert out[0]["role"] == "user"
    assert out[0]["content"].startswith("Earlier in this chat (shortened by the app")
    assert "- You asked: turn 0 " in out[0]["content"]
    assert out[-1] == turns[-1]


def test_a_few_huge_turns_are_cut_by_size_not_count() -> None:
    turns = _turns(8, size=25_000)
    out = chat_history.compact(turns)
    assert sum(len(t["content"]) for t in out[1:]) <= chat_history.CHARS
    assert len(out) < 8 and out[-1] == turns[-1]
    assert len(out[0]["content"].split("\n")[1]) < 200  # a digest line is short


def test_the_kept_turns_always_start_with_a_request() -> None:
    turns = _turns(61)[1:]  # starts with an answer
    out = chat_history.compact(turns)
    assert out[0]["role"] == "user"
