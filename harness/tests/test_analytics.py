import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.agents.analytics import (
    track_video,
    pull_daily_snapshots,
    rebuild_learnings_from_week,
    _get_video_ids_to_track,
)


@pytest.fixture(autouse=True)
def patch_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.agents.analytics.DATA_DIR", tmp_path)
    (tmp_path / "performance").mkdir()
    index = {
        "updated_at": None,
        "total_videos_tracked": 0,
        "channel_stats": {"subscriber_count": None, "total_views_all_time": None},
        "kpis_7d": {"avg_views_per_video": None, "avg_ctr": None,
                    "avg_watch_time_min": None, "subscribers_gained": None},
        "videos": [],
    }
    (tmp_path / "performance" / "index.json").write_text(json.dumps(index))
    yield tmp_path


# ── track_video ────────────────────────────────────────────────────────────────

def test_track_video_creates_performance_file(patch_data_dir):
    track_video("vid001", {
        "title": "Dogs Detect Cancer",
        "format": "short",
        "topic": "dogs detecting cancer",
        "topic_cluster": "dog health",
        "hook_pattern_used": "Did you know dogs can [fact]?",
        "title_formula_used": "[Claim] Before [Authority]",
        "eval_scores": {"hook_eval": 8.5},
    })
    perf_file = patch_data_dir / "performance" / "vid001.json"
    assert perf_file.exists()
    data = json.loads(perf_file.read_text())
    assert data["video_id"] == "vid001"
    assert data["format"] == "short"
    assert data["snapshots"] == []


def test_track_video_registers_in_index(patch_data_dir):
    track_video("vid001", {"title": "T", "format": "short", "topic": "t",
                            "topic_cluster": "tc", "hook_pattern_used": "hp",
                            "title_formula_used": "tf", "eval_scores": {}})
    index = json.loads((patch_data_dir / "performance" / "index.json").read_text())
    assert any(v["video_id"] == "vid001" for v in index["videos"])


def test_track_video_idempotent(patch_data_dir):
    """Calling track_video twice for the same video_id should not duplicate index entry."""
    meta = {"title": "T", "format": "short", "topic": "t", "topic_cluster": "tc",
            "hook_pattern_used": "hp", "title_formula_used": "tf", "eval_scores": {}}
    track_video("vid001", meta)
    track_video("vid001", meta)
    index = json.loads((patch_data_dir / "performance" / "index.json").read_text())
    assert sum(1 for v in index["videos"] if v["video_id"] == "vid001") == 1


# ── _get_video_ids_to_track ────────────────────────────────────────────────────

def test_get_video_ids_to_track_returns_registered_ids(patch_data_dir):
    track_video("vid001", {"title": "T", "format": "short", "topic": "t",
                            "topic_cluster": "tc", "hook_pattern_used": "hp",
                            "title_formula_used": "tf", "eval_scores": {}})
    ids = _get_video_ids_to_track()
    assert "vid001" in ids


# ── pull_daily_snapshots ───────────────────────────────────────────────────────

def test_pull_daily_snapshots_appends_snapshot(patch_data_dir):
    track_video("vid001", {"title": "T", "format": "short", "topic": "t",
                            "topic_cluster": "tc", "hook_pattern_used": "hp",
                            "title_formula_used": "tf", "eval_scores": {}})

    mock_analytics = MagicMock()
    mock_analytics.reports().query().execute.return_value = {
        "rows": [[1240, 620, 30, 4, 88, 12, 20000, 0.062]],
        "columnHeaders": [
            {"name": "views"}, {"name": "watchTimeMinutes"}, {"name": "averageViewDuration"},
            {"name": "subscribersGained"}, {"name": "likes"}, {"name": "comments"},
            {"name": "impressions"}, {"name": "impressionClickThroughRate"},
        ],
    }

    with patch("harness.agents.analytics.get_analytics_service", return_value=mock_analytics):
        pull_daily_snapshots()

    perf = json.loads((patch_data_dir / "performance" / "vid001.json").read_text())
    assert len(perf["snapshots"]) == 1
    assert perf["snapshots"][0]["views"] == 1240
    assert abs(perf["snapshots"][0]["ctr"] - 0.062) < 0.001


def test_pull_daily_snapshots_does_not_duplicate_same_day(patch_data_dir):
    track_video("vid001", {"title": "T", "format": "short", "topic": "t",
                            "topic_cluster": "tc", "hook_pattern_used": "hp",
                            "title_formula_used": "tf", "eval_scores": {}})

    mock_analytics = MagicMock()
    mock_analytics.reports().query().execute.return_value = {
        "rows": [[100, 50, 30, 1, 5, 1, 1000, 0.04]],
        "columnHeaders": [
            {"name": "views"}, {"name": "watchTimeMinutes"}, {"name": "averageViewDuration"},
            {"name": "subscribersGained"}, {"name": "likes"}, {"name": "comments"},
            {"name": "impressions"}, {"name": "impressionClickThroughRate"},
        ],
    }

    with patch("harness.agents.analytics.get_analytics_service", return_value=mock_analytics):
        pull_daily_snapshots()
        pull_daily_snapshots()  # second call same day

    perf = json.loads((patch_data_dir / "performance" / "vid001.json").read_text())
    assert len(perf["snapshots"]) == 1  # not duplicated


# ── rebuild_learnings_from_week ────────────────────────────────────────────────

def test_rebuild_learnings_from_week_calls_rebuild(patch_data_dir):
    today = datetime.now().strftime("%Y-%m-%d")
    for vid_id, ctr in [("vid001", 0.08), ("vid002", 0.06)]:
        track_video(vid_id, {"title": "T", "format": "short", "topic": f"topic {vid_id}",
                              "topic_cluster": "dog health", "hook_pattern_used": "Did you know [fact]?",
                              "title_formula_used": "[Claim] Before [Authority]", "eval_scores": {}})
        perf = json.loads((patch_data_dir / "performance" / f"{vid_id}.json").read_text())
        perf["uploaded_at"] = (datetime.now() - timedelta(days=1)).isoformat()
        perf["snapshots"] = [{"date": today, "views": 1000, "watch_time_minutes": 500,
                               "avg_view_duration_sec": 30, "ctr": ctr, "likes": 80,
                               "comments": 10, "subscribers_gained": 3, "impressions": 15000}]
        (patch_data_dir / "performance" / f"{vid_id}.json").write_text(json.dumps(perf))

    with patch("harness.agents.analytics.rebuild_from_week") as mock_rebuild:
        rebuild_learnings_from_week()
        mock_rebuild.assert_called_once()
        call_args = mock_rebuild.call_args[0][0]
        assert len(call_args) == 2
