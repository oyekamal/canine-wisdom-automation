"""Tests for generate_script module."""

import inspect


def test_generate_script_accepts_channel_config_param():
    """generate_script must accept an optional channel_config keyword argument."""
    from generate_script import generate_script
    sig = inspect.signature(generate_script)
    assert "channel_config" in sig.parameters


def test_build_prompt_uses_channel_niche():
    """When channel_config provided, its niche appears in the built prompt."""
    from generate_script import _build_prompt
    from pathlib import Path

    class FakeCfg:
        niche = "horror narration channel for sleepless nights"
        topic_clusters = ["horror", "paranormal"]
        prompt_path = Path("/nonexistent/prompt.txt")  # does not exist → use niche
        affiliate_links = {}

    prompt = _build_prompt(FakeCfg())
    assert "horror narration channel" in prompt
