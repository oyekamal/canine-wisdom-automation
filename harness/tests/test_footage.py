import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from harness.tools.footage import (
    _search_pexels,
    _download_clip,
    fetch_footage_for_topic,
    TOPIC_SEARCH_MAP,
    DEFAULT_QUERIES,
)


def make_pexels_response(video_id=1, width=1080, height=1920, duration=30):
    return {
        "videos": [{
            "id": video_id,
            "url": f"https://pexels.com/video/{video_id}",
            "duration": duration,
            "video_files": [
                {"link": f"https://cdn.pexels.com/{video_id}.mp4",
                 "width": width, "height": height, "quality": "hd"}
            ],
        }]
    }


# ── _search_pexels ─────────────────────────────────────────────────────────────

def test_search_pexels_returns_clips():
    mock_resp = MagicMock()
    mock_resp.json.return_value = make_pexels_response(width=1080, height=1920, duration=30)
    with patch("requests.get", return_value=mock_resp):
        results = _search_pexels("dog", api_key="fakekey")
    assert len(results) == 1
    assert results[0]["pexels_id"] == 1
    assert results[0]["height"] == 1920


def test_search_pexels_skips_short_clips():
    mock_resp = MagicMock()
    mock_resp.json.return_value = make_pexels_response(duration=3)  # too short
    with patch("requests.get", return_value=mock_resp):
        results = _search_pexels("dog", api_key="fakekey")
    assert results == []


def test_search_pexels_handles_network_error():
    with patch("requests.get", side_effect=Exception("timeout")):
        results = _search_pexels("dog", api_key="fakekey")
    assert results == []


# ── _download_clip ─────────────────────────────────────────────────────────────

def test_download_clip_writes_file(tmp_path):
    mock_resp = MagicMock()
    mock_resp.iter_content.return_value = [b"fakevideodata"]
    with patch("requests.get", return_value=mock_resp):
        clip = {"download_url": "http://fake.url/vid.mp4", "width": 1080, "height": 1920, "duration": 30}
        result = _download_clip(clip, tmp_path / "test.mp4")
    assert result is True
    assert (tmp_path / "test.mp4").exists()


def test_download_clip_returns_false_on_error(tmp_path):
    with patch("requests.get", side_effect=Exception("network error")):
        clip = {"download_url": "http://fake.url/vid.mp4", "width": 1080, "height": 1920, "duration": 30}
        result = _download_clip(clip, tmp_path / "test.mp4")
    assert result is False


# ── TOPIC_SEARCH_MAP ───────────────────────────────────────────────────────────

def test_all_topic_clusters_have_queries():
    clusters = ["dog health", "dog behavior", "dog breeds", "dog training",
                "dog history", "dog science", "dog fun"]
    for cluster in clusters:
        assert cluster in TOPIC_SEARCH_MAP
        assert len(TOPIC_SEARCH_MAP[cluster]) >= 2


# ── fetch_footage_for_topic ────────────────────────────────────────────────────

def test_fetch_footage_downloads_pexels_clip(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.tools.footage.DOG_FOOTAGE_DIR", tmp_path)
    monkeypatch.setattr("harness.tools.footage.FOOTAGE_INDEX", tmp_path / "footage_index.json")

    mock_search = MagicMock(return_value=[{
        "pexels_id": 42,
        "pexels_url": "https://pexels.com/video/42",
        "download_url": "https://cdn.pexels.com/42.mp4",
        "width": 1080, "height": 1920, "duration": 25,
        "query": "dog nose",
    }])
    mock_download = MagicMock(return_value=True)

    with patch("harness.tools.footage._load_api_key", return_value="fakekey"):
        with patch("harness.tools.footage._search_pexels", mock_search):
            with patch("harness.tools.footage._download_clip", mock_download):
                result = fetch_footage_for_topic("dog health", "dogs detecting cancer")

    assert result is not None
    assert "pexels_42" in result.name


def test_fetch_footage_returns_existing_file(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.tools.footage.DOG_FOOTAGE_DIR", tmp_path)
    monkeypatch.setattr("harness.tools.footage.FOOTAGE_INDEX", tmp_path / "footage_index.json")

    # Pre-create the file
    existing = tmp_path / "pexels_42_dog_health.mp4"
    existing.write_bytes(b"fakedata")

    mock_search = MagicMock(return_value=[{
        "pexels_id": 42,
        "pexels_url": "https://pexels.com/video/42",
        "download_url": "https://cdn.pexels.com/42.mp4",
        "width": 1080, "height": 1920, "duration": 25,
        "query": "dog nose",
    }])

    with patch("harness.tools.footage._load_api_key", return_value="fakekey"):
        with patch("harness.tools.footage._search_pexels", mock_search):
            with patch("harness.tools.footage._download_clip") as mock_dl:
                result = fetch_footage_for_topic("dog health", "dogs detecting cancer")
                mock_dl.assert_not_called()  # already exists, no download

    assert result == existing


def test_fetch_footage_falls_back_to_ytdlp_when_pexels_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.tools.footage.DOG_FOOTAGE_DIR", tmp_path)
    monkeypatch.setattr("harness.tools.footage.FOOTAGE_INDEX", tmp_path / "footage_index.json")

    cc_file = tmp_path / "cc_abc123.mp4"
    cc_file.write_bytes(b"ccvideo")

    with patch("harness.tools.footage._load_api_key", return_value="fakekey"):
        with patch("harness.tools.footage._search_pexels", return_value=[]):
            with patch("harness.tools.footage._yt_dlp_cc_fallback", return_value=cc_file):
                result = fetch_footage_for_topic("dog science", "dog brain research")

    assert result == cc_file


def test_fetch_footage_returns_none_when_all_fail(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.tools.footage.DOG_FOOTAGE_DIR", tmp_path)
    monkeypatch.setattr("harness.tools.footage.FOOTAGE_INDEX", tmp_path / "footage_index.json")

    with patch("harness.tools.footage._load_api_key", return_value="fakekey"):
        with patch("harness.tools.footage._search_pexels", return_value=[]):
            with patch("harness.tools.footage._yt_dlp_cc_fallback", return_value=None):
                result = fetch_footage_for_topic("dog fun", "cute puppies")

    assert result is None
