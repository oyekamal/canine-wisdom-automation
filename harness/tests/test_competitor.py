import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from harness.agents.competitor import (
    discover_channels,
    refresh_channel,
    should_refresh,
    extract_hook,
    compute_engagement,
    run_daily_refresh,
)


# ── extract_hook ───────────────────────────────────────────────────────────────

def test_extract_hook_returns_first_15_words():
    transcript = "Dogs can smell cancer before doctors can. Studies show trained dogs identify tumors with 97 percent accuracy. One Golden Retriever named Bear saved 12 lives."
    hook = extract_hook(transcript)
    words = hook.split()
    assert len(words) <= 15
    assert hook.startswith("Dogs can smell")


def test_extract_hook_empty_transcript():
    assert extract_hook("") == ""


# ── compute_engagement ─────────────────────────────────────────────────────────

def test_compute_engagement_ratios():
    result = compute_engagement(views=10000, likes=800, comments=50, subscriber_count=20000)
    assert abs(result["views_per_sub"] - 0.5) < 0.001
    assert abs(result["like_rate"] - 0.08) < 0.001
    assert abs(result["comment_rate"] - 0.005) < 0.001


def test_compute_engagement_zero_division_safe():
    result = compute_engagement(views=0, likes=0, comments=0, subscriber_count=0)
    assert result["views_per_sub"] == 0.0
    assert result["like_rate"] == 0.0
    assert result["comment_rate"] == 0.0


# ── should_refresh ─────────────────────────────────────────────────────────────

def test_should_refresh_true_when_no_channel_file(tmp_path):
    assert should_refresh(tmp_path / "channel.json", max_age_hours=24) is True


def test_should_refresh_false_when_recently_scanned(tmp_path):
    channel_file = tmp_path / "channel.json"
    channel_file.write_text(json.dumps({"last_scanned": datetime.now().isoformat()}))
    assert should_refresh(channel_file, max_age_hours=24) is False


def test_should_refresh_true_when_stale(tmp_path):
    channel_file = tmp_path / "channel.json"
    old_time = (datetime.now() - timedelta(hours=25)).isoformat()
    channel_file.write_text(json.dumps({"last_scanned": old_time}))
    assert should_refresh(channel_file, max_age_hours=24) is True


# ── discover_channels ──────────────────────────────────────────────────────────

def test_discover_channels_returns_top_5(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.agents.competitor.DATA_DIR", tmp_path)

    mock_youtube = MagicMock()
    mock_youtube.search().list().execute.return_value = {
        "items": [
            {"snippet": {"channelId": f"UC{i:06d}", "channelTitle": f"Channel {i}"}}
            for i in range(10)
        ]
    }

    def fake_channel_list(**kwargs):
        ids = kwargs["id"].split(",")
        mock_resp = MagicMock()
        mock_resp.execute.return_value = {
            "items": [
                {
                    "id": cid,
                    "snippet": {"title": f"Channel {cid}", "description": "dog facts daily shorts"},
                    "statistics": {"subscriberCount": "50000", "videoCount": "200", "viewCount": "5000000"},
                }
                for cid in ids
            ]
        }
        return mock_resp
    mock_youtube.channels().list.side_effect = fake_channel_list
    mock_youtube.search().list.return_value.execute.return_value = {
        "items": [{"snippet": {"channelId": f"UC{i:06d}", "channelTitle": f"Ch {i}"}} for i in range(10)]
    }

    with patch("harness.agents.competitor.Anthropic") as MockAnth:
        MockAnth.return_value.messages.create.return_value = MagicMock(
            content=[MagicMock(type="text", text='{"score": 0.85, "reasoning": "dog niche"}')]
        )
        channels = discover_channels(mock_youtube, seeds=["dog facts"])

    assert len(channels) <= 5
    for ch in channels:
        assert "channel_id" in ch
        assert "ranking_score" in ch


# ── refresh_channel ────────────────────────────────────────────────────────────

def test_refresh_channel_writes_video_json(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.agents.competitor.DATA_DIR", tmp_path)

    channel_dir = tmp_path / "competitors" / "UCtest"
    channel_dir.mkdir(parents=True)
    (channel_dir / "videos").mkdir()
    (channel_dir / "thumbnails").mkdir()
    (channel_dir / "transcripts").mkdir()
    (channel_dir / "channel.json").write_text(json.dumps({"channel_id": "UCtest", "subscriber_count": 100000}))

    mock_youtube = MagicMock()
    mock_youtube.search().list().execute.return_value = {
        "items": [{"id": {"videoId": "vid001"}}]
    }
    mock_youtube.videos().list().execute.return_value = {
        "items": [{
            "id": "vid001",
            "snippet": {
                "title": "Dogs Detect Cancer",
                "description": "Amazing dog fact",
                "tags": ["dogs"],
                "publishedAt": "2026-05-16T14:00:00Z",
            },
            "statistics": {"viewCount": "50000", "likeCount": "3000", "commentCount": "200"},
            "contentDetails": {"duration": "PT58S"},
        }]
    }

    with patch("harness.agents.competitor.YouTubeTranscriptApi") as MockTranscript:
        MockTranscript.get_transcript.return_value = [
            {"text": "Dogs can smell cancer.", "start": 0.0, "duration": 2.0}
        ]
        with patch("requests.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, content=b"fakejpeg")
            result = refresh_channel(mock_youtube, "UCtest", subscriber_count=100000)

    assert result["videos_pulled"] >= 1
    video_files = list((channel_dir / "videos").glob("*.json"))
    assert len(video_files) == 1
    video_data = json.loads(video_files[0].read_text())
    assert video_data["video_id"] == "vid001"
    assert "hook" in video_data
    assert "like_rate" in video_data


def test_run_daily_refresh_skips_fresh_channels(tmp_path, monkeypatch):
    """Channels scanned within 24h are skipped."""
    monkeypatch.setattr("harness.agents.competitor.DATA_DIR", tmp_path)
    ch_dir = tmp_path / "competitors" / "UCfresh"
    ch_dir.mkdir(parents=True)
    (ch_dir / "channel.json").write_text(json.dumps({
        "channel_id": "UCfresh",
        "subscriber_count": 50000,
        "last_scanned": datetime.now().isoformat(),
    }))

    mock_youtube = MagicMock()
    with patch("harness.agents.competitor.get_youtube_service", return_value=mock_youtube):
        with patch("harness.agents.competitor.refresh_channel") as mock_refresh:
            run_daily_refresh(channel_ids=["UCfresh"])
            mock_refresh.assert_not_called()
