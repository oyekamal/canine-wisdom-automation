import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.evals.base import EvalResult, save_eval_result
from harness.evals.hook_eval import hook_eval
from harness.evals.script_eval import script_eval
from harness.evals.title_eval import title_eval
from harness.evals.description_eval import description_eval
from harness.evals.thumbnail_eval import thumbnail_eval
from harness.evals.channel_eval import channel_eval


# ── fixtures ──────────────────────────────────────────────────────────────────

GOOD_HOOK = "Did you know dogs can detect cancer before doctors can? Here's the proof."
WEAK_HOOK = "Today we will talk about some interesting dog facts that you may or may not know."

GOOD_SCRIPT = (
    "Did you know dogs can detect cancer before doctors can? "
    "Studies show trained dogs identify tumors with 97% accuracy. "
    "One Golden Retriever named Bear saved 12 lives in a single year. "
    "Follow for daily dog facts!"
)
BAD_SCRIPT = "Dogs are good. They are loyal. They like to play. Follow for daily dog facts!"

GOOD_TITLE = "Dogs Detect Cancer Before Doctors 🐕"
BAD_TITLE = "dog facts video number 47"

GOOD_DESCRIPTION = (
    "🐕 Dogs can smell cancer with 97% accuracy! Watch to discover how. "
    "#dogs #dogfacts #shorts #cancerdetection #animalsareamazing "
    "Follow for daily dog wisdom!"
)
BAD_DESCRIPTION = "dog video"


def make_claude_response(score: float, reasoning: str = "test reasoning"):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock()]
    mock_msg.content[0].text = json.dumps({"score": score, "reasoning": reasoning})
    return mock_msg


# ── EvalResult ────────────────────────────────────────────────────────────────

def test_eval_result_passed_when_score_above_threshold():
    r = EvalResult(eval_name="hook_eval", score=8.0, threshold=7.0, reasoning="good")
    assert r.passed is True


def test_eval_result_failed_when_score_below_threshold():
    r = EvalResult(eval_name="hook_eval", score=5.0, threshold=7.0, reasoning="weak")
    assert r.passed is False


def test_eval_result_passed_at_exact_threshold():
    r = EvalResult(eval_name="hook_eval", score=7.0, threshold=7.0, reasoning="ok")
    assert r.passed is True


# ── hook_eval ─────────────────────────────────────────────────────────────────

def test_hook_eval_passes_strong_hook():
    with patch("harness.evals.hook_eval.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = make_claude_response(8.5)
        result = hook_eval(GOOD_HOOK)
    assert result.passed is True
    assert result.score == 8.5
    assert result.eval_name == "hook_eval"


def test_hook_eval_fails_weak_hook():
    with patch("harness.evals.hook_eval.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = make_claude_response(4.0)
        result = hook_eval(WEAK_HOOK)
    assert result.passed is False


# ── script_eval ───────────────────────────────────────────────────────────────

def test_script_eval_passes_good_script():
    with patch("harness.evals.script_eval.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = make_claude_response(8.0)
        result = script_eval(GOOD_SCRIPT, recent_topics=[])
    assert result.passed is True


def test_script_eval_fails_bad_script():
    with patch("harness.evals.script_eval.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = make_claude_response(3.0)
        result = script_eval(BAD_SCRIPT, recent_topics=[])
    assert result.passed is False


def test_script_eval_includes_recent_topics_in_prompt():
    captured_prompt = {}
    def fake_create(**kwargs):
        captured_prompt["content"] = kwargs["messages"][0]["content"]
        return make_claude_response(8.0)
    with patch("harness.evals.script_eval.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.side_effect = fake_create
        script_eval(GOOD_SCRIPT, recent_topics=["dogs sleep", "dog paws"])
    assert "dogs sleep" in captured_prompt["content"]


# ── title_eval ────────────────────────────────────────────────────────────────

def test_title_eval_passes_good_title():
    with patch("harness.evals.title_eval.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = make_claude_response(7.5)
        result = title_eval(GOOD_TITLE)
    assert result.passed is True


def test_title_eval_fails_bad_title():
    with patch("harness.evals.title_eval.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = make_claude_response(2.0)
        result = title_eval(BAD_TITLE)
    assert result.passed is False


# ── description_eval ──────────────────────────────────────────────────────────

def test_description_eval_passes_good_description():
    with patch("harness.evals.description_eval.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = make_claude_response(8.0)
        result = description_eval(GOOD_DESCRIPTION)
    assert result.passed is True


def test_description_eval_fails_bad_description():
    with patch("harness.evals.description_eval.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = make_claude_response(1.0)
        result = description_eval(BAD_DESCRIPTION)
    assert result.passed is False


# ── thumbnail_eval (placeholder) ──────────────────────────────────────────────

def test_thumbnail_eval_always_passes():
    result = thumbnail_eval(variants=[])
    assert result.passed is True
    assert result.score == 8.0


# ── channel_eval (placeholder) ────────────────────────────────────────────────

def test_channel_eval_always_passes():
    result = channel_eval(current_kpis={}, prior_kpis={})
    assert result.passed is True
