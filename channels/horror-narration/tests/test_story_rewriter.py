import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[4]))
sys.path.insert(0, str(Path(__file__).parents[1]))

from harness.story_rewriter import _build_rewrite_prompt, _detect_emotional_angle


def _story(title="Test", text="I found something in the basement.", subreddit="nosleep",
           author="anon", url="https://reddit.com/r/nosleep/x", word_count=80):
    return {"id": "t1", "title": title, "text": text,
            "subreddit": subreddit, "author": author, "url": url, "word_count": word_count}


def test_detect_emotional_angle_sensory():
    """Stories with sensory words trigger sensory-lead angle"""
    s = _story(text="I could hear it breathing. Then I smelled it — wrong, like copper.")
    angle = _detect_emotional_angle(s)
    assert angle == "sensory"


def test_detect_emotional_angle_action():
    """Stories with chase/run/escape words trigger action angle"""
    s = _story(text="I ran but it was already at the door. I couldn't get out.")
    angle = _detect_emotional_angle(s)
    assert angle == "action"


def test_detect_emotional_angle_default():
    """Stories with no strong signal fall back to delayed-answer"""
    s = _story(text="The house was old. Things happened there.")
    angle = _detect_emotional_angle(s)
    assert angle == "delayed-answer"


def test_rewrite_prompt_includes_emotional_guidance():
    """The rewrite prompt must include EMOTIONAL BEAT GUIDANCE section"""
    s = _story()
    prompt = _build_rewrite_prompt(s, "short")
    assert "EMOTIONAL BEAT GUIDANCE" in prompt


def test_rewrite_prompt_includes_arousal_ending_instruction():
    """The rewrite prompt must instruct Claude to end on high-arousal state"""
    s = _story()
    prompt = _build_rewrite_prompt(s, "short")
    assert "HIGH-AROUSAL" in prompt or "still happening" in prompt
