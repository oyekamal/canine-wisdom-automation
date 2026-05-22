"""
Clip scheduler: least-recently-used clip rotation across pipeline runs.

State stored in harness/data/state.json under key "clip_usage":
    {"filename.mp4": "2026-05-22T09:41:41", ...}

Clips not present in state are treated as never used (sorted before any used clip).
"""

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from harness.storage import lock_state


_NEVER_USED = "0000-00-00T00:00:00"
_CUT_DURATION_AVG = 2.5  # seconds per clip segment


def get_clips_for_video(footage_dir: Path, audio_duration: float) -> List[Path]:
    """
    Select clips for one video using LRU rotation tracked in harness state.

    Args:
        footage_dir: Directory containing .mp4 / .mov clips.
        audio_duration: Total audio duration in seconds.

    Returns:
        Ordered list of clip Paths (oldest-used first). May repeat clips if
        fewer clips exist than needed.
    """
    video_extensions = {".mp4", ".mov"}
    available = sorted(
        [p for p in footage_dir.iterdir() if p.is_file() and p.suffix.lower() in video_extensions],
        key=lambda p: p.name,
    )
    if not available:
        raise FileNotFoundError(f"No video clips found in {footage_dir}")

    n_clips = math.ceil(audio_duration / _CUT_DURATION_AVG)

    with lock_state() as state:
        usage = state.setdefault("clip_usage", {})

        def sort_key(p):
            return usage.get(p.name, _NEVER_USED)

        sorted_clips = sorted(available, key=sort_key)

        selected = []
        for i in range(n_clips):
            selected.append(sorted_clips[i % len(sorted_clips)])

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        for clip in selected:
            usage[clip.name] = now

    return selected
