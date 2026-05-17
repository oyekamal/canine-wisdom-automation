"""
Optimized Video Assembly with Hardware Acceleration
Fast encoding with GPU support and simplified filters.
"""

import subprocess
import json
import psutil
import random
import tempfile
from pathlib import Path
from config import load_config, VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_CRF, VIDEO_PRESET, AUDIO_BITRATE, AUDIO_SAMPLE_RATE
from utils import log, get_random_dog_clip


class HardwareAccelerator:
    """Detect and use available hardware acceleration"""

    @staticmethod
    def detect_encoder():
        """Detect best available hardware encoder"""
        encoders_to_try = [
            ("hevc_nvenc", "NVIDIA GPU (fastest)"),
            ("hevc_amf", "AMD GPU"),
            ("hevc_qsv", "Intel QuickSync"),
            ("libx265", "CPU H.265 (fast)"),
        ]

        for encoder, name in encoders_to_try:
            try:
                result = subprocess.run(
                    ["ffmpeg", "-encoders", "-hide_banner"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if encoder in result.stdout:
                    return encoder, name
            except:
                pass

        return "libx264", "CPU H.264 (fallback)"

    @staticmethod
    def detect_input_format(video_path):
        """Get input video resolution and codec"""
        try:
            cmd = [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,codec_name",
                "-of", "json", str(video_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data.get("streams"):
                    return data["streams"][0]
        except:
            pass
        return None

    @staticmethod
    def get_video_duration(video_path):
        """Get video duration in seconds"""
        try:
            cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(video_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return float(result.stdout.strip())
        except:
            pass
        return None


class VideoOptimizer:
    """Fast video optimization with minimal re-encoding"""

    def __init__(self, video_path):
        self.video_path = Path(video_path)
        self.encoder, self.encoder_name = HardwareAccelerator.detect_encoder()
        self.input_info = HardwareAccelerator.detect_input_format(video_path)
        self.duration = HardwareAccelerator.get_video_duration(video_path)
        log(f"🎬 Using encoder: {self.encoder_name}")

    def get_encoding_params(self):
        """Get optimized encoding parameters"""
        if self.encoder.startswith("hevc"):
            return {
                "codec": self.encoder,
                "crf": "28",
                "preset": "fast" if "nvenc" in self.encoder else "medium"
            }
        elif self.encoder == "libx265":
            return {
                "codec": "libx265",
                "crf": "26",
                "preset": "ultrafast"
            }
        else:
            return {
                "codec": "libx264",
                "crf": "26",
                "preset": "ultrafast"
            }

    def trim_video_segment(self, audio_duration: float) -> str:
        """
        Trim video to match audio duration from random start position.

        Args:
            audio_duration: Duration of audio in seconds

        Returns:
            Path to trimmed video segment
        """
        if not self.duration:
            log(f"⚠️  Could not detect video duration, using full video")
            return str(self.video_path)

        if self.duration < audio_duration:
            log(f"🔁 Video shorter than audio ({self.duration:.1f}s < {audio_duration:.1f}s), looping to match")
            temp_dir = Path(tempfile.gettempdir())
            looped_video = temp_dir / f"canine_loop_{self.video_path.stem}.mp4"
            loops_needed = int(audio_duration / self.duration) + 2
            try:
                cmd = [
                    "ffmpeg",
                    "-stream_loop", str(loops_needed),
                    "-i", str(self.video_path),
                    "-t", str(audio_duration),
                    "-c:v", "copy",
                    "-an",
                    "-y",
                    str(looped_video)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if result.returncode == 0 and looped_video.exists():
                    return str(looped_video)
            except Exception as e:
                log(f"⚠️  Loop failed: {e}, using full video")
            return str(self.video_path)

        # Calculate random start position
        max_start = self.duration - audio_duration
        start_pos = random.uniform(0, max_start)

        # Create temp file for trimmed segment
        temp_dir = Path(tempfile.gettempdir())
        trimmed_video = temp_dir / f"canine_segment_{self.video_path.stem}.mp4"

        try:
            cmd = [
                "ffmpeg",
                "-i", str(self.video_path),
                "-ss", str(start_pos),
                "-t", str(audio_duration),
                "-c:v", "copy",
                "-c:a", "copy",
                "-y",
                str(trimmed_video)
            ]

            log(f"✂️  Trimming video: {start_pos:.1f}s to {start_pos + audio_duration:.1f}s")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0 and trimmed_video.exists():
                return str(trimmed_video)
            else:
                log(f"⚠️  Trim failed, using full video")
                return str(self.video_path)

        except Exception as e:
            log(f"⚠️  Trim error: {e}, using full video")
            return str(self.video_path)


def build_video(audio_duration: float, clip_path: str = None) -> str:
    """
    Build vertical Shorts video with fast hardware-accelerated encoding.

    Features:
    - Automatic GPU detection (NVIDIA/AMD/Intel)
    - Random video segment matching audio duration
    - Simplified filter chain for speed
    - Direct scaling without loops
    - No pre-transcoding

    Args:
        audio_duration: Duration of audio track in seconds

    Returns:
        str: Path to final_video.mp4
    """

    cfg = load_config()
    dog_footage_dir = cfg["dog_footage_dir"]

    log("🎬 Step 3: Building vertical Shorts video...")

    if clip_path and Path(clip_path).exists():
        dog_clip = clip_path
        log(f"📹 Using topic-matched clip: {Path(dog_clip).name}")
    else:
        dog_clip = get_random_dog_clip(dog_footage_dir)
        log(f"📹 Selected dog clip: {Path(dog_clip).name}")

    voiceover_path = Path("outputs/voiceover.mp3")
    if not voiceover_path.exists():
        raise FileNotFoundError(f"Audio file not found: {voiceover_path}")

    # Initialize optimizer with hardware detection
    optimizer = VideoOptimizer(dog_clip)
    enc_params = optimizer.get_encoding_params()

    # Trim video to match audio duration from random start position
    actual_video_path = optimizer.trim_video_segment(audio_duration)

    # Simplified filter chain: just scale + pad + brightness boost
    video_filter = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
        f"eq=brightness=0.02:saturation=1.3"
    )

    cmd = [
        "ffmpeg",
        "-i", actual_video_path,
        "-i", str(voiceover_path),
        "-c:v", enc_params["codec"],
        "-crf", enc_params["crf"],
        "-preset", enc_params["preset"],
        "-vf", video_filter,
        "-c:a", "aac",
        "-b:a", AUDIO_BITRATE,
        "-ar", str(AUDIO_SAMPLE_RATE),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-shortest",
        "-y",
        "outputs/final_video.mp4"
    ]

    try:
        log(f"⏳ Encoding with {optimizer.encoder_name}...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            error_output = result.stderr[-500:] if result.stderr else "Unknown error"
            raise Exception(f"ffmpeg error: {error_output}")

    except FileNotFoundError:
        raise Exception(
            "ffmpeg not found. Install with:\n"
            "  Mac: brew install ffmpeg\n"
            "  Linux: sudo apt install ffmpeg\n"
            "  Windows: download from ffmpeg.org"
        )

    final_video = "outputs/final_video.mp4"

    # Verify output
    if not Path(final_video).exists():
        raise Exception("Video encoding failed - no output file created")

    final_size_mb = Path(final_video).stat().st_size / (1024 * 1024)
    log(f"✅ Video saved to {final_video}")
    log(f"📦 Output size: {final_size_mb:.1f} MB")
    log("✅ Vertical Shorts video built!")

    return final_video
