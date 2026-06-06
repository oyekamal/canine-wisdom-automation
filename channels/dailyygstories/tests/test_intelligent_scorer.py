import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3]))

from channels.dailyygstories.harness.intelligent_scorer import score_candidate, pick_best_candidate


def _make_candidate(cid, title, word_count, score, story_type_hint="paranormal"):
    return {
        "id": cid,
        "title": title,
        "text": "x " * word_count,
        "score": score,
        "source": "reddit",
        "word_count": word_count,
    }


def test_used_story_scores_zero():
    c = _make_candidate("used1", "A scary night", 80, 500)
    result = score_candidate(c, target="short", used_ids={"used1"}, top_story_types=[])
    assert result == 0.0


def test_short_target_prefers_short_word_count():
    short = _make_candidate("s1", "Shadow followed me", 80, 200)
    long = _make_candidate("l1", "The basement door", 1200, 200)
    score_short = score_candidate(short, target="short", used_ids=set(), top_story_types=[])
    score_long = score_candidate(long, target="short", used_ids=set(), top_story_types=[])
    assert score_short > score_long


def test_long_target_prefers_long_word_count():
    short = _make_candidate("s2", "Two words", 80, 200)
    long = _make_candidate("l2", "Long investigation story", 1200, 200)
    score_short = score_candidate(short, target="long", used_ids=set(), top_story_types=[])
    score_long = score_candidate(long, target="long", used_ids=set(), top_story_types=[])
    assert score_long > score_short


def test_pick_best_candidate_returns_highest_score():
    candidates = [
        _make_candidate("a", "Low score", 80, 10),
        _make_candidate("b", "High score shadow followed me escaped ran", 80, 5000),
        _make_candidate("c", "Mid score disappeared", 80, 100),
    ]
    best = pick_best_candidate(candidates, target="short", used_ids=set(), top_story_types=[])
    assert best["id"] == "b"


def test_pick_best_candidate_returns_none_when_all_used():
    candidates = [_make_candidate("x", "test", 80, 100)]
    result = pick_best_candidate(candidates, target="short", used_ids={"x"}, top_story_types=[])
    assert result is None
