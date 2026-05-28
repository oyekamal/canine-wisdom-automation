import json
from pathlib import Path
from unittest.mock import patch
from footage_db import scan_footage_dir, get_clips_for_channel, FOOTAGE_DB_FILE


def test_scan_footage_dir_returns_list(tmp_path):
    """scan_footage_dir returns a list of clip dicts."""
    fake_mp4 = tmp_path / "pexels_12345_nosleep.mp4"
    fake_mp4.write_bytes(b"fake")

    with patch("footage_db._probe_clip") as mock_probe:
        mock_probe.return_value = {"duration": 10.0, "width": 1080, "height": 1920, "fps": 30.0}
        clips = scan_footage_dir(tmp_path)

    assert len(clips) == 1
    assert clips[0]["filename"] == "pexels_12345_nosleep.mp4"
    assert clips[0]["topic_cluster"] == "nosleep"
    assert clips[0]["source"] == "pexels"
    assert clips[0]["duration_secs"] == 10.0


def test_scan_footage_dir_parses_topic_from_filename(tmp_path):
    """Filename pattern pexels_ID_TOPIC.mp4 → topic_cluster extracted."""
    (tmp_path / "pexels_999_dog_fun.mp4").write_bytes(b"x")
    (tmp_path / "pixabay_888_nosleep.mp4").write_bytes(b"x")
    (tmp_path / "unknown_clip.mp4").write_bytes(b"x")

    with patch("footage_db._probe_clip", return_value={"duration": 5.0, "width": 1080, "height": 1920, "fps": 30.0}):
        clips = scan_footage_dir(tmp_path)

    topics = {c["filename"]: c["topic_cluster"] for c in clips}
    assert topics["pexels_999_dog_fun.mp4"] == "dog_fun"
    assert topics["pixabay_888_nosleep.mp4"] == "nosleep"
    assert topics["unknown_clip.mp4"] == "unknown"


def test_get_clips_for_channel_filters_by_dir(tmp_path):
    """get_clips_for_channel returns clips from the channel's footage_dir."""
    import json as _json
    settings = {
        "channel_name": "T", "niche": "n", "voice_id": "v",
        "youtube_category_id": "22", "topic_clusters": [],
        "description_template": "", "affiliate_links": {},
        "footage_dir": str(tmp_path / "footage"),
    }
    (tmp_path / "settings.json").write_text(_json.dumps(settings))

    footage_dir = tmp_path / "footage"
    footage_dir.mkdir()
    (footage_dir / "pexels_1_nosleep.mp4").write_bytes(b"x")

    class FakeCfg:
        channel_dir = tmp_path
        slug = "test"

    with patch("footage_db._probe_clip", return_value={"duration": 5.0, "width": 1080, "height": 1920, "fps": 30.0}):
        clips = get_clips_for_channel(FakeCfg())

    assert len(clips) == 1
    assert clips[0]["topic_cluster"] == "nosleep"
