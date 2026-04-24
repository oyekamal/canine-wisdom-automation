"""
Tests for build_video module.

Tests cover:
1. Video building with ffmpeg (if available)
2. Missing voiceover error
3. Random dog clip selection
"""

import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from build_video import build_video


class TestBuildVideo(unittest.TestCase):
    """Test cases for build_video() function."""

    @patch("build_video.log")
    @patch("build_video.get_random_dog_clip")
    @patch("build_video.subprocess.run")
    @patch("build_video.load_config")
    def test_build_video_success_with_mocked_ffmpeg(
        self,
        mock_load_config,
        mock_subprocess_run,
        mock_get_random_dog_clip,
        mock_log
    ):
        """Test successful video building with mocked ffmpeg."""

        # Setup config mock
        outputs_dir = Path("/tmp/test_outputs")
        dog_footage_dir = Path("/tmp/test_dog_footage")

        mock_load_config.return_value = {
            "dog_footage_dir": dog_footage_dir,
            "outputs_dir": outputs_dir,
        }

        # Setup random dog clip mock
        mock_get_random_dog_clip.return_value = "/tmp/test_dog_footage/clip.mp4"

        # Setup voiceover mock (create a mock file context)
        with patch("build_video.Path") as mock_path_class:
            # Create a proper mock for Path instances
            mock_voiceover_path = MagicMock()
            mock_voiceover_path.exists.return_value = True
            mock_voiceover_path.__str__.return_value = "/tmp/test_outputs/voiceover.mp3"

            mock_output_path = MagicMock()
            mock_output_path.__str__.return_value = "/tmp/test_outputs/final_video.mp4"

            # Mock Path constructor to return appropriate mocks
            def path_constructor(path_str):
                if "voiceover" in str(path_str):
                    return mock_voiceover_path
                elif "final_video" in str(path_str):
                    return mock_output_path
                else:
                    # Return a real Path for other operations
                    return Path(path_str)

            mock_path_class.side_effect = path_constructor

            # subprocess.run should not raise
            mock_subprocess_run.return_value = None

            # Call build_video
            result = build_video()

            # Assertions
            assert result == "/tmp/test_outputs/final_video.mp4"
            mock_subprocess_run.assert_called_once()

            # Verify ffmpeg was called with expected arguments
            call_args = mock_subprocess_run.call_args
            cmd = call_args[0][0]  # First positional arg is the command list

            assert cmd[0] == "ffmpeg"
            assert "-c:v" in cmd
            assert "libx264" in cmd
            assert "-vf" in cmd

            # Verify video filter contains scale
            vf_index = cmd.index("-vf")
            video_filter = cmd[vf_index + 1]
            assert "scale=1080:1920:force_original_aspect_ratio=decrease" in video_filter

    @patch("build_video.log")
    @patch("build_video.subprocess.run")
    @patch("build_video.get_random_dog_clip")
    @patch("build_video.load_config")
    def test_build_video_missing_voiceover(
        self,
        mock_load_config,
        mock_get_random_dog_clip,
        mock_subprocess_run,
        mock_log
    ):
        """Test error when voiceover.mp3 is missing."""

        # Setup config mock with mocked output dir
        mock_outputs_dir = MagicMock()
        mock_dog_footage_dir = MagicMock()

        # Mock the voiceover file path
        mock_voiceover_path = MagicMock()
        mock_voiceover_path.exists.return_value = False

        # When outputs_dir / "voiceover.mp3" is called, return the mock voiceover
        mock_outputs_dir.__truediv__.return_value = mock_voiceover_path

        mock_load_config.return_value = {
            "dog_footage_dir": mock_dog_footage_dir,
            "outputs_dir": mock_outputs_dir,
        }

        mock_get_random_dog_clip.return_value = "/tmp/test_dog_footage/clip.mp4"

        # Should raise FileNotFoundError
        with self.assertRaises(FileNotFoundError) as context:
            build_video()

        assert "Voiceover file not found" in str(context.exception)

    @patch("build_video.log")
    @patch("build_video.subprocess.run")
    @patch("build_video.get_random_dog_clip")
    @patch("build_video.load_config")
    def test_build_video_ffmpeg_command_structure(
        self,
        mock_load_config,
        mock_get_random_dog_clip,
        mock_subprocess_run,
        mock_log
    ):
        """Test that ffmpeg command has correct structure and flags."""

        # Setup config mock
        outputs_dir = Path("/tmp/test_outputs")
        dog_footage_dir = Path("/tmp/test_dog_footage")

        mock_load_config.return_value = {
            "dog_footage_dir": dog_footage_dir,
            "outputs_dir": outputs_dir,
        }

        mock_get_random_dog_clip.return_value = "/tmp/test_dog_footage/clip.mp4"

        with patch("build_video.Path") as mock_path_class:
            mock_voiceover_path = MagicMock()
            mock_voiceover_path.exists.return_value = True
            mock_voiceover_path.__str__.return_value = "/tmp/test_outputs/voiceover.mp3"

            mock_output_path = MagicMock()
            mock_output_path.__str__.return_value = "/tmp/test_outputs/final_video.mp4"

            def path_constructor(path_str):
                if "voiceover" in str(path_str):
                    return mock_voiceover_path
                elif "final_video" in str(path_str):
                    return mock_output_path
                else:
                    return Path(path_str)

            mock_path_class.side_effect = path_constructor
            mock_subprocess_run.return_value = None

            build_video()

            # Get the ffmpeg command
            call_args = mock_subprocess_run.call_args
            cmd = call_args[0][0]

            # Verify key flags are present
            assert "-c:v" in cmd
            assert "-crf" in cmd
            assert "-preset" in cmd
            assert "-vf" in cmd
            assert "-c:a" in cmd
            assert "-b:a" in cmd
            assert "-ar" in cmd
            assert "-shortest" in cmd
            assert "-y" in cmd

            # Verify video filter components
            vf_index = cmd.index("-vf")
            video_filter = cmd[vf_index + 1]
            assert "scale=1080:1920:force_original_aspect_ratio=decrease" in video_filter
            assert "pad=1080:1920:(ow-iw)/2:(oh-ih)/2" in video_filter
            assert "eq=brightness=0.02:saturation=1.3" in video_filter
            assert "loop=-1:1" in video_filter

    @patch("build_video.log")
    @patch("build_video.subprocess.run")
    @patch("build_video.get_random_dog_clip")
    @patch("build_video.load_config")
    def test_build_video_ffmpeg_error_handling(
        self,
        mock_load_config,
        mock_get_random_dog_clip,
        mock_subprocess_run,
        mock_log
    ):
        """Test error handling when ffmpeg command fails."""

        # Setup config mock
        outputs_dir = Path("/tmp/test_outputs")
        dog_footage_dir = Path("/tmp/test_dog_footage")

        mock_load_config.return_value = {
            "dog_footage_dir": dog_footage_dir,
            "outputs_dir": outputs_dir,
        }

        mock_get_random_dog_clip.return_value = "/tmp/test_dog_footage/clip.mp4"

        with patch("build_video.Path") as mock_path_class:
            mock_voiceover_path = MagicMock()
            mock_voiceover_path.exists.return_value = True
            mock_voiceover_path.__str__.return_value = "/tmp/test_outputs/voiceover.mp3"

            def path_constructor(path_str):
                if "voiceover" in str(path_str):
                    return mock_voiceover_path
                else:
                    return Path(path_str)

            mock_path_class.side_effect = path_constructor

            # Mock ffmpeg to raise CalledProcessError
            import subprocess
            error = subprocess.CalledProcessError(
                returncode=1,
                cmd="ffmpeg"
            )
            error.stdout = ""
            error.stderr = "Error encoding video"
            mock_subprocess_run.side_effect = error

            # Should raise Exception with helpful message
            with self.assertRaises(Exception) as context:
                build_video()

            assert "ffmpeg command failed" in str(context.exception)


if __name__ == "__main__":
    unittest.main()
