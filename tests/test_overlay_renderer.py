# tests/test_overlay_renderer.py
import os
import pytest
from unittest.mock import patch
from overlay_renderer import render_overlay, OverlayConfig


def test_render_overlay_returns_webm_path(tmp_path):
    """render_overlay returns the output path when render succeeds."""
    fake_webm = tmp_path / "overlay.webm"
    fake_webm.write_bytes(b"fake")

    config = OverlayConfig(
        channel_slug="canine-wisdom",
        template_name="hook",
        placeholders={"{{HOOK_TEXT}}": "Test hook", "{{EMOJI}}": "🐕", "{{DURATION}}": "3"},
        width=1080,
        height=1920,
        duration=3.0,
        output_path=str(fake_webm),
    )

    with patch("overlay_renderer._call_node_renderer", return_value=0):
        result = render_overlay(config)

    assert result == str(fake_webm)
    assert result.endswith(".webm")


def test_render_overlay_raises_on_nonzero_exit(tmp_path):
    """render_overlay raises RuntimeError when node exits nonzero."""
    config = OverlayConfig(
        channel_slug="canine-wisdom",
        template_name="hook",
        placeholders={"{{HOOK_TEXT}}": "Test", "{{EMOJI}}": "🐕", "{{DURATION}}": "3"},
        width=1080,
        height=1920,
        duration=3.0,
        output_path=str(tmp_path / "overlay.webm"),
    )
    with patch("overlay_renderer._call_node_renderer", return_value=1):
        with pytest.raises(RuntimeError, match="HyperFrames render failed"):
            render_overlay(config)


def test_render_overlay_raises_on_missing_template(tmp_path):
    """render_overlay raises FileNotFoundError for unknown channel/template."""
    config = OverlayConfig(
        channel_slug="nonexistent-channel",
        template_name="hook",
        placeholders={},
        width=1080,
        height=1920,
        duration=3.0,
        output_path=str(tmp_path / "overlay.webm"),
    )
    with pytest.raises(FileNotFoundError):
        render_overlay(config)


def test_placeholder_substitution(tmp_path):
    """render_overlay substitutes all placeholders in the HTML before rendering."""
    fake_webm = tmp_path / "overlay.webm"
    fake_webm.write_bytes(b"fake")

    captured_html = []

    def fake_renderer(template, output, width, height, duration):
        with open(template) as f:
            captured_html.append(f.read())
        return 0

    config = OverlayConfig(
        channel_slug="canine-wisdom",
        template_name="hook",
        placeholders={"{{HOOK_TEXT}}": "Amazing fact!", "{{EMOJI}}": "🐾", "{{DURATION}}": "3"},
        width=1080,
        height=1920,
        duration=3.0,
        output_path=str(fake_webm),
    )

    with patch("overlay_renderer._call_node_renderer", side_effect=fake_renderer):
        render_overlay(config)

    assert "Amazing fact!" in captured_html[0]
    assert "🐾" in captured_html[0]
    assert "{{HOOK_TEXT}}" not in captured_html[0]
    assert "{{EMOJI}}" not in captured_html[0]
