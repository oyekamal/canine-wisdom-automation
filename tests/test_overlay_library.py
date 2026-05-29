# tests/test_overlay_library.py
import os
import pytest
from pathlib import Path
from unittest.mock import patch
from overlay_library import get_or_render_overlay, _content_hash, OverlayRequest


def test_content_hash_is_deterministic():
    content = {"hook_text": "Dogs can smell cancer!", "emoji": "🐕", "duration": "3"}
    assert _content_hash(content) == _content_hash(content)


def test_content_hash_differs_for_different_content():
    a = {"hook_text": "Fact A"}
    b = {"hook_text": "Fact B"}
    assert _content_hash(a) != _content_hash(b)


def test_get_or_render_returns_cached_path(tmp_path):
    """Returns existing file path without calling render_overlay."""
    overlay_dir = tmp_path / "canine-wisdom" / "hook"
    overlay_dir.mkdir(parents=True)
    content = {"{{HOOK_TEXT}}": "Test", "{{EMOJI}}": "🐕", "{{DURATION}}": "3"}
    hash_val = _content_hash(content)
    cached = overlay_dir / f"{hash_val}.webm"
    cached.write_bytes(b"fake webm")

    req = OverlayRequest(
        channel_slug="canine-wisdom",
        template_name="hook",
        placeholders=content,
        width=1080,
        height=1920,
        duration=3.0,
    )

    with patch("overlay_library.OVERLAYS_DIR", tmp_path):
        with patch("overlay_library.render_overlay") as mock_render:
            result = get_or_render_overlay(req)
            mock_render.assert_not_called()

    assert result == str(cached)


def test_get_or_render_calls_render_on_cache_miss(tmp_path):
    """Calls render_overlay when cached file does not exist."""
    content = {"{{HOOK_TEXT}}": "New Fact", "{{EMOJI}}": "🐾", "{{DURATION}}": "3"}
    hash_val = _content_hash(content)
    expected_path = tmp_path / "canine-wisdom" / "hook" / f"{hash_val}.webm"

    req = OverlayRequest(
        channel_slug="canine-wisdom",
        template_name="hook",
        placeholders=content,
        width=1080,
        height=1920,
        duration=3.0,
    )

    def fake_render(config):
        Path(config.output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(config.output_path).write_bytes(b"rendered")
        return config.output_path

    with patch("overlay_library.OVERLAYS_DIR", tmp_path):
        with patch("overlay_library.render_overlay", side_effect=fake_render):
            result = get_or_render_overlay(req)

    assert result == str(expected_path)
    assert expected_path.exists()
