"""
Configuration module for Canine Wisdom YouTube Shorts Pipeline.

Handles environment loading, validation, and provides API constants.
"""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv


# ============================================================================
# Custom Exception Class
# ============================================================================

class ConfigError(Exception):
    """Raised when configuration validation fails."""
    pass


# ============================================================================
# API Constants
# ============================================================================

# Anthropic API Configuration
ANTHROPIC_API_BASE = "https://api.anthropic.com"
ANTHROPIC_MODEL = "claude-opus-4-5"
ANTHROPIC_MAX_TOKENS = 500

# ElevenLabs API Configuration
ELEVENLABS_API_BASE = "https://api.elevenlabs.io"

# YouTube API Configuration
YOUTUBE_API_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

# Retry & Backoff Configuration
MAX_RETRIES = 1
INITIAL_BACKOFF = 2

# Video Encoding Configuration
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_CRF = 20
VIDEO_PRESET = "fast"


class VideoFormat(Enum):
    SHORT = "short"   # vertical 1080×1920 YouTube Short
    LONG  = "long"    # landscape 1920×1080 long-form video


LONG_VIDEO_WIDTH  = 1920
LONG_VIDEO_HEIGHT = 1080

# Target Short duration
TARGET_DURATION_MIN = 25   # seconds
TARGET_DURATION_MAX = 35   # seconds
# Approx 130 words per minute → 25-35s ≈ 54-76 words
TARGET_WORD_COUNT_MIN = 54
TARGET_WORD_COUNT_MAX = 76

# Audio Configuration
AUDIO_BITRATE = "192k"
AUDIO_SAMPLE_RATE = 44100


# ============================================================================
# Configuration Loading & Validation
# ============================================================================

def load_config() -> Dict[str, Any]:
    """
    Load and validate configuration from environment variables and filesystem.

    Returns:
        Dict with configuration values and paths:
        - anthropic_api_key: str
        - elevenlabs_api_key: str
        - elevenlabs_voice_id: str
        - dog_footage_dir: Path
        - outputs_dir: Path
        - archive_dir: Path
        - run_logs_dir: Path

    Raises:
        ConfigError: If required environment variables are missing or validation fails.
    """

    # Load .env file if it exists
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # ========================================================================
    # Load Required Environment Variables
    # ========================================================================

    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        raise ConfigError(
            "ANTHROPIC_API_KEY is not set. Please set it in .env or environment."
        )

    elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
    if not elevenlabs_api_key:
        raise ConfigError(
            "ELEVENLABS_API_KEY is not set. Please set it in .env or environment."
        )

    # ========================================================================
    # Load Optional Environment Variables (with defaults)
    # ========================================================================

    elevenlabs_voice_id = os.getenv(
        "ELEVENLABS_VOICE_ID",
        "pNInz6obpgDQGcFmaJgB"
    )

    # ========================================================================
    # Define Paths
    # ========================================================================

    base_dir = Path(__file__).parent
    dog_footage_dir = base_dir / "dog_footage"
    outputs_dir = base_dir / "outputs"
    archive_dir = base_dir / "archive"
    run_logs_dir = base_dir / "run_logs"

    # ========================================================================
    # Validate dog_footage/ Folder Exists
    # ========================================================================

    if not dog_footage_dir.exists():
        raise ConfigError(
            f"dog_footage/ folder not found at {dog_footage_dir}. "
            "Please create it and add video clips."
        )

    # ========================================================================
    # Validate at Least One Video Clip Exists
    # ========================================================================

    video_extensions = {".mp4", ".mov"}
    video_clips = [
        f for f in dog_footage_dir.iterdir()
        if f.is_file() and f.suffix.lower() in video_extensions
    ]

    if not video_clips:
        raise ConfigError(
            f"No .mp4 or .mov video clips found in dog_footage/. "
            f"Path: {dog_footage_dir}"
        )

    # ========================================================================
    # Create Output Directories (mkdir with exist_ok=True)
    # ========================================================================

    outputs_dir.mkdir(exist_ok=True)
    archive_dir.mkdir(exist_ok=True)
    run_logs_dir.mkdir(exist_ok=True)

    # ========================================================================
    # Return Configuration Dictionary
    # ========================================================================

    return {
        "anthropic_api_key": anthropic_api_key,
        "elevenlabs_api_key": elevenlabs_api_key,
        "elevenlabs_voice_id": elevenlabs_voice_id,
        "dog_footage_dir": dog_footage_dir,
        "outputs_dir": outputs_dir,
        "archive_dir": archive_dir,
        "run_logs_dir": run_logs_dir,
    }
