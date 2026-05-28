import sys
from unittest.mock import patch


def test_run_pipeline_accepts_channel_config():
    """run_pipeline must accept an optional channel_config keyword argument."""
    import inspect
    from harness.orchestrator import run_pipeline
    sig = inspect.signature(run_pipeline)
    assert "channel_config" in sig.parameters


def test_load_channel_from_args_defaults_to_canine_wisdom():
    """With no --channel arg, _load_channel_from_args returns canine-wisdom config."""
    from harness.orchestrator import _load_channel_from_args
    with patch("sys.argv", ["orchestrator"]):
        cfg = _load_channel_from_args()
    assert cfg.slug == "canine-wisdom"


def test_load_channel_from_args_loads_specified_channel(tmp_path, monkeypatch):
    """--channel flag loads the specified channel slug."""
    import json
    from harness.orchestrator import _load_channel_from_args

    ch_dir = tmp_path / "test-ch"
    ch_dir.mkdir()
    (ch_dir / "settings.json").write_text(json.dumps({
        "channel_name": "Test", "niche": "n", "voice_id": "v",
        "youtube_category_id": "22", "topic_clusters": [],
        "description_template": "", "affiliate_links": {},
    }))
    (ch_dir / "data").mkdir()

    with patch("sys.argv", ["orchestrator", "--channel", "test-ch"]), \
         patch("channel_config.CHANNELS_ROOT", tmp_path):
        cfg = _load_channel_from_args()
    assert cfg.slug == "test-ch"
