"""
Clip scheduler: least-recently-used clip rotation across pipeline runs.

State stored per-channel in channels/<slug>/data/state.json under key "clip_usage":
    {"filename.mp4": "2026-05-22T09:41:41", ...}

Each channel has its own separate clip usage state so dog and horror channels
never interfere with each other's LRU rotation.

Clips not present in state are treated as never used (sorted before any used clip).
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from harness.storage import lock_state, STATE_PATH


_NEVER_USED = "0000-00-00T00:00:00"
_CUT_DURATION_AVG = 1.5  # seconds per clip segment


def get_clips_for_video(
    footage_dir: Path,
    audio_duration: float,
    cut_duration: float = None,
    state_path: Path = None,
) -> List[Path]:
    """
    Select clips for one video using LRU rotation tracked in per-channel state.

    Args:
        footage_dir: Directory containing .mp4 / .mov clips.
        audio_duration: Total audio duration in seconds.
        cut_duration: Seconds per clip (overrides default 1.5s).
        state_path: Path to the channel's state.json. Defaults to global state.

    Returns:
        Ordered list of clip Paths (oldest-used first). May repeat clips if
        fewer clips exist than needed.
    """
    video_extensions = {".mp4", ".mov"}
    available = sorted(
        [p for p in footage_dir.iterdir()
         if p.is_file() and p.suffix.lower() in video_extensions
         and p.name != "footage_index.json"],  # exclude index file
        key=lambda p: p.name,
    )
    if not available:
        raise FileNotFoundError(f"No video clips found in {footage_dir}")

    avg = cut_duration if cut_duration is not None else _CUT_DURATION_AVG
    n_clips = max(1, math.ceil(audio_duration / avg))

    # Use per-channel state if provided, else global state
    effective_state_path = state_path if state_path is not None else STATE_PATH

    import fcntl
    effective_state_path.parent.mkdir(parents=True, exist_ok=True)
    if not effective_state_path.exists():
        effective_state_path.write_text("{}", encoding="utf-8")

    lock_file = effective_state_path.with_suffix(".lock")
    with open(lock_file, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            state = json.loads(effective_state_path.read_text(encoding="utf-8"))
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
        finally:
            tmp = effective_state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
            tmp.replace(effective_state_path)
            fcntl.flock(lf, fcntl.LOCK_UN)

    return selected
