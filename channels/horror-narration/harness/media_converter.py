"""
Convert Reddit media (images/videos) into video clips usable by build_video.

Images: converted to looping video via ffmpeg -loop 1 with slow Ken Burns zoom.
Videos: returned as-is (already MP4 from yt-dlp download).

Ken Burns zoom is safe here because we work with a single static source,
not mixing variable-fps clips (which caused the earlier freeze bug).
"""
import subprocess
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def is_image_file(path: str) -> bool:
    """Return True if the file has an image extension."""
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def image_to_video(
    image_path: str,
    output_path: str,
    duration: float,
    width: int = 1080,
    height: int = 1920,
) -> str | None:
    """
    Convert a static image to a video clip using ffmpeg -loop 1.

    Applies slow Ken Burns zoom (safe on single image — no fps-mixing issue).
    Output is constant 30fps h264, duration matches audio length.

    Returns output_path as string on success, None on failure.
    """
    d_frames = int(duration * 30)

    cmd = [
        "ffmpeg",
        "-loop", "1",
        "-i", str(image_path),
        "-t", str(duration),
        "-vf", (
            f"scale={width * 2}:{height * 2},"
            f"zoompan=z='min(zoom+0.0003,1.15)':d={d_frames}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
            f"scale={width}:{height},"
            f"eq=brightness=0.02:saturation=1.1:contrast=1.05,"
            f"vignette=PI/4"
        ),
        "-r", "30",
        "-vsync", "cfr",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "slow",
        "-bf", "0",
        "-g", "30",
        "-pix_fmt", "yuv420p",
        "-an",
        "-y", str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and Path(output_path).exists():
            return str(output_path)
        return None
    except Exception:
        return None


def prepare_reddit_media(media_path: str, duration: float, save_dir: str) -> str | None:
    """
    Ensure Reddit media is in a usable video format for build_video.

    - .mp4: returned as-is
    - image (.jpg etc): converted to video with Ken Burns zoom

    Returns path to usable .mp4 clip, or None on failure.
    """
    p = Path(media_path)
    if not p.exists():
        return None

    if p.suffix.lower() == ".mp4":
        return str(p)

    if is_image_file(str(p)):
        output_path = Path(save_dir) / (p.stem + "_converted.mp4")
        if output_path.exists():
            return str(output_path)
        return image_to_video(str(p), str(output_path), duration=duration)

    return None
