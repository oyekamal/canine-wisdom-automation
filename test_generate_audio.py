"""
Tests for generate_audio module.

Tests cover:
1. generate_audio() creates voiceover.mp3
2. Correct duration calculation (192kbps = 24 KB/sec)
3. Error handling for bad API key (401)
4. Error handling for invalid request (400)
5. Error handling for missing script.txt
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from generate_audio import generate_audio


@pytest.fixture
def mock_config():
    """Fixture to mock load_config in both generate_audio and utils modules."""
    def _mock_config(outputs_dir):
        return {
            "elevenlabs_api_key": "test_key",
            "elevenlabs_voice_id": "test_voice_id",
            "outputs_dir": outputs_dir,
            "run_logs_dir": Path("/tmp/test_logs")
        }
    return _mock_config


class TestGenerateAudio:
    """Test suite for generate_audio function."""

    @patch("utils.load_config")
    @patch("generate_audio.requests.post")
    @patch("generate_audio.load_config")
    def test_generate_audio_success(self, mock_load_config_ga, mock_post, mock_load_config_utils):
        """Test successful voiceover generation."""

        # Setup: Create mock config
        tmp_dir = Path("/tmp/test_outputs")
        tmp_dir.mkdir(exist_ok=True)

        script_file = tmp_dir / "script.txt"
        script_file.write_text("Test dog fact script")

        config = {
            "elevenlabs_api_key": "test_key",
            "elevenlabs_voice_id": "test_voice_id",
            "outputs_dir": tmp_dir,
            "run_logs_dir": Path("/tmp/test_logs")
        }
        mock_load_config_ga.return_value = config
        mock_load_config_utils.return_value = config

        # Setup: Mock successful API response
        mock_audio_data = b"mock_mp3_binary_data_" * 100  # ~2.1 KB
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = mock_audio_data
        mock_post.return_value = mock_response

        # Execute
        duration = generate_audio()

        # Assert: Audio file created
        audio_file = tmp_dir / "voiceover.mp3"
        assert audio_file.exists()

        # Assert: Audio data written correctly
        assert audio_file.read_bytes() == mock_audio_data

        # Assert: Duration calculated correctly
        audio_size_kb = len(mock_audio_data) / 1024
        expected_duration = audio_size_kb / 24
        assert abs(duration - expected_duration) < 0.01

        # Assert: API called with correct parameters
        call_args = mock_post.call_args
        assert "test_key" in str(call_args)
        assert "Test dog fact script" in str(call_args)

    @patch("utils.load_config")
    @patch("generate_audio.requests.post")
    @patch("generate_audio.load_config")
    def test_generate_audio_duration_calculation(self, mock_load_config_ga, mock_post, mock_load_config_utils):
        """Test duration calculation with various audio sizes."""

        tmp_dir = Path("/tmp/test_outputs")
        tmp_dir.mkdir(exist_ok=True)

        script_file = tmp_dir / "script.txt"
        script_file.write_text("Test script")

        config = {
            "elevenlabs_api_key": "key",
            "elevenlabs_voice_id": "voice_id",
            "outputs_dir": tmp_dir,
            "run_logs_dir": Path("/tmp/test_logs")
        }
        mock_load_config_ga.return_value = config
        mock_load_config_utils.return_value = config

        # Test case: 24 KB audio should be 1 second (192kbps = 24 KB/s)
        audio_data = b"x" * (24 * 1024)  # 24 KB
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = audio_data
        mock_post.return_value = mock_response

        duration = generate_audio()
        assert abs(duration - 1.0) < 0.01

    @patch("utils.load_config")
    @patch("generate_audio.requests.post")
    @patch("generate_audio.load_config")
    def test_generate_audio_invalid_api_key(self, mock_load_config_ga, mock_post, mock_load_config_utils):
        """Test error handling for invalid API key (401)."""

        tmp_dir = Path("/tmp/test_outputs")
        tmp_dir.mkdir(exist_ok=True)

        script_file = tmp_dir / "script.txt"
        script_file.write_text("Test script")

        config = {
            "elevenlabs_api_key": "invalid_key",
            "elevenlabs_voice_id": "voice_id",
            "outputs_dir": tmp_dir,
            "run_logs_dir": Path("/tmp/test_logs")
        }
        mock_load_config_ga.return_value = config
        mock_load_config_utils.return_value = config

        # Mock 401 response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        # Assert: Exception raised with helpful message
        with pytest.raises(Exception) as exc_info:
            generate_audio()

        assert "ElevenLabs API key invalid" in str(exc_info.value)

    @patch("utils.load_config")
    @patch("generate_audio.requests.post")
    @patch("generate_audio.load_config")
    def test_generate_audio_bad_request(self, mock_load_config_ga, mock_post, mock_load_config_utils):
        """Test error handling for bad request (400)."""

        tmp_dir = Path("/tmp/test_outputs")
        tmp_dir.mkdir(exist_ok=True)

        script_file = tmp_dir / "script.txt"
        script_file.write_text("Test script")

        config = {
            "elevenlabs_api_key": "key",
            "elevenlabs_voice_id": "voice_id",
            "outputs_dir": tmp_dir,
            "run_logs_dir": Path("/tmp/test_logs")
        }
        mock_load_config_ga.return_value = config
        mock_load_config_utils.return_value = config

        # Mock 400 response
        error_message = "Invalid voice settings"
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = error_message
        mock_post.return_value = mock_response

        # Assert: ValueError raised with response text
        with pytest.raises(ValueError) as exc_info:
            generate_audio()

        assert error_message in str(exc_info.value)

    @patch("utils.load_config")
    @patch("generate_audio.requests.post")
    @patch("generate_audio.load_config")
    def test_generate_audio_missing_script(self, mock_load_config_ga, mock_post, mock_load_config_utils):
        """Test error handling for missing script.txt."""

        # Use unique temp directory for this test
        tmp_dir = Path(tempfile.mkdtemp(prefix="test_missing_script_"))
        tmp_logs = Path(tempfile.mkdtemp(prefix="test_logs_"))

        try:
            config = {
                "elevenlabs_api_key": "key",
                "elevenlabs_voice_id": "voice_id",
                "outputs_dir": tmp_dir,
                "run_logs_dir": tmp_logs
            }
            mock_load_config_ga.return_value = config
            mock_load_config_utils.return_value = config

            # Assert: FileNotFoundError raised
            with pytest.raises(FileNotFoundError) as exc_info:
                generate_audio()

            assert "Script file not found" in str(exc_info.value)
        finally:
            # Cleanup
            shutil.rmtree(tmp_dir, ignore_errors=True)
            shutil.rmtree(tmp_logs, ignore_errors=True)

    @patch("utils.load_config")
    @patch("generate_audio.requests.post")
    @patch("generate_audio.load_config")
    def test_generate_audio_api_call_parameters(self, mock_load_config_ga, mock_post, mock_load_config_utils):
        """Test that API call is made with correct parameters."""

        tmp_dir = Path("/tmp/test_outputs")
        tmp_dir.mkdir(exist_ok=True)

        script_file = tmp_dir / "script.txt"
        script_text = "Did you know dogs have 21 amazing abilities?"
        script_file.write_text(script_text)

        config = {
            "elevenlabs_api_key": "test_api_key_123",
            "elevenlabs_voice_id": "voice_xyz",
            "outputs_dir": tmp_dir,
            "run_logs_dir": Path("/tmp/test_logs")
        }
        mock_load_config_ga.return_value = config
        mock_load_config_utils.return_value = config

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"audio_data"
        mock_post.return_value = mock_response

        generate_audio()

        # Verify POST request details
        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Check URL
        url = call_args[0][0] if call_args[0] else call_args[1].get("url")
        assert "text-to-speech/voice_xyz" in url

        # Check headers
        headers = call_args[1].get("headers", {})
        assert headers["xi-api-key"] == "test_api_key_123"
        assert headers["Content-Type"] == "application/json"

        # Check request data
        request_data = call_args[1].get("json", {})
        assert request_data["text"] == script_text
        assert request_data["voice_settings"]["stability"] == 0.4
        assert request_data["voice_settings"]["similarity_boost"] == 0.8
        assert request_data["voice_settings"]["style"] == 0.6
        assert request_data["voice_settings"]["use_speaker_boost"] is True

    @patch("utils.load_config")
    @patch("generate_audio.requests.post")
    @patch("generate_audio.load_config")
    def test_generate_audio_timeout_retry(self, mock_load_config_ga, mock_post, mock_load_config_utils):
        """Test retry logic on timeout."""

        tmp_dir = Path("/tmp/test_outputs")
        tmp_dir.mkdir(exist_ok=True)

        script_file = tmp_dir / "script.txt"
        script_file.write_text("Test script")

        config = {
            "elevenlabs_api_key": "key",
            "elevenlabs_voice_id": "voice_id",
            "outputs_dir": tmp_dir,
            "run_logs_dir": Path("/tmp/test_logs")
        }
        mock_load_config_ga.return_value = config
        mock_load_config_utils.return_value = config

        # Mock first call fails, second succeeds
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.content = b"audio_data" * 100

        mock_post.side_effect = [
            Exception("Timeout"),
            mock_response_success
        ]

        # Should succeed after retry
        duration = generate_audio()
        assert duration > 0
        assert mock_post.call_count == 2

    @patch("utils.load_config")
    @patch("generate_audio.requests.post")
    @patch("generate_audio.load_config")
    def test_generate_audio_unexpected_status_code(self, mock_load_config_ga, mock_post, mock_load_config_utils):
        """Test error handling for unexpected status codes."""

        tmp_dir = Path("/tmp/test_outputs")
        tmp_dir.mkdir(exist_ok=True)

        script_file = tmp_dir / "script.txt"
        script_file.write_text("Test script")

        config = {
            "elevenlabs_api_key": "key",
            "elevenlabs_voice_id": "voice_id",
            "outputs_dir": tmp_dir,
            "run_logs_dir": Path("/tmp/test_logs")
        }
        mock_load_config_ga.return_value = config
        mock_load_config_utils.return_value = config

        # Mock 500 error
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        with pytest.raises(Exception) as exc_info:
            generate_audio()

        assert "500" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
