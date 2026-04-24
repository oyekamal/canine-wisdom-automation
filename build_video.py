"""
Video assembly module for Canine Wisdom YouTube Shorts Pipeline.

Combines dog footage with voiceover into a vertical Shorts video using ffmpeg.
"""

import subprocess
from pathlib import Path
from config import load_config, VIDEO_CRF, VIDEO_PRESET, AUDIO_BITRATE, AUDIO_SAMPLE_RATE
from utils import log, get_random_dog_clip


def build_video() -> str:
    """
    Assemble vertical Shorts video from dog footage and voiceover.

    Process:
    1. Load configuration
    2. Log: "🎬 Step 3: Building vertical Shorts video..."
    3. Get random dog clip using get_random_dog_clip()
    4. Log: f"📹 Selected dog clip: {Path(dog_clip).name}"
    5. Verify outputs/voiceover.mp3 exists
    6. Build ffmpeg command with exact flags:
       - Input 1: dog_clip
       - Input 2: outputs/voiceover.mp3
       - Video codec: libx264
       - CRF: 20 (from config)
       - Preset: fast (from config)
       - Video filter: scale=1080:1920:force_original_aspect_ratio=decrease,
                       pad=1080:1920:(ow-iw)/2:(oh-ih)/2,
                       eq=brightness=0.02:saturation=1.3,loop=-1:1
       - Audio codec: aac
       - Audio bitrate: 192k (from config)
       - Sample rate: 44100 Hz (from config)
       - Shortest flag: -shortest
       - Overwrite: -y
       - Output: outputs/final_video.mp4
    7. Run subprocess with timeout=120 (2 minutes)
    8. Log: f"✅ Video saved to {final_video}"
    9. Log: "✅ Vertical Shorts video built!"
    10. Return final_video path

    Returns:
        str: Path to final_video.mp4

    Raises:
        FileNotFoundError: If voiceover.mp3 or ffmpeg not found.
        Exception: If ffmpeg returns non-zero exit code.
    """

    # ========================================================================
    # Step 1: Load Configuration
    # ========================================================================

    cfg = load_config()
    dog_footage_dir = cfg["dog_footage_dir"]
    outputs_dir = cfg["outputs_dir"]

    # ========================================================================
    # Step 2: Log Start
    # ========================================================================

    log("🎬 Step 3: Building vertical Shorts video...")

    # ========================================================================
    # Step 3: Get Random Dog Clip
    # ========================================================================

    dog_clip = get_random_dog_clip(dog_footage_dir)

    # ========================================================================
    # Step 4: Log Selected Clip
    # ========================================================================

    log(f"📹 Selected dog clip: {Path(dog_clip).name}")

    # ========================================================================
    # Step 5: Verify Voiceover Exists
    # ========================================================================

    voiceover_file = outputs_dir / "voiceover.mp3"
    if not voiceover_file.exists():
        raise FileNotFoundError(
            f"Voiceover file not found at {voiceover_file}. "
            "Run generate_audio() first."
        )

    # ========================================================================
    # Step 6: Define Nested run_ffmpeg() Function
    # ========================================================================

    def run_ffmpeg() -> str:
        """
        Run ffmpeg to assemble video.

        Returns:
            str: Path to final_video.mp4

        Raises:
            FileNotFoundError: If ffmpeg is not installed.
            Exception: If ffmpeg returns non-zero exit code.
        """

        # Define output path
        output_path = outputs_dir / "final_video.mp4"

        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            # Input 1: dog_clip
            "-i", dog_clip,
            # Input 2: voiceover
            "-i", str(voiceover_file),
            # Video codec
            "-c:v", "libx264",
            # CRF (quality, 0-51, lower is better)
            "-crf", str(VIDEO_CRF),
            # Preset (speed/compression tradeoff)
            "-preset", VIDEO_PRESET,
            # Video filter: scale + pad + brightness/saturation + loop
            "-vf", (
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
                "eq=brightness=0.02:saturation=1.3,"
                "loop=-1:1"
            ),
            # Audio codec
            "-c:a", "aac",
            # Audio bitrate
            "-b:a", AUDIO_BITRATE,
            # Audio sample rate
            "-ar", str(AUDIO_SAMPLE_RATE),
            # Use shortest input duration
            "-shortest",
            # Overwrite output file if exists
            "-y",
            # Output path
            str(output_path),
        ]

        try:
            # Run ffmpeg with 120 second timeout
            subprocess.run(
                cmd,
                check=True,
                timeout=120,
                capture_output=True,
                text=True
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                "ffmpeg not found. Please install ffmpeg: "
                "macOS (brew install ffmpeg) | Ubuntu (apt-get install ffmpeg) | "
                "Windows (choco install ffmpeg)"
            )
        except subprocess.CalledProcessError as e:
            raise Exception(
                f"ffmpeg command failed with exit code {e.returncode}.\n"
                f"stdout: {e.stdout}\nstderr: {e.stderr}"
            )

        return str(output_path)

    # ========================================================================
    # Step 7: Run ffmpeg (no retry - errors are deterministic)
    # ========================================================================

    final_video = run_ffmpeg()

    # ========================================================================
    # Step 8: Log Save Location
    # ========================================================================

    log(f"✅ Video saved to {final_video}")

    # ========================================================================
    # Step 9: Log Completion
    # ========================================================================

    log("✅ Vertical Shorts video built!")

    # ========================================================================
    # Step 10: Return Final Video Path
    # ========================================================================

    return final_video
