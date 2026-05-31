import importlib.util
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).parents[4]))
sys.path.insert(0, str(Path(__file__).parents[1]))

from harness.story_scorer import score_story, _arousal_score


def _load_module(module_path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def story_scorer():
    """Load the story_scorer module by file path."""
    module_path = Path(__file__).parent.parent / "harness" / "story_scorer.py"
    return _load_module(str(module_path), "story_scorer")


def _make_story(**kwargs):
    base = {
        "id": "x1", "title": "The darkness came", "text": "word " * 100,
        "author": "author1", "subreddit": "nosleep", "score": 1000,
        "num_comments": 100, "permalink": "/r/nosleep/x1",
        "url": "https://reddit.com/r/nosleep/x1", "word_count": 100,
    }
    base.update(kwargs)
    return base


def _story(title, score=500, word_count=80):
    return {"id": "x1", "title": title, "score": score, "word_count": word_count}


def test_score_story_returns_float_between_0_and_10(story_scorer):
    story = _make_story(word_count=80, title="What was hiding behind my door", score=2000)
    result = story_scorer.score_story(story, target="short", used_ids=set())
    assert 0.0 <= result <= 10.0


def test_short_target_prefers_short_word_count(story_scorer):
    short_story = _make_story(word_count=80)
    long_story = _make_story(word_count=1200)
    assert story_scorer.score_story(short_story, target="short", used_ids=set()) > story_scorer.score_story(long_story, target="short", used_ids=set())


def test_long_target_prefers_long_word_count(story_scorer):
    short_story = _make_story(word_count=80)
    long_story = _make_story(word_count=1000)
    assert story_scorer.score_story(long_story, target="long", used_ids=set()) > story_scorer.score_story(short_story, target="long", used_ids=set())


def test_already_used_story_scores_zero(story_scorer):
    story = _make_story(word_count=80)
    assert story_scorer.score_story(story, target="short", used_ids={"x1"}) == 0.0


def test_pick_best_story_returns_highest_scoring(story_scorer):
    stories = [
        _make_story(id="a", word_count=80, score=500, title="meh"),
        _make_story(id="b", word_count=75, score=5000, title="What was in the basement"),
        _make_story(id="c", word_count=90, score=300, title="ok"),
    ]
    best = story_scorer.pick_best_story(stories, target="short", used_ids=set())
    assert best["id"] == "b"


def test_pick_best_story_returns_none_when_all_used(story_scorer):
    stories = [_make_story(id="a"), _make_story(id="b")]
    assert story_scorer.pick_best_story(stories, target="short", used_ids={"a", "b"}) is None


def test_hook_words_in_title_boost_score(story_scorer):
    plain = _make_story(title="A dog story", score=1000)
    hooked = _make_story(title="What was watching from the dark", score=1000)
    assert story_scorer.score_story(hooked, target="short", used_ids=set()) > story_scorer.score_story(plain, target="short", used_ids=set())


def test_arousal_score_high_for_action_titles():
    """Titles with immediate threat/action words should score > 0.5"""
    s = _story("I followed the sound and found it still breathing")
    assert _arousal_score(s["title"]) > 0.5


def test_arousal_score_low_for_passive_titles():
    """Titles with passive, atmospheric language should score < 0.3"""
    s = _story("The old house had a strange feeling")
    assert _arousal_score(s["title"]) < 0.3


def test_arousal_contributes_to_total_score():
    """A high-arousal story should outscore an otherwise identical low-arousal story"""
    high = _story("I ran but it was already inside", score=500, word_count=80)
    low  = _story("The atmosphere seemed unsettling", score=500, word_count=80)
    assert score_story(high, "short", set()) > score_story(low, "short", set())


def test_used_id_still_zero():
    """Used stories score 0 regardless of arousal"""
    s = _story("I ran but it was already inside")
    assert score_story(s, "short", {"x1"}) == 0.0
