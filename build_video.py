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
from config import load_config, VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_CRF, VIDEO_PRESET, AUDIO_BITRATE, AUDIO_SAMPLE_RATE, TARGET_DURATION_MIN, TARGET_DURATION_MAX
from utils import log, get_random_dog_clip
from caption_engine import build_caption_filter, CaptionStyle, write_word_ass
from clip_scheduler import get_clips_for_video

MUSIC_DIR = Path(__file__).parent / "assets" / "music"
MUSIC_VOLUME = 0.45  # background music at 45% of voiceover volume


def _pick_music_track() -> Path | None:
    """Pick a random MP3 from assets/music/. Returns None if folder empty."""
    if not MUSIC_DIR.exists():
        return None
    tracks = list(MUSIC_DIR.glob("*.mp3"))
    return random.choice(tracks) if tracks else None

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


def _assign_cut_durations(n_clips: int, audio_duration: float) -> list:
    """
    Assign a random duration (2.0–3.0s) to each clip, scaled so they sum to audio_duration.

    Args:
        n_clips: Number of clip segments needed.
        audio_duration: Total duration all segments must fill exactly.

    Returns:
        List of float durations, one per clip, summing to audio_duration.
    """
    raw = [random.uniform(1.0, 2.0) for _ in range(n_clips)]
    total = sum(raw)
    return [r * audio_duration / total for r in raw]


def _concat_clips(clip_paths: list, audio_duration: float) -> str:
    """
    Extract one random-duration segment from each clip and concatenate them.

    Each clip gets a proportionally-scaled random duration between 2–3s.
    Short clips are looped to cover their assigned duration.
    The result is a single raw concatenated video (no audio, no scale) in a temp file.

    Args:
        clip_paths: Ordered list of Path objects for source clips.
        audio_duration: Total duration the concatenated video must fill.

    Returns:
        Path to concatenated temp video as str.
    """
    temp_dir = Path(tempfile.gettempdir())
    durations = _assign_cut_durations(len(clip_paths), audio_duration)

    segment_paths = []
    for i, (clip, dur) in enumerate(zip(clip_paths, durations)):
        clip_dur = HardwareAccelerator.get_video_duration(str(clip))
        seg_out = temp_dir / f"canine_seg_{i}_{clip.stem}.mp4"

        # Re-encode every segment to a consistent format (yuv420p, 30fps, 1080x1920).
        # Stream-copy (-c:v copy) causes freezes when clips have mismatched codecs/fps.
        if clip_dur is None or clip_dur < dur:
            loops = int(dur / (clip_dur or 1)) + 2
            cmd = [
                "ffmpeg", "-stream_loop", str(loops),
                "-i", str(clip),
                "-t", f"{dur:.3f}",
                "-vf", f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-r", "30",
                "-c:v", "libx264", "-crf", "26", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-an", "-y", str(seg_out),
            ]
        else:
            max_start = clip_dur - dur
            start = random.uniform(0, max_start)
            cmd = [
                "ffmpeg",
                "-ss", f"{start:.3f}",
                "-i", str(clip),
                "-t", f"{dur:.3f}",
                "-vf", f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-r", "30",
                "-c:v", "libx264", "-crf", "26", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                "-an", "-y", str(seg_out),
            ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0 or not seg_out.exists():
            raise Exception(f"Segment extraction failed for {clip.name}: {result.stderr[-300:]}")
        segment_paths.append(seg_out)

    # Write concat list file
    concat_list = temp_dir / "canine_concat_list.txt"
    with open(concat_list, "w") as f:
        for seg in segment_paths:
            f.write(f"file '{seg}'\n")

    # Concatenate pre-normalised segments — all same codec/fps/resolution so copy is safe
    concat_out = temp_dir / "canine_concat.mp4"
    cmd = [
        "ffmpeg", "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy", "-y", str(concat_out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0 or not concat_out.exists():
        raise Exception(f"Concat failed: {result.stderr[-300:]}")

    return str(concat_out)


def build_video(audio_duration: float, clip_path: str = None,
                word_timestamps: list = None, hook_overlay: str = None) -> str:
    """
    Build vertical Shorts video with fast hardware-accelerated encoding.

    Features:
    - Automatic GPU detection (NVIDIA/AMD/Intel)
    - Random video segment matching audio duration
    - Simplified filter chain for speed
    - Direct scaling without loops
    - No pre-transcoding
    - Word-by-word animated captions
    - Hook overlay text in first 1.5 seconds
    - Duration clamp to 25-35 seconds

    Args:
        audio_duration: Duration of audio track in seconds
        clip_path: Optional path to video clip (defaults to random from dog_footage/)
        word_timestamps: Optional list of word-level timestamps for captions
        hook_overlay: Optional hook text to overlay in first 1.5 seconds

    Returns:
        str: Path to final_video.mp4
    """

    cfg = load_config()
    dog_footage_dir = cfg["dog_footage_dir"]

    log("🎬 Step 3: Building vertical Shorts video...")

    voiceover_path = Path("outputs/voiceover.mp3")
    if not voiceover_path.exists():
        raise FileNotFoundError(f"Audio file not found: {voiceover_path}")

    # Detect encoder using any available clip
    all_clips = sorted(dog_footage_dir.iterdir())
    first_clip = next(
        (c for c in all_clips if c.suffix.lower() in {".mp4", ".mov"}), None
    )
    if not first_clip:
        raise FileNotFoundError(f"No clips found in {dog_footage_dir}")
    optimizer = VideoOptimizer(str(first_clip))
    enc_params = optimizer.get_encoding_params()

    # Always use multi-clip mode. If a topic-matched clip was downloaded,
    # copy it into the footage library first so it gets included in rotation.
    if clip_path and Path(clip_path).exists():
        topic_clip = Path(clip_path)
        dest = dog_footage_dir / topic_clip.name
        if not dest.exists():
            import shutil
            shutil.copy2(str(topic_clip), str(dest))
            log(f"📥 Added topic clip to library: {topic_clip.name}")

    clips = get_clips_for_video(dog_footage_dir, audio_duration)
    log(f"📹 Multi-clip mode: {len(clips)} cuts from LRU rotation")
    for i, c in enumerate(clips):
        log(f"   [{i+1}] {c.name}")
    actual_video_path = _concat_clips(clips, audio_duration)
    log(f"✂️  Concat complete: {actual_video_path}")

    # Duration clamp: enforce 25-35s range
    if audio_duration < TARGET_DURATION_MIN:
        log(f"⚠️  Audio is {audio_duration:.1f}s — shorter than target {TARGET_DURATION_MIN}s")
    elif audio_duration > TARGET_DURATION_MAX:
        log(f"⚠️  Audio is {audio_duration:.1f}s — longer than target {TARGET_DURATION_MAX}s")
        audio_duration = float(TARGET_DURATION_MAX)
        log(f"✂️  Clamping video to {TARGET_DURATION_MAX}s")

    # Cinematic filter: Ken Burns slow zoom → scale → warm color grade → vignette
    base_filter = (
        "zoompan=z='min(zoom+0.0015,1.5)':d=150"
        ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
        f"eq=brightness=0.04:saturation=1.25:contrast=1.15,"
        f"colorbalance=rs=0.08:gs=0:bs=-0.08,"
        f"vignette=PI/5"
    )

    # Build ASS subtitle file containing both hook overlay and word captions.
    # ASS avoids the ffmpeg -vf comma/quote parsing issues that affect drawtext.
    style = CaptionStyle(font_size=88, font_color="white", stroke_width=6)
    ass_file = write_word_ass(
        word_timestamps or [],
        style,
        VIDEO_WIDTH,
        VIDEO_HEIGHT,
        hook_overlay=hook_overlay,
    )

    filter_parts = [base_filter]
    if ass_file:
        filter_parts.append(f"subtitles={ass_file}")

    video_filter = ",".join(filter_parts)

    music_track = _pick_music_track()
    if music_track:
        log(f"🎵 Mixing background music: {music_track.name} at {int(MUSIC_VOLUME * 100)}% volume")
        cmd = [
            "ffmpeg",
            "-i", actual_video_path,
            "-i", str(voiceover_path),
            "-stream_loop", "-1", "-i", str(music_track),
            "-c:v", enc_params["codec"],
            "-crf", enc_params["crf"],
            "-preset", enc_params["preset"],
            "-vf", video_filter,
            "-filter_complex",
            f"[1:a]volume=1.0[voice];[2:a]volume={MUSIC_VOLUME}[music];[voice][music]amix=inputs=2:duration=first[aout]",
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:a", "aac",
            "-b:a", AUDIO_BITRATE,
            "-ar", str(AUDIO_SAMPLE_RATE),
            "-t", str(audio_duration),
            "-y",
            "outputs/final_video.mp4"
        ]
    else:
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
            "-t", str(audio_duration),
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
