import pytest
from generate_audio import _chars_to_words


def test_basic_word_split():
    chars = list("hello world")
    starts = [i * 0.1 for i in range(len(chars))]
    ends = [s + 0.1 for s in starts]
    result = _chars_to_words(chars, starts, ends)
    assert len(result) == 2
    assert result[0]["word"] == "hello"
    assert result[1]["word"] == "world"
    assert result[0]["start"] == pytest.approx(0.0)
    assert result[1]["start"] == pytest.approx(0.6)


def test_empty_input():
    assert _chars_to_words([], [], []) == []
