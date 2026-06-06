"""Tests for trend_horror.py — use offline mocks, never hit live APIs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3]))

import json
import pytest
from unittest.mock import patch, MagicMock


def test_merge_candidates_deduplicates_by_id():
    from channels.dailyygstories.harness.trend_horror import _merge_and_rank
    candidates = [
        {"id": "abc", "title": "A ghost story", "text": "...", "score": 100, "source": "reddit"},
        {"id": "abc", "title": "A ghost story", "text": "...", "score": 100, "source": "reddit"},
        {"id": "def", "title": "Real crime news", "text": "...", "score": 50, "source": "news"},
    ]
    merged = _merge_and_rank(candidates)
    assert len(merged) == 2


def test_merge_candidates_sorted_by_score_desc():
    from channels.dailyygstories.harness.trend_horror import _merge_and_rank
    candidates = [
        {"id": "a", "title": "Low", "text": "...", "score": 10, "source": "reddit"},
        {"id": "b", "title": "High", "text": "...", "score": 200, "source": "news"},
        {"id": "c", "title": "Mid", "text": "...", "score": 80, "source": "trends"},
    ]
    merged = _merge_and_rank(candidates)
    scores = [c["score"] for c in merged]
    assert scores == sorted(scores, reverse=True)


def test_score_news_item_returns_dict_with_required_keys():
    from channels.dailyygstories.harness.trend_horror import _score_news_item
    item = {
        "title": "Mysterious disappearance shocks small town",
        "summary": "A woman went missing after...",
        "link": "https://example.com/news/123",
        "published": "Mon, 06 Jun 2026 10:00:00 GMT",
    }
    result = _score_news_item(item)
    assert "id" in result
    assert "title" in result
    assert "text" in result
    assert "score" in result
    assert result["source"] == "news"


def test_harvest_trends_returns_list():
    """harvest_trends() must return a list (may be empty) without crashing."""
    from channels.dailyygstories.harness.trend_horror import harvest_trends
    with patch("channels.dailyygstories.harness.trend_horror.TrendReq") as mock_pytrends:
        mock_instance = MagicMock()
        mock_instance.trending_searches.return_value = MagicMock()
        mock_pytrends.return_value = mock_instance
        result = harvest_trends(keywords=["horror story"], geo="PK")
        assert isinstance(result, list)
