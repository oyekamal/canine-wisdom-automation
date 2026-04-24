"""
Tests for utils.py module covering logging, retry, and file helpers.
"""

import os
import sys
import tempfile
import time
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from utils import (
    Logger,
    retry_with_backoff,
    get_random_dog_clip,
)


# ============================================================================
# PART 1: LOGGING TESTS
# ============================================================================

class TestLogger:
    """Test Logger class functionality."""

    def test_logger_creates_parent_directory(self, tmp_path):
        """Logger should create parent directory if it doesn't exist."""
        log_file = tmp_path / "nested" / "dir" / "test.log"
        logger = Logger(log_file)
        assert log_file.parent.exists()

    def test_logger_writes_to_file(self, tmp_path):
        """Logger should write messages to file."""
        log_file = tmp_path / "test.log"
        logger = Logger(log_file)

        logger.log("Test message", level="info")

        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content
        assert "[INFO]" in content

    def test_logger_includes_timestamp(self, tmp_path):
        """Logger should include timestamp in ISO format."""
        log_file = tmp_path / "test.log"
        logger = Logger(log_file)

        logger.log("Test message", level="info")

        content = log_file.read_text()
        # Check for timestamp format YYYY-MM-DDTHH:MM:SS
        import re
        assert re.search(r"\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\]", content)

    def test_logger_handles_emoji_messages(self, tmp_path):
        """Logger should handle emoji-prefixed messages without level prefix."""
        log_file = tmp_path / "test.log"
        logger = Logger(log_file)

        logger.log("🚀 Rocket message")
        logger.log("✅ Success message")

        content = log_file.read_text()
        # Emoji messages should have emoji and timestamp but no [LEVEL] prefix
        assert "🚀 Rocket message" in content
        assert "✅ Success message" in content
        # Make sure there's no [INFO] or [ERROR] before emoji
        assert not any(
            f"[{level}] 🚀" in content
            for level in ["INFO", "ERROR", "WARNING", "DEBUG"]
        )

    def test_logger_appends_to_file(self, tmp_path):
        """Logger should append messages, not overwrite."""
        log_file = tmp_path / "test.log"
        logger = Logger(log_file)

        logger.log("First message")
        logger.log("Second message")

        content = log_file.read_text()
        assert "First message" in content
        assert "Second message" in content
        assert content.index("First") < content.index("Second")

    def test_logger_without_file_path(self, capsys):
        """Logger should work without file path (terminal only)."""
        logger = Logger(None)
        logger.log("Terminal message", level="info")

        captured = capsys.readouterr()
        assert "Terminal message" in captured.out

    def test_logger_handles_all_emoji_types(self, tmp_path):
        """Logger should handle all specified emoji types."""
        log_file = tmp_path / "test.log"
        logger = Logger(log_file)

        emojis = ["🚀", "📝", "✅", "🎤", "🎬", "📤", "🎉", "❌", "⚠️"]
        for emoji in emojis:
            logger.log(f"{emoji} Test message for {emoji}")

        content = log_file.read_text()
        for emoji in emojis:
            assert emoji in content


# ============================================================================
# PART 2: RETRY LOGIC TESTS
# ============================================================================

class TestRetryWithBackoff:
    """Test retry_with_backoff function."""

    def test_retry_succeeds_on_first_attempt(self):
        """Function that succeeds should return immediately."""
        call_count = {"count": 0}

        def success_func():
            call_count["count"] += 1
            return "success"

        result = retry_with_backoff(success_func, max_retries=3)
        assert result == "success"
        assert call_count["count"] == 1

    def test_retry_succeeds_after_one_failure(self, capsys):
        """Function that fails once then succeeds should retry."""
        call_count = {"count": 0}

        def fail_once():
            call_count["count"] += 1
            if call_count["count"] < 2:
                raise ValueError("First attempt fails")
            return "success"

        with patch('utils.log'):
            result = retry_with_backoff(fail_once, max_retries=1, initial_backoff=0.01)

        assert result == "success"
        assert call_count["count"] == 2

    def test_retry_exhausts_max_retries(self):
        """Function that always fails should exhaust retries."""
        call_count = {"count": 0}

        def always_fails():
            call_count["count"] += 1
            raise ValueError("Always fails")

        with patch('utils.log'):
            with pytest.raises(ValueError):
                retry_with_backoff(always_fails, max_retries=2, initial_backoff=0.001)

        # Should attempt 3 times (max_retries=2 means 2+1 attempts)
        assert call_count["count"] == 3

    def test_retry_exponential_backoff(self):
        """Retry should use exponential backoff."""
        call_count = {"count": 0}

        def fail_twice():
            call_count["count"] += 1
            if call_count["count"] < 3:
                raise ValueError("Fails")
            return "success"

        start = time.time()
        with patch('utils.log'):
            result = retry_with_backoff(
                fail_twice,
                max_retries=2,
                initial_backoff=0.05
            )
        elapsed = time.time() - start

        assert result == "success"
        assert call_count["count"] == 3
        # Should have slept: 0.05s (2^0) + 0.1s (0.05 * 2^1) = 0.15s minimum
        # Allow some tolerance for system variation
        assert elapsed >= 0.1

    def test_retry_raises_original_exception(self):
        """Retry should raise original exception after exhaustion."""
        def always_fails():
            raise RuntimeError("Custom error")

        with patch('utils.log'):
            with pytest.raises(RuntimeError) as exc_info:
                retry_with_backoff(always_fails, max_retries=1, initial_backoff=0.001)

        assert str(exc_info.value) == "Custom error"

    def test_retry_custom_step_name(self):
        """Retry should log custom step name."""
        call_count = {"count": 0}
        logged_messages = []

        def fail_once():
            call_count["count"] += 1
            if call_count["count"] < 2:
                raise ValueError("Fail")
            return "success"

        def mock_log(msg, level="info"):
            logged_messages.append(msg)

        with patch('utils.log', side_effect=mock_log):
            retry_with_backoff(
                fail_once,
                max_retries=1,
                initial_backoff=0.001,
                step_name="CustomStep"
            )

        # Check that custom step name was logged
        assert any("CustomStep" in msg for msg in logged_messages)


# ============================================================================
# PART 3: FILE HELPERS TESTS
# ============================================================================

class TestFileHelpers:
    """Test file helper functions."""

    def test_get_random_dog_clip(self, tmp_path):
        """get_random_dog_clip should return random video clip."""
        dog_footage_dir = tmp_path / "dog_footage"
        dog_footage_dir.mkdir()

        # Create test video files
        (dog_footage_dir / "dog1.mp4").write_text("video1")
        (dog_footage_dir / "dog2.mov").write_text("video2")
        (dog_footage_dir / "dog3.mp4").write_text("video3")
        (dog_footage_dir / "image.png").write_text("image")

        # Get random clip multiple times - should be one of the videos
        for _ in range(10):
            clip = get_random_dog_clip(dog_footage_dir)
            assert clip.endswith((".mp4", ".mov"))
            assert "image.png" not in clip

    def test_get_random_dog_clip_case_insensitive(self, tmp_path):
        """get_random_dog_clip should handle uppercase extensions."""
        dog_footage_dir = tmp_path / "dog_footage"
        dog_footage_dir.mkdir()

        # Create test video files with uppercase extensions
        (dog_footage_dir / "dog1.MP4").write_text("video1")
        (dog_footage_dir / "dog2.MOV").write_text("video2")

        clip = get_random_dog_clip(dog_footage_dir)
        assert clip.endswith((".MP4", ".MOV", ".mp4", ".mov"))

    def test_get_random_dog_clip_raises_error_if_no_clips(self, tmp_path):
        """get_random_dog_clip should raise FileNotFoundError if no clips."""
        dog_footage_dir = tmp_path / "dog_footage"
        dog_footage_dir.mkdir()

        # Only create non-video files
        (dog_footage_dir / "image.png").write_text("image")
        (dog_footage_dir / "readme.txt").write_text("readme")

        with pytest.raises(FileNotFoundError):
            get_random_dog_clip(dog_footage_dir)

    def test_get_random_dog_clip_empty_directory(self, tmp_path):
        """get_random_dog_clip should raise FileNotFoundError if directory empty."""
        dog_footage_dir = tmp_path / "dog_footage"
        dog_footage_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            get_random_dog_clip(dog_footage_dir)

    def test_get_random_dog_clip_only_mp4(self, tmp_path):
        """get_random_dog_clip should work with only mp4 files."""
        dog_footage_dir = tmp_path / "dog_footage"
        dog_footage_dir.mkdir()

        (dog_footage_dir / "dog1.mp4").write_text("video1")
        (dog_footage_dir / "dog2.mp4").write_text("video2")

        clip = get_random_dog_clip(dog_footage_dir)
        assert clip.endswith(".mp4")

    def test_get_random_dog_clip_returns_string(self, tmp_path):
        """get_random_dog_clip should return string, not Path object."""
        dog_footage_dir = tmp_path / "dog_footage"
        dog_footage_dir.mkdir()

        (dog_footage_dir / "dog.mp4").write_text("video")

        clip = get_random_dog_clip(dog_footage_dir)
        assert isinstance(clip, str)


# ============================================================================
# INTEGRATION TESTS FOR CONFIG-DEPENDENT FUNCTIONS
# ============================================================================

class TestInitLoggerWithMocking:
    """Test init_logger with mocked config."""

    def test_init_logger_creates_log_file(self, tmp_path):
        """init_logger should create log file in run_logs directory."""
        mock_config = {
            "run_logs_dir": tmp_path / "run_logs"
        }
        mock_config["run_logs_dir"].mkdir(exist_ok=True)

        with patch('utils.load_config', return_value=mock_config):
            import utils
            utils._logger = None
            utils._log_file = None

            logger = utils.init_logger(run_id="test_run_2026_04_24")

            # Write to log to ensure file is created
            logger.log("Test log entry")

            assert logger is not None
            assert (tmp_path / "run_logs" / "test_run_2026_04_24.log").exists()


class TestFileHelperFunctionsWithMocking:
    """Test file helper functions with mocked config."""

    def test_ensure_outputs_dir(self, tmp_path):
        """ensure_outputs_dir should create outputs directory."""
        outputs_dir = tmp_path / "outputs"
        mock_config = {"outputs_dir": outputs_dir}

        with patch('utils.load_config', return_value=mock_config):
            from utils import ensure_outputs_dir
            ensure_outputs_dir()
            assert outputs_dir.exists()

    def test_clear_outputs_dir(self, tmp_path):
        """clear_outputs_dir should remove files but not subdirectories."""
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()

        # Create test files and subdirectory
        (outputs_dir / "file1.txt").write_text("content1")
        (outputs_dir / "file2.txt").write_text("content2")
        subdir = outputs_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested")

        mock_config = {"outputs_dir": outputs_dir}

        with patch('utils.load_config', return_value=mock_config):
            from utils import clear_outputs_dir
            clear_outputs_dir()

        # Files should be removed
        assert not (outputs_dir / "file1.txt").exists()
        assert not (outputs_dir / "file2.txt").exists()
        # Subdirectory should remain
        assert subdir.exists()
        assert (subdir / "nested.txt").exists()

    def test_move_outputs_to_archive(self, tmp_path):
        """move_outputs_to_archive should move files and log file."""
        outputs_dir = tmp_path / "outputs"
        archive_dir = tmp_path / "archive"
        run_logs_dir = tmp_path / "run_logs"

        outputs_dir.mkdir(exist_ok=True)
        archive_dir.mkdir(exist_ok=True)
        run_logs_dir.mkdir(exist_ok=True)

        # Create test files and log file
        (outputs_dir / "output1.mp4").write_text("video1")
        (outputs_dir / "output2.mp4").write_text("video2")
        (run_logs_dir / "test_run.log").write_text("log content")

        mock_config = {
            "outputs_dir": outputs_dir,
            "archive_dir": archive_dir,
            "run_logs_dir": run_logs_dir,
        }

        with patch('utils.load_config', return_value=mock_config):
            with patch('utils.log'):
                from utils import move_outputs_to_archive
                move_outputs_to_archive("test_run")

        # Files should be moved to archive/test_run/
        assert (archive_dir / "test_run" / "output1.mp4").exists()
        assert (archive_dir / "test_run" / "output2.mp4").exists()
        assert (archive_dir / "test_run" / "test_run.log").exists()

        # Original files should not exist
        assert not (outputs_dir / "output1.mp4").exists()
        assert not (outputs_dir / "output2.mp4").exists()
        assert not (run_logs_dir / "test_run.log").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
