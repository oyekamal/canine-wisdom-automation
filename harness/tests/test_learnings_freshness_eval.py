import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from harness.evals.learnings_freshness_eval import learnings_freshness_eval


def _make_learnings(hook_patterns=None, title_formulas=None):
    return {
        "updated_at": datetime.now().isoformat(),
        "schema_version": 1,
        "hook_patterns": hook_patterns or [],
        "title_formulas": title_formulas or [],
        "thumbnail_features": [],
        "posting_times": {
            "shorts": {"best_hour_utc": 14, "best_dow": "Tue", "confidence": "low", "sample_size": 0},
            "long_form": {"best_hour_utc": 17, "best_dow": "Sat", "confidence": "low", "sample_size": 0},
        },
        "topic_performance": [],
        "pacing_rules": {},
        "anti_patterns": [],
        "format_mix": {},
        "covered_topics": [],
    }


def test_freshness_eval_passes_with_enough_medium_patterns():
    recent = datetime.now().strftime("%Y-%m-%d")
    learnings = _make_learnings(
        hook_patterns=[
            {"pattern": f"hook {i}", "avg_3sec_retention_proxy": 0.7, "sample_size": 8,
             "confidence": "medium", "source": "competitor", "last_seen": recent}
            for i in range(3)
        ]
    )
    with patch("harness.evals.learnings_freshness_eval.read_learnings", return_value=learnings):
        with patch("harness.evals.learnings_freshness_eval._write_learnings"):
            result = learnings_freshness_eval()
    assert result.passed is True


def test_freshness_eval_fails_with_no_patterns():
    learnings = _make_learnings()
    with patch("harness.evals.learnings_freshness_eval.read_learnings", return_value=learnings):
        with patch("harness.evals.learnings_freshness_eval._write_learnings"):
            result = learnings_freshness_eval()
    assert result.passed is False
    assert result.score == 0.0


def test_freshness_eval_demotes_stale_entries():
    """Entries with last_seen > 14 days should have confidence downgraded."""
    stale_date = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d")
    learnings = _make_learnings(
        hook_patterns=[
            {"pattern": "stale hook", "avg_3sec_retention_proxy": 0.7, "sample_size": 10,
             "confidence": "medium", "source": "competitor", "last_seen": stale_date}
        ]
    )
    written = {}
    def capture_write(data):
        written.update(data)

    with patch("harness.evals.learnings_freshness_eval.read_learnings", return_value=learnings):
        with patch("harness.evals.learnings_freshness_eval._write_learnings", side_effect=capture_write):
            learnings_freshness_eval()

    assert written.get("hook_patterns", [{}])[0]["confidence"] == "low"


def test_freshness_eval_removes_very_old_zero_sample_entries():
    """Entries with sample_size=0 and last_seen > 30 days should be removed."""
    very_old = (datetime.now() - timedelta(days=35)).strftime("%Y-%m-%d")
    learnings = _make_learnings(
        hook_patterns=[
            {"pattern": "dead hook", "avg_3sec_retention_proxy": 0.0, "sample_size": 0,
             "confidence": "low", "source": "competitor", "last_seen": very_old}
        ]
    )
    written = {}
    def capture_write(data):
        written.update(data)

    with patch("harness.evals.learnings_freshness_eval.read_learnings", return_value=learnings):
        with patch("harness.evals.learnings_freshness_eval._write_learnings", side_effect=capture_write):
            learnings_freshness_eval()

    assert written.get("hook_patterns", []) == []
