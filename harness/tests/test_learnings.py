import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from harness.tools.learnings import (
    read_learnings,
    get_top_hook_patterns,
    get_top_title_formulas,
    get_covered_topics,
    add_covered_topic,
    update_from_competitor,
    update_from_analytics,
    rebuild_from_week,
    bootstrap_from_competitors,
    _invalidate_cache,
)


EMPTY_LEARNINGS = {
    "updated_at": None,
    "schema_version": 1,
    "hook_patterns": [],
    "title_formulas": [],
    "thumbnail_features": [],
    "posting_times": {
        "shorts": {"best_hour_utc": 14, "best_dow": "Tue", "confidence": "low", "sample_size": 0},
        "long_form": {"best_hour_utc": 17, "best_dow": "Sat", "confidence": "low", "sample_size": 0},
    },
    "topic_performance": [],
    "pacing_rules": {
        "shorts": {"hook_max_sec": 3, "words_per_min": 140},
        "long_form": {"b_roll_cut_every_sec": 7, "chapter_count_target": 6},
    },
    "anti_patterns": [],
    "format_mix": {
        "shorts_per_week": 7,
        "long_form_per_week": 0,
        "rationale": "insufficient data",
        "next_review": None,
    },
    "covered_topics": [],
}


@pytest.fixture(autouse=True)
def patch_learnings_path(tmp_path, monkeypatch):
    """Redirect LEARNINGS_PATH to a tmp file and clear cache before each test."""
    learnings_file = tmp_path / "learnings.json"
    learnings_file.write_text(json.dumps(EMPTY_LEARNINGS, indent=2))
    monkeypatch.setattr("harness.tools.learnings.LEARNINGS_PATH", learnings_file)
    _invalidate_cache()
    yield learnings_file


# ── read_learnings ─────────────────────────────────────────────────────────────

def test_read_learnings_returns_dict(patch_learnings_path):
    data = read_learnings()
    assert isinstance(data, dict)
    assert data["schema_version"] == 1


def test_read_learnings_is_cached(patch_learnings_path):
    d1 = read_learnings()
    d2 = read_learnings()
    assert d1 is d2  # same object = cache hit


def test_read_learnings_cache_invalidated_after_1h(patch_learnings_path, monkeypatch):
    d1 = read_learnings()
    # Move cache timestamp back 2 hours
    import harness.tools.learnings as lm
    lm._cache_time = datetime.now() - timedelta(hours=2)
    d2 = read_learnings()
    assert d1 is not d2  # different object = cache miss


# ── get_top_hook_patterns ──────────────────────────────────────────────────────

def test_get_top_hook_patterns_empty(patch_learnings_path):
    assert get_top_hook_patterns() == []


def test_get_top_hook_patterns_sorted_by_retention(patch_learnings_path):
    import harness.tools.learnings as lm
    lm._cache = {
        **EMPTY_LEARNINGS,
        "hook_patterns": [
            {"pattern": "A", "avg_3sec_retention_proxy": 0.5, "confidence": "medium", "sample_size": 6, "source": "competitor", "last_seen": "2026-05-17"},
            {"pattern": "B", "avg_3sec_retention_proxy": 0.8, "confidence": "high", "sample_size": 20, "source": "competitor", "last_seen": "2026-05-17"},
            {"pattern": "C", "avg_3sec_retention_proxy": 0.6, "confidence": "low", "sample_size": 3, "source": "competitor", "last_seen": "2026-05-17"},
        ],
    }
    lm._cache_time = datetime.now()
    result = get_top_hook_patterns(min_confidence="low", n=3)
    assert result[0]["pattern"] == "B"
    assert result[1]["pattern"] == "C"
    assert result[2]["pattern"] == "A"


def test_get_top_hook_patterns_filters_by_confidence(patch_learnings_path):
    import harness.tools.learnings as lm
    lm._cache = {
        **EMPTY_LEARNINGS,
        "hook_patterns": [
            {"pattern": "A", "avg_3sec_retention_proxy": 0.9, "confidence": "low", "sample_size": 2, "source": "competitor", "last_seen": "2026-05-17"},
            {"pattern": "B", "avg_3sec_retention_proxy": 0.7, "confidence": "medium", "sample_size": 8, "source": "competitor", "last_seen": "2026-05-17"},
        ],
    }
    lm._cache_time = datetime.now()
    result = get_top_hook_patterns(min_confidence="medium", n=3)
    assert len(result) == 1
    assert result[0]["pattern"] == "B"


# ── get_top_title_formulas ─────────────────────────────────────────────────────

def test_get_top_title_formulas_sorted_by_ctr(patch_learnings_path):
    import harness.tools.learnings as lm
    lm._cache = {
        **EMPTY_LEARNINGS,
        "title_formulas": [
            {"formula": "A", "avg_ctr": 0.04, "confidence": "medium", "sample_size": 5, "source": "competitor"},
            {"formula": "B", "avg_ctr": 0.09, "confidence": "high", "sample_size": 20, "source": "own_analytics"},
        ],
    }
    lm._cache_time = datetime.now()
    result = get_top_title_formulas(n=2)
    assert result[0]["formula"] == "B"


# ── get_covered_topics ─────────────────────────────────────────────────────────

def test_get_covered_topics_returns_recent_only(patch_learnings_path):
    import harness.tools.learnings as lm
    old_date = (datetime.now() - timedelta(days=35)).strftime("%Y-%m-%d")
    recent_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
    lm._cache = {
        **EMPTY_LEARNINGS,
        "covered_topics": [
            {"topic": "old topic", "posted": old_date, "video_id": "old"},
            {"topic": "recent topic", "posted": recent_date, "video_id": "new"},
        ],
    }
    lm._cache_time = datetime.now()
    topics = get_covered_topics(days=30)
    assert "recent topic" in topics
    assert "old topic" not in topics


# ── add_covered_topic ──────────────────────────────────────────────────────────

def test_add_covered_topic_persists_to_disk(patch_learnings_path):
    add_covered_topic("dogs detect cancer", "vid123")
    data = json.loads(patch_learnings_path.read_text())
    topics = [t["topic"] for t in data["covered_topics"]]
    assert "dogs detect cancer" in topics


# ── update_from_competitor ─────────────────────────────────────────────────────

def test_update_from_competitor_adds_hook_patterns(patch_learnings_path):
    videos = [
        {
            "hook": "Did you know dogs can detect cancer?",
            "like_rate": 0.08,
            "views_per_sub": 0.6,
            "comment_rate": 0.005,
            "title": "Dogs Detect Cancer Before Doctors",
            "publish_hour_utc": 14,
            "publish_dow": "Tue",
        }
    ] * 6  # 6 samples → medium confidence
    update_from_competitor("UCtest", videos)
    data = json.loads(patch_learnings_path.read_text())
    assert len(data["hook_patterns"]) > 0
    assert data["hook_patterns"][0]["source"] == "competitor"
    assert data["hook_patterns"][0]["sample_size"] == 6


def test_update_from_competitor_does_not_overwrite_own_analytics(patch_learnings_path):
    """own_analytics source should never be overwritten by competitor data."""
    import harness.tools.learnings as lm
    existing = {
        **EMPTY_LEARNINGS,
        "hook_patterns": [
            {
                "pattern": "Did you know dogs can [fact]?",
                "avg_3sec_retention_proxy": 0.85,
                "sample_size": 10,
                "confidence": "medium",
                "source": "own_analytics",
                "last_seen": "2026-05-17",
            }
        ],
    }
    patch_learnings_path.write_text(json.dumps(existing))
    _invalidate_cache()

    videos = [{"hook": "Did you know dogs can detect cancer?", "like_rate": 0.03,
               "views_per_sub": 0.1, "comment_rate": 0.001,
               "title": "Dogs", "publish_hour_utc": 9, "publish_dow": "Mon"}] * 6
    update_from_competitor("UCtest", videos)

    data = json.loads(patch_learnings_path.read_text())
    own = [p for p in data["hook_patterns"] if p["source"] == "own_analytics"]
    assert len(own) == 1
    assert own[0]["avg_3sec_retention_proxy"] == 0.85  # unchanged


# ── update_from_analytics ──────────────────────────────────────────────────────

def test_update_from_analytics_updates_hook_pattern(patch_learnings_path):
    import harness.tools.learnings as lm
    lm._cache = {
        **EMPTY_LEARNINGS,
        "hook_patterns": [
            {
                "pattern": "Did you know dogs can [fact]?",
                "avg_3sec_retention_proxy": 0.5,
                "sample_size": 4,
                "confidence": "low",
                "source": "competitor",
                "last_seen": "2026-05-10",
            }
        ],
    }
    lm._cache_time = datetime.now()
    patch_learnings_path.write_text(json.dumps(lm._cache))

    video_data = {
        "hook_pattern_used": "Did you know dogs can [fact]?",
        "title_formula_used": "[Claim] Before [Authority]",
        "avg_ctr_latest": 0.08,
        "avg_view_duration_sec_latest": 38,
        "topic": "dogs detecting cancer",
        "topic_cluster": "dog health",
        "avg_views_latest": 4200,
    }
    update_from_analytics("vid123", video_data)

    data = json.loads(patch_learnings_path.read_text())
    hook = data["hook_patterns"][0]
    assert hook["sample_size"] == 5
    assert hook["source"] == "own_analytics"
    assert hook["confidence"] == "medium"  # sample_size 5 → medium (threshold: 5-19)


# ── rebuild_from_week ──────────────────────────────────────────────────────────

def test_rebuild_from_week_promotes_confidence(patch_learnings_path):
    """After 20 own_analytics samples, confidence should be 'high'."""
    import harness.tools.learnings as lm
    lm._cache = {**EMPTY_LEARNINGS}
    lm._cache_time = datetime.now()
    patch_learnings_path.write_text(json.dumps(lm._cache))

    week_data = [
        {
            "hook_pattern_used": "Did you know dogs can [fact]?",
            "title_formula_used": "[Claim] Before [Authority]",
            "avg_ctr_latest": 0.07 + i * 0.001,
            "avg_view_duration_sec_latest": 35,
            "topic": f"topic {i}",
            "topic_cluster": "dog health",
            "avg_views_latest": 3000 + i * 100,
        }
        for i in range(20)
    ]
    rebuild_from_week(week_data)

    data = json.loads(patch_learnings_path.read_text())
    hook = data["hook_patterns"][0]
    assert hook["confidence"] == "high"
    assert hook["sample_size"] == 20
    assert hook["source"] == "own_analytics"


def test_rebuild_from_week_adds_anti_pattern_for_low_ctr(patch_learnings_path):
    """Title formula with CTR < 0.04 across 5+ samples → anti_pattern."""
    import harness.tools.learnings as lm
    lm._cache = {**EMPTY_LEARNINGS}
    lm._cache_time = datetime.now()
    patch_learnings_path.write_text(json.dumps(lm._cache))

    week_data = [
        {
            "hook_pattern_used": "Did you know dogs can [fact]?",
            "title_formula_used": "How to [train] your dog",
            "avg_ctr_latest": 0.02,
            "avg_view_duration_sec_latest": 20,
            "topic": f"topic {i}",
            "topic_cluster": "training",
            "avg_views_latest": 800,
        }
        for i in range(5)
    ]
    rebuild_from_week(week_data)

    data = json.loads(patch_learnings_path.read_text())
    anti = [a for a in data["anti_patterns"] if "How to" in a["pattern"]]
    assert len(anti) == 1


# ── bootstrap_from_competitors ─────────────────────────────────────────────────

def test_bootstrap_populates_empty_learnings(patch_learnings_path):
    competitor_videos = [
        {
            "hook": "Your dog is doing THIS for a reason",
            "like_rate": 0.07,
            "views_per_sub": 0.55,
            "comment_rate": 0.004,
            "title": "Your Dog Is Doing THIS for a Reason",
            "publish_hour_utc": 14,
            "publish_dow": "Tue",
        }
    ] * 8
    bootstrap_from_competitors(competitor_videos)
    data = json.loads(patch_learnings_path.read_text())
    assert len(data["hook_patterns"]) > 0
    assert data["updated_at"] is not None


def test_bootstrap_skips_if_learnings_already_has_own_analytics(patch_learnings_path):
    """Bootstrap must not overwrite existing own_analytics entries."""
    import harness.tools.learnings as lm
    existing = {
        **EMPTY_LEARNINGS,
        "hook_patterns": [
            {"pattern": "existing", "avg_3sec_retention_proxy": 0.9, "sample_size": 10,
             "confidence": "medium", "source": "own_analytics", "last_seen": "2026-05-17"}
        ],
    }
    patch_learnings_path.write_text(json.dumps(existing))
    _invalidate_cache()

    bootstrap_from_competitors([{"hook": "new hook", "like_rate": 0.05,
                                  "views_per_sub": 0.4, "comment_rate": 0.003,
                                  "title": "New", "publish_hour_utc": 9, "publish_dow": "Mon"}] * 8)

    data = json.loads(patch_learnings_path.read_text())
    own = [p for p in data["hook_patterns"] if p["source"] == "own_analytics"]
    assert len(own) == 1  # original untouched
    assert own[0]["pattern"] == "existing"
