"""
Per-channel footage clip registry.

Scans a footage directory, probes each clip with ffprobe, and writes a JSON
index. The index is used by build_video.py to know what clips exist, avoid
re-downloading, and pick clips by topic_cluster.

Filename convention: {source}_{id}_{topic_cluster}.mp4
  e.g. pexels_12345_nosleep.mp4  → source=pexels, topic_cluster=nosleep
       pixabay_99_dog_fun.mp4   → source=pixabay, topic_cluster=dog_fun
"""
import json
import subprocess
import re
from pathlib import Path

FOOTAGE_DB_FILE = "footage_index.json"


def _probe_clip(path: Path) -> dict:
    """Return {duration, width, height, fps} for a video file via ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate,duration",
                "-of", "json", str(path),
            ],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        s = data["streams"][0]
        num, den = s["r_frame_rate"].split("/")
        fps = float(num) / float(den)
        return {
            "duration": float(s.get("duration", 0)),
            "width": int(s["width"]),
            "height": int(s["height"]),
            "fps": round(fps, 3),
        }
    except Exception:
        return {"duration": 0.0, "width": 0, "height": 0, "fps": 0.0}


def _parse_filename(filename: str) -> tuple:
    """
    Parse source and topic_cluster from filename.
    pexels_12345_nosleep.mp4 → ("pexels", "nosleep")
    pixabay_88_dog_fun.mp4  → ("pixabay", "dog_fun")
    other.mp4               → ("unknown", "unknown")
    """
    m = re.match(r"^(pexels|pixabay)_\d+_(.+)\.mp4$", filename, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)
    return "unknown", "unknown"


def scan_footage_dir(footage_dir: Path) -> list:
    """
    Scan a directory for .mp4 files and return a list of clip dicts.

    Each dict: filename, path, source, topic_cluster, duration_secs,
               width, height, fps
    """
    clips = []
    for f in sorted(footage_dir.glob("*.mp4")):
        source, topic = _parse_filename(f.name)
        probe = _probe_clip(f)
        clips.append({
            "filename": f.name,
            "path": str(f),
            "source": source,
            "topic_cluster": topic,
            "duration_secs": probe["duration"],
            "width": probe["width"],
            "height": probe["height"],
            "fps": probe["fps"],
        })
    return clips


def build_footage_index(footage_dir: Path, index_path: Path) -> list:
    """
    Scan footage_dir, write JSON index to index_path, return clip list.
    Call this once after downloading new clips.
    """
    clips = scan_footage_dir(footage_dir)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(clips, indent=2), encoding="utf-8")
    return clips


def get_clips_for_channel(channel_config) -> list:
    """
    Return all clips in the channel's footage_dir.
    Reads footage_dir from channel settings.json.
    Falls back to scanning live if index doesn't exist yet.
    """
    settings = json.loads((channel_config.channel_dir / "settings.json").read_text())
    footage_dir_str = settings.get("footage_dir", "dog_footage")
    footage_dir = (Path(footage_dir_str) if Path(footage_dir_str).is_absolute()
                   else Path(footage_dir_str))
    if not footage_dir.exists():
        return []
    index_path = footage_dir / FOOTAGE_DB_FILE
    if index_path.exists():
        return json.loads(index_path.read_text())
    return scan_footage_dir(footage_dir)
