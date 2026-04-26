"""
Optimized Video Assembly with Hardware Acceleration
Fast encoding with GPU support and simplified filters.
"""

import subprocess
import json
import psutil
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


class VideoOptimizer:
    """Fast video optimization with minimal re-encoding"""

    def __init__(self, video_path):
        self.video_path = Path(video_path)
        self.encoder, self.encoder_name = HardwareAccelerator.detect_encoder()
        self.input_info = HardwareAccelerator.detect_input_format(video_path)
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


def build_video() -> str:
    """
    Build vertical Shorts video with fast hardware-accelerated encoding.

    Features:
    - Automatic GPU detection (NVIDIA/AMD/Intel)
    - Simplified filter chain for speed
    - Direct scaling without loops
    - No pre-transcoding

    Returns:
        str: Path to final_video.mp4
    """

    cfg = load_config()
    dog_footage_dir = cfg["dog_footage_dir"]

    log("🎬 Step 3: Building vertical Shorts video...")

    dog_clip = get_random_dog_clip(dog_footage_dir)
    log(f"📹 Selected dog clip: {Path(dog_clip).name}")

    voiceover_path = Path("outputs/voiceover.mp3")
    if not voiceover_path.exists():
        raise FileNotFoundError(f"Audio file not found: {voiceover_path}")

    # Initialize optimizer with hardware detection
    optimizer = VideoOptimizer(dog_clip)
    enc_params = optimizer.get_encoding_params()

    # Simplified filter chain: just scale + pad + brightness boost
    video_filter = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
        f"eq=brightness=0.02:saturation=1.3"
    )

    cmd = [
        "ffmpeg",
        "-i", dog_clip,
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
