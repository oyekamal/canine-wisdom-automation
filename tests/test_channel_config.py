import json
import pytest
from pathlib import Path
from channel_config import ChannelConfig, load_channel_config


def test_load_channel_config_returns_dataclass(tmp_path):
    """load_channel_config reads settings.json and returns a ChannelConfig."""
    ch_dir = tmp_path / "channels" / "test-channel"
    ch_dir.mkdir(parents=True)
    settings = {
        "channel_name": "Test Channel",
        "niche": "test niche",
        "voice_id": "abc123",
        "youtube_category_id": "22",
        "topic_clusters": ["topic a", "topic b"],
        "description_template": "{video_script}\n\n{hashtags}",
        "affiliate_links": {},
    }
    (ch_dir / "settings.json").write_text(json.dumps(settings))

    cfg = load_channel_config("test-channel", channels_root=tmp_path / "channels")

    assert cfg.channel_name == "Test Channel"
    assert cfg.niche == "test niche"
    assert cfg.voice_id == "abc123"
    assert cfg.youtube_category_id == "22"
    assert cfg.topic_clusters == ["topic a", "topic b"]
    assert cfg.channel_dir == ch_dir


def test_load_channel_config_raises_on_missing_channel(tmp_path):
    with pytest.raises(FileNotFoundError, match="Channel 'ghost' not found"):
        load_channel_config("ghost", channels_root=tmp_path / "channels")


def test_load_channel_config_raises_on_missing_required_field(tmp_path):
    ch_dir = tmp_path / "channels" / "bad-channel"
    ch_dir.mkdir(parents=True)
    (ch_dir / "settings.json").write_text(json.dumps({"channel_name": "Bad"}))
    with pytest.raises(KeyError):
        load_channel_config("bad-channel", channels_root=tmp_path / "channels")


def test_data_dir_is_inside_channel_dir(tmp_path):
    ch_dir = tmp_path / "channels" / "test-channel"
    ch_dir.mkdir(parents=True)
    settings = {
        "channel_name": "T", "niche": "n", "voice_id": "v",
        "youtube_category_id": "15", "topic_clusters": [],
        "description_template": "", "affiliate_links": {},
    }
    (ch_dir / "settings.json").write_text(json.dumps(settings))
    cfg = load_channel_config("test-channel", channels_root=tmp_path / "channels")
    assert cfg.data_dir == ch_dir / "data"
    assert cfg.state_path == ch_dir / "data" / "state.json"
