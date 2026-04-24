"""
Utilities module for Canine Wisdom YouTube Shorts Pipeline.

Provides logging, retry logic, and file management helpers.
"""

import os
import time
import shutil
import random
from pathlib import Path
from datetime import datetime
from typing import Callable, Any, Optional
from config import load_config


# ============================================================================
# PART 1: LOGGING
# ============================================================================

# Global logger and log file variables
_logger: Optional["Logger"] = None
_log_file: Optional[Path] = None


class Logger:
    """Logger for pipeline operations with file and terminal output."""

    def __init__(self, log_file_path: Optional[Path] = None):
        """
        Initialize logger with optional log file.

        Args:
            log_file_path: Path to log file. Creates parent directory if needed.
        """
        self.log_file_path = log_file_path
        if self.log_file_path:
            self.log_file_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, message: str, level: str = "info") -> None:
        """
        Log a message to terminal and file.

        Args:
            message: Message to log.
            level: Log level ("info", "error", "warning", "debug").
        """
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        # Check if message starts with emoji
        emoji_prefixes = ("🚀", "📝", "✅", "🎤", "🎬", "📤", "🎉", "❌", "⚠️")
        is_emoji = any(message.startswith(e) for e in emoji_prefixes)

        # Format based on emoji or level
        if is_emoji:
            # Emoji messages don't need level prefix
            formatted = f"[{timestamp}] {message}"
        else:
            formatted = f"[{timestamp}] [{level.upper()}] {message}"

        # Print to terminal
        print(formatted)

        # Write to file if path is set
        if self.log_file_path:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")


def init_logger(run_id: Optional[str] = None) -> Logger:
    """
    Initialize global logger with run-specific log file.

    Args:
        run_id: Optional run ID for log filename. If None, uses current timestamp.

    Returns:
        Logger instance.
    """
    global _logger, _log_file

    cfg = load_config()
    run_logs_dir = cfg["run_logs_dir"]

    if run_id is None:
        run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    _log_file = run_logs_dir / f"{run_id}.log"
    _logger = Logger(_log_file)

    return _logger


def log(message: str, level: str = "info") -> None:
    """
    Global log function with lazy logger initialization.

    Args:
        message: Message to log.
        level: Log level ("info", "error", "warning", "debug").
    """
    global _logger

    if _logger is None:
        init_logger()

    _logger.log(message, level)


def get_logger() -> Logger:
    """
    Get current logger instance.

    Returns:
        Logger instance (initializes if needed).
    """
    global _logger

    if _logger is None:
        init_logger()

    return _logger


# ============================================================================
# PART 2: RETRY LOGIC
# ============================================================================

def retry_with_backoff(
    func: Callable,
    max_retries: int = 1,
    initial_backoff: int = 2,
    step_name: str = "Operation"
) -> Any:
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to retry.
        max_retries: Maximum number of retries (total attempts = max_retries + 1).
        initial_backoff: Initial backoff time in seconds.
        step_name: Name of operation for logging.

    Returns:
        Result of func if successful.

    Raises:
        Exception: If all retries exhausted.
    """
    attempt = 0
    total_attempts = max_retries + 1

    while attempt < total_attempts:
        try:
            return func()
        except Exception as e:
            if attempt < max_retries:
                backoff = initial_backoff * (2 ** attempt)
                log(
                    f"⚠️ {step_name} failed (attempt {attempt + 1}/{total_attempts}). "
                    f"Retrying in {backoff}s...",
                    level="warning"
                )
                time.sleep(backoff)
                attempt += 1
            else:
                log(
                    f"❌ {step_name} failed after {total_attempts} attempts.",
                    level="error"
                )
                raise


# ============================================================================
# PART 3: FILE HELPERS
# ============================================================================

def ensure_outputs_dir() -> None:
    """Create outputs/ directory if it doesn't exist."""
    cfg = load_config()
    cfg["outputs_dir"].mkdir(exist_ok=True)


def clear_outputs_dir() -> None:
    """Remove all files from outputs/ directory (not subdirectories)."""
    cfg = load_config()
    outputs_dir = cfg["outputs_dir"]

    if not outputs_dir.exists():
        return

    for item in outputs_dir.iterdir():
        if item.is_file():
            item.unlink()


def move_outputs_to_archive(run_id: str) -> None:
    """
    Move all outputs and log file to archive/run_id/ directory.

    Args:
        run_id: Run identifier for archive folder.
    """
    cfg = load_config()
    outputs_dir = cfg["outputs_dir"]
    archive_dir = cfg["archive_dir"]
    run_logs_dir = cfg["run_logs_dir"]

    # Create archive/run_id/ directory
    archive_run_dir = archive_dir / run_id
    archive_run_dir.mkdir(parents=True, exist_ok=True)

    # Move all files from outputs/ to archive/run_id/
    if outputs_dir.exists():
        for item in outputs_dir.iterdir():
            if item.is_file():
                shutil.move(str(item), str(archive_run_dir / item.name))

    # Move log file from run_logs/ to archive/run_id/
    log_file = run_logs_dir / f"{run_id}.log"
    if log_file.exists():
        shutil.move(str(log_file), str(archive_run_dir / log_file.name))

    log(f"📦 Archived run to {archive_run_dir}")


def get_random_dog_clip(dog_footage_dir: Path) -> str:
    """
    Get a random dog footage clip from the specified directory.

    Args:
        dog_footage_dir: Path to directory containing dog footage clips.

    Returns:
        Path to random video clip as string.

    Raises:
        FileNotFoundError: If no .mp4 or .mov clips found.
    """
    video_extensions = {".mp4", ".mov"}
    clips = [
        f for f in dog_footage_dir.iterdir()
        if f.is_file() and f.suffix.lower() in video_extensions
    ]

    if not clips:
        raise FileNotFoundError(
            f"No .mp4 or .mov video clips found in {dog_footage_dir}"
        )

    return str(random.choice(clips))
