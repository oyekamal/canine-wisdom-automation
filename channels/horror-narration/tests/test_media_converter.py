import pytest
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock


def _load_module(module_path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


media_converter = _load_module(
    Path(__file__).parent.parent / "harness" / "media_converter.py",
    "media_converter"
)


def test_image_to_video_returns_mp4_path(tmp_path):
    """image_to_video returns the output path string on success."""
    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"\xff\xd8\xff" + b"x" * 5000)
    output = tmp_path / "out.mp4"

    def fake_run(cmd, **kwargs):
        output.write_bytes(b"fake_video")
        return MagicMock(returncode=0)

    with patch("subprocess.run", side_effect=fake_run):
        result = media_converter.image_to_video(str(fake_img), str(output), duration=25.0)

    assert result == str(output)


def test_image_to_video_uses_loop_flag(tmp_path):
    """image_to_video command must include -loop 1 for static image."""
    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"\xff\xd8\xff" + b"x" * 5000)
    output = tmp_path / "out.mp4"

    captured_cmd = []

    def fake_run(cmd, **kwargs):
        captured_cmd.extend(cmd)
        output.write_bytes(b"fake")
        return MagicMock(returncode=0)

    with patch("subprocess.run", side_effect=fake_run):
        media_converter.image_to_video(str(fake_img), str(output), duration=25.0)

    assert "-loop" in captured_cmd
    assert "1" in captured_cmd
    assert "-t" in captured_cmd


def test_image_to_video_returns_none_on_failure(tmp_path):
    """image_to_video returns None if ffmpeg fails."""
    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"\xff\xd8\xff" + b"x" * 5000)
    output = tmp_path / "out.mp4"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = media_converter.image_to_video(str(fake_img), str(output), duration=25.0)

    assert result is None


def test_is_image_file_detects_jpg():
    """is_image_file returns True for image extensions."""
    assert media_converter.is_image_file("photo.jpg") is True
    assert media_converter.is_image_file("photo.PNG") is True
    assert media_converter.is_image_file("video.mp4") is False
    assert media_converter.is_image_file("file.txt") is False
