import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from harness.agents.trend import (
    _youtube_autocomplete,
    _get_competitor_topics,
    _assign_cluster,
    _suggestion_to_topic,
    build_topic_queue,
    pick_best_topic,
    mark_topic_used,
)


@pytest.fixture(autouse=True)
def patch_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.agents.trend.TOPICS_DIR", tmp_path / "topics")
    monkeypatch.setattr("harness.agents.trend.COMPETITORS_DIR", tmp_path / "competitors")
    (tmp_path / "topics").mkdir()
    (tmp_path / "competitors").mkdir()
    yield tmp_path


# ── _youtube_autocomplete ──────────────────────────────────────────────────────

def test_autocomplete_returns_suggestions():
    fake_response = b'["dog facts",["dog facts daily","dog facts for kids","dog facts 2024",[],[]]]'
    mock_resp = MagicMock()
    mock_resp.read.return_value = fake_response
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        results = _youtube_autocomplete("dog facts")
    assert len(results) > 0
    assert any("dog" in r.lower() for r in results)


def test_autocomplete_handles_network_error():
    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        results = _youtube_autocomplete("dog facts")
    assert results == []


# ── _get_competitor_topics ─────────────────────────────────────────────────────

def test_get_competitor_topics_counts_from_video_files(patch_dirs):
    ch_dir = patch_dirs / "competitors" / "UCtest" / "videos"
    ch_dir.mkdir(parents=True)
    (ch_dir / "vid1.json").write_text(json.dumps({
        "title": "Why Dogs Can Detect Cancer — Amazing Dog Health Facts",
        "view_count": 50000,
    }))
    counts = _get_competitor_topics()
    assert counts.get("dog health", 0) > 0


def test_get_competitor_topics_empty_when_no_competitors(patch_dirs):
    counts = _get_competitor_topics()
    assert sum(counts.values()) == 0


# ── _assign_cluster ────────────────────────────────────────────────────────────

def test_assign_cluster_dog_health():
    # "dog detect" keyword maps to dog health; "dogs can" maps to dog science first
    assert _assign_cluster("dog detect cancer in humans") == "dog health"


def test_assign_cluster_dog_behavior():
    assert _assign_cluster("why do dogs lick their paws") == "dog behavior"


def test_assign_cluster_defaults_to_fun():
    assert _assign_cluster("something completely unrelated") == "dog fun"


# ── _suggestion_to_topic ───────────────────────────────────────────────────────

def test_suggestion_strips_dog_facts_boilerplate():
    result = _suggestion_to_topic("dog facts about nose prints")
    assert "dog facts" not in result.lower()


# ── build_topic_queue ──────────────────────────────────────────────────────────

def test_build_topic_queue_creates_file(patch_dirs):
    fake_suggestions = ["dogs can detect cancer", "why do dogs tilt head", "dog nose facts"]
    with patch("harness.agents.trend._youtube_autocomplete", return_value=fake_suggestions):
        with patch("harness.agents.trend._get_covered_topics", return_value=set()):
            queue = build_topic_queue(date="2026-05-17")
    out = patch_dirs / "topics" / "2026-05-17.json"
    assert out.exists()
    assert len(queue["topics"]) > 0


def test_build_topic_queue_cached_on_second_call(patch_dirs):
    fake_suggestions = ["dogs can detect cancer"]
    with patch("harness.agents.trend._youtube_autocomplete", return_value=fake_suggestions) as mock_ac:
        with patch("harness.agents.trend._get_covered_topics", return_value=set()):
            build_topic_queue(date="2026-05-17")
            first_call_count = mock_ac.call_count
            build_topic_queue(date="2026-05-17")  # second call — should not re-fetch
            second_call_count = mock_ac.call_count
    # First build calls autocomplete once per seed term; second call is cached (no new calls)
    assert first_call_count > 0
    assert second_call_count == first_call_count  # no additional calls on cache hit


def test_build_topic_queue_uses_fallback_when_no_suggestions(patch_dirs):
    with patch("harness.agents.trend._youtube_autocomplete", return_value=[]):
        with patch("harness.agents.trend._get_covered_topics", return_value=set()):
            queue = build_topic_queue(date="2026-05-18")
    assert len(queue["topics"]) > 0
    assert queue["topics"][0]["source"] == "fallback"


def test_build_topic_queue_skips_covered_topics(patch_dirs):
    with patch("harness.agents.trend._youtube_autocomplete",
               return_value=["dogs can detect cancer"]):
        with patch("harness.agents.trend._get_covered_topics",
                   return_value={"dogs can detect cancer"}):
            queue = build_topic_queue(date="2026-05-19")
    # The covered topic should not appear in the queue
    topics = [t["topic"] for t in queue["topics"]]
    assert not any("detect cancer" in t for t in topics)


# ── pick_best_topic + mark_topic_used ─────────────────────────────────────────

def test_pick_best_topic_returns_first_unused():
    queue = {
        "topics": [
            {"rank": 1, "topic": "cancer detection", "raw_suggestion": "dogs detect cancer",
             "topic_cluster": "dog health", "score": 90, "used": True},
            {"rank": 2, "topic": "head tilt", "raw_suggestion": "why dogs tilt head",
             "topic_cluster": "dog behavior", "score": 80, "used": False},
        ]
    }
    result = pick_best_topic(queue)
    assert result["topic"] == "head tilt"


def test_pick_best_topic_returns_none_when_all_used():
    queue = {"topics": [{"rank": 1, "topic": "t", "raw_suggestion": "t",
                          "topic_cluster": "dog fun", "score": 10, "used": True}]}
    assert pick_best_topic(queue) is None


def test_mark_topic_used_updates_file(patch_dirs):
    date = "2026-05-20"
    queue_file = patch_dirs / "topics" / f"{date}.json"
    queue_file.write_text(json.dumps({
        "date": date, "generated_at": "2026-05-20T09:00:00", "used": None,
        "topics": [{"rank": 1, "topic": "cancer", "raw_suggestion": "dogs detect cancer",
                    "topic_cluster": "dog health", "score": 90, "used": False}]
    }))
    topic = {"topic": "cancer", "raw_suggestion": "dogs detect cancer"}
    mark_topic_used(date, topic)
    updated = json.loads(queue_file.read_text())
    assert updated["topics"][0]["used"] is True
    assert updated["used"] == "cancer"
