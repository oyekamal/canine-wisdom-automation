"""Tests for story_classifier.py — use offline mocks, never hit live Claude API."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3]))

import json
from unittest.mock import patch, MagicMock
from channels.dailyygstories.harness.story_classifier import classify_story, VALID_TYPES, VALID_FORMATS


def _mock_claude_response(story_type, fmt):
    """Helper: mock a Claude messages.create response with given story_type and format."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps({
        "story_type": story_type,
        "format": fmt,
        "reasoning": "test"
    }))]
    return mock_msg


def test_classify_returns_valid_type_and_format():
    """classify_story should return a dict with valid story_type and format."""
    candidate = {"title": "A ghost in the hospital", "text": "I was working the night shift..."}
    with patch("channels.dailyygstories.harness.story_classifier.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_claude_response("paranormal", "long")
        mock_cls.return_value = mock_client
        result = classify_story(candidate)
    assert result["story_type"] in VALID_TYPES
    assert result["format"] in VALID_FORMATS
    assert "reasoning" in result


def test_classify_returns_fallback_on_bad_json():
    """classify_story should return fallback dict when Claude returns invalid JSON."""
    candidate = {"title": "Scary thing", "text": "It was dark..."}
    with patch("channels.dailyygstories.harness.story_classifier.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(content=[MagicMock(text="not json")])
        mock_cls.return_value = mock_client
        result = classify_story(candidate)
    assert result["story_type"] in VALID_TYPES
    assert result["format"] in VALID_FORMATS
    assert result["story_type"] == "paranormal"  # default


def test_classify_returns_fallback_on_api_error():
    """classify_story should return fallback dict when Claude API raises."""
    candidate = {"title": "Scary thing", "text": "It was dark..."}
    with patch("channels.dailyygstories.harness.story_classifier.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")
        mock_cls.return_value = mock_client
        result = classify_story(candidate)
    assert result["story_type"] in VALID_TYPES
    assert result["format"] in VALID_FORMATS


def test_classify_format_based_on_word_count_fallback():
    """When falling back, format should be based on text word count."""
    short_text = "It was dark."
    long_text = " ".join(["word"] * 800)

    with patch("channels.dailyygstories.harness.story_classifier.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")
        mock_cls.return_value = mock_client

        result_short = classify_story({"title": "Short", "text": short_text})
        result_long = classify_story({"title": "Long", "text": long_text})

    assert result_short["format"] == "short"
    assert result_long["format"] == "long"


def test_classify_sanitizes_invalid_type_to_paranormal():
    """classify_story should sanitize an invalid story_type to paranormal."""
    candidate = {"title": "Scary thing", "text": "It was dark..."}
    with patch("channels.dailyygstories.harness.story_classifier.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_claude_response("invalid_type", "short")
        mock_cls.return_value = mock_client
        result = classify_story(candidate)
    assert result["story_type"] == "paranormal"
    assert result["format"] == "short"


def test_classify_sanitizes_invalid_format_to_short():
    """classify_story should sanitize an invalid format to short."""
    candidate = {"title": "Scary thing", "text": "It was dark..."}
    with patch("channels.dailyygstories.harness.story_classifier.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_claude_response("paranormal", "invalid_fmt")
        mock_cls.return_value = mock_client
        result = classify_story(candidate)
    assert result["story_type"] == "paranormal"
    assert result["format"] == "short"
