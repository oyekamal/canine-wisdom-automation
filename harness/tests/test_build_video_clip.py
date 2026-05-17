from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


def test_build_video_uses_provided_clip_path(tmp_path):
    """When clip_path is provided and exists, build_video should use it instead of random."""
    # Create a fake clip
    fake_clip = tmp_path / "my_topic_clip.mp4"
    fake_clip.write_bytes(b"fakemp4")

    # Patch all the heavy dependencies
    with patch("build_video.load_config") as mock_cfg:
        mock_cfg.return_value = {"dog_footage_dir": tmp_path}
        with patch("build_video.VideoOptimizer") as MockOpt:
            mock_opt = MagicMock()
            mock_opt.encoder_name = "CPU"
            mock_opt.trim_video_segment.return_value = str(fake_clip)
            mock_opt.get_encoding_params.return_value = {"codec": "libx264", "crf": "26", "preset": "ultrafast"}
            MockOpt.return_value = mock_opt
            with patch("build_video.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                # Create fake output
                (Path("outputs")).mkdir(exist_ok=True)
                (Path("outputs/voiceover.mp3")).write_bytes(b"fakeaudio")
                (Path("outputs/final_video.mp4")).write_bytes(b"fakevideo")

                import build_video
                result = build_video.build_video(30.0, clip_path=str(fake_clip))

                # Verify VideoOptimizer was called with our clip, not a random one
                MockOpt.assert_called_once_with(str(fake_clip))
