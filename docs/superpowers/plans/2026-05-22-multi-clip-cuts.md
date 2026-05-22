# Multi-Clip Fast Cuts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current single-clip video assembly with multi-clip concatenation that cuts every 2–3 seconds, using globally-tracked least-recently-used clip rotation stored in harness state.

**Architecture:** A new `clip_scheduler.py` module handles clip selection and LRU tracking via `harness/storage.py`'s `lock_state()`. `build_video.py` gains a `_concat_clips()` helper that extracts random-duration segments from each selected clip and concatenates them into a single temp video via ffmpeg's concat demuxer. The final encode (scale + ASS subtitles) runs on that concatenated video unchanged.

**Tech Stack:** Python 3, ffmpeg (concat demuxer, `-ss`/`-t`/`-c copy` segment extraction), existing `harness/storage.py` atomic state, existing `build_video.py` encode pipeline.

---

## File Map

| File | Change |
|---|---|
| `clip_scheduler.py` | **New** — `get_clips_for_video()` + LRU state management |
| `build_video.py` | Modify — replace single-clip logic with `_concat_clips()` + `get_clips_for_video()` |
| `tests/test_clip_scheduler.py` | **New** — 4 unit tests |
| `tests/test_build_video_concat.py` | **New** — 2 unit tests for cut duration math |

`utils.py`'s `get_random_dog_clip()` is left in place (other tests may reference it) but is no longer called from `build_video.py`.

---

## Task 1: Create clip_scheduler.py with LRU selection

**Files:**
- Create: `clip_scheduler.py`
- Create: `tests/test_clip_scheduler.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_clip_scheduler.py`:

```python
import json
import math
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# We test get_clips_for_video by mocking lock_state and the filesystem.

FOOTAGE_DIR = Path("/fake/footage")

def _make_clips(names):
    """Return mock Path objects for clip names."""
    clips = []
    for n in names:
        p = MagicMock(spec=Path)
        p.name = n
        p.suffix = ".mp4"
        p.__str__ = lambda self, n=n: f"/fake/footage/{n}"
        clips.append(p)
    return clips


def test_new_clips_picked_before_used(tmp_path, monkeypatch):
    """Clips with no usage entry are treated as never used and picked first."""
    from clip_scheduler import get_clips_for_video

    clips = [tmp_path / f"clip_{i}.mp4" for i in range(4)]
    for c in clips:
        c.touch()

    state = {"clip_usage": {"clip_2.mp4": "2026-01-01T00:00:00", "clip_3.mp4": "2026-01-02T00:00:00"}}

    import contextlib
    @contextlib.contextmanager
    def fake_lock_state():
        yield state

    monkeypatch.setattr("clip_scheduler.lock_state", fake_lock_state)

    result = get_clips_for_video(tmp_path, audio_duration=5.0)
    names = [r.name for r in result]
    # clip_0 and clip_1 have no usage entry → should appear before clip_2 and clip_3
    assert names[0] in ("clip_0.mp4", "clip_1.mp4")
    assert names[1] in ("clip_0.mp4", "clip_1.mp4")


def test_state_updated_after_selection(tmp_path, monkeypatch):
    """After get_clips_for_video(), selected clips have updated timestamps in state."""
    from clip_scheduler import get_clips_for_video

    clips = [tmp_path / f"clip_{i}.mp4" for i in range(3)]
    for c in clips:
        c.touch()

    state = {}

    import contextlib
    @contextlib.contextmanager
    def fake_lock_state():
        yield state

    monkeypatch.setattr("clip_scheduler.lock_state", fake_lock_state)

    result = get_clips_for_video(tmp_path, audio_duration=5.0)
    # All returned clips should now have a timestamp in state
    for clip in result:
        assert clip.name in state.get("clip_usage", {}), f"{clip.name} not updated in state"


def test_wraps_when_fewer_clips_than_needed(tmp_path, monkeypatch):
    """With 3 clips and n_clips=5 needed, returns 5 paths (some repeated)."""
    from clip_scheduler import get_clips_for_video
    import math

    clips = [tmp_path / f"clip_{i}.mp4" for i in range(3)]
    for c in clips:
        c.touch()

    state = {}

    import contextlib
    @contextlib.contextmanager
    def fake_lock_state():
        yield state

    monkeypatch.setattr("clip_scheduler.lock_state", fake_lock_state)

    # audio_duration=12.0 → n_clips = ceil(12.0/2.5) = 5
    result = get_clips_for_video(tmp_path, audio_duration=12.0)
    assert len(result) == math.ceil(12.0 / 2.5)


def test_oldest_picked_first(tmp_path, monkeypatch):
    """Clip with older timestamp is picked before newer one."""
    from clip_scheduler import get_clips_for_video

    clips = [tmp_path / f"clip_{i}.mp4" for i in range(2)]
    for c in clips:
        c.touch()

    state = {
        "clip_usage": {
            "clip_0.mp4": "2026-05-01T00:00:00",
            "clip_1.mp4": "2026-01-01T00:00:00",  # older
        }
    }

    import contextlib
    @contextlib.contextmanager
    def fake_lock_state():
        yield state

    monkeypatch.setattr("clip_scheduler.lock_state", fake_lock_state)

    result = get_clips_for_video(tmp_path, audio_duration=5.0)
    # clip_1 is oldest → should be first
    assert result[0].name == "clip_1.mp4"
```

- [ ] **Step 2: Run tests to confirm ImportError**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
source venv/bin/activate
python -m pytest tests/test_clip_scheduler.py -v
```
Expected: `ImportError: No module named 'clip_scheduler'`

- [ ] **Step 3: Create clip_scheduler.py**

```python
"""
Clip scheduler: least-recently-used clip rotation across pipeline runs.

State is stored in harness/data/state.json under key "clip_usage":
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

        # Sort available clips: never-used (not in usage) first, then by timestamp ascending
        def sort_key(p):
            return usage.get(p.name, _NEVER_USED)

        sorted_clips = sorted(available, key=sort_key)

        # Fill n_clips slots, cycling through sorted_clips if needed
        selected = []
        for i in range(n_clips):
            selected.append(sorted_clips[i % len(sorted_clips)])

        # Mark all selected clips with current timestamp
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        for clip in selected:
            usage[clip.name] = now

    return selected
```

- [ ] **Step 4: Run tests — all 4 must pass**

```bash
python -m pytest tests/test_clip_scheduler.py -v
```
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add clip_scheduler.py tests/test_clip_scheduler.py
git commit -m "feat: add clip_scheduler with LRU rotation via harness state"
```

---

## Task 2: Add cut duration math and concat helper to build_video.py

**Files:**
- Create: `tests/test_build_video_concat.py`
- Modify: `build_video.py` — add `_assign_cut_durations()` and `_concat_clips()`

- [ ] **Step 1: Write failing tests**

Create `tests/test_build_video_concat.py`:

```python
import math
import pytest


def test_cut_durations_sum_to_audio_duration():
    """Given n clips and audio_duration, assigned durations must sum exactly to audio_duration."""
    from build_video import _assign_cut_durations

    audio_duration = 28.3
    n = math.ceil(audio_duration / 2.5)
    durations = _assign_cut_durations(n, audio_duration)

    assert len(durations) == n
    assert sum(durations) == pytest.approx(audio_duration, abs=0.001)


def test_cut_durations_all_positive():
    """All assigned durations must be positive (scaling can't produce zero or negative)."""
    from build_video import _assign_cut_durations

    durations = _assign_cut_durations(12, 30.0)
    assert all(d > 0 for d in durations)
```

- [ ] **Step 2: Run tests to confirm ImportError**

```bash
python -m pytest tests/test_build_video_concat.py -v
```
Expected: `ImportError: cannot import name '_assign_cut_durations'`

- [ ] **Step 3: Add _assign_cut_durations() to build_video.py**

Add this function just before `build_video()` in `build_video.py` (around line 180):

```python
def _assign_cut_durations(n_clips: int, audio_duration: float) -> list:
    """
    Assign a random duration (2.0–3.0s) to each clip, scaled so they sum to audio_duration.

    Args:
        n_clips: Number of clip segments needed.
        audio_duration: Total duration all segments must fill exactly.

    Returns:
        List of float durations, one per clip, summing to audio_duration.
    """
    raw = [random.uniform(2.0, 3.0) for _ in range(n_clips)]
    total = sum(raw)
    return [r * audio_duration / total for r in raw]
```

- [ ] **Step 4: Run tests — both must pass**

```bash
python -m pytest tests/test_build_video_concat.py -v
```
Expected: 2 tests PASS.

- [ ] **Step 5: Add _concat_clips() to build_video.py**

Add this function directly after `_assign_cut_durations()`:

```python
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
    import os
    temp_dir = Path(tempfile.gettempdir())
    durations = _assign_cut_durations(len(clip_paths), audio_duration)

    segment_paths = []
    for i, (clip, dur) in enumerate(zip(clip_paths, durations)):
        clip_dur = HardwareAccelerator.get_video_duration(str(clip))
        seg_out = temp_dir / f"canine_seg_{i}_{clip.stem}.mp4"

        if clip_dur is None or clip_dur < dur:
            # Loop clip to cover assigned duration
            loops = int(dur / (clip_dur or 1)) + 2
            cmd = [
                "ffmpeg", "-stream_loop", str(loops),
                "-i", str(clip),
                "-t", f"{dur:.3f}",
                "-c:v", "copy", "-an", "-y", str(seg_out),
            ]
        else:
            max_start = clip_dur - dur
            start = random.uniform(0, max_start)
            cmd = [
                "ffmpeg",
                "-ss", f"{start:.3f}",
                "-i", str(clip),
                "-t", f"{dur:.3f}",
                "-c:v", "copy", "-an", "-y", str(seg_out),
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

    # Concatenate all segments
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
```

- [ ] **Step 6: Add import for clip_scheduler at top of build_video.py**

In `build_video.py`, add after the existing imports (around line 14):

```python
from clip_scheduler import get_clips_for_video
```

- [ ] **Step 7: Run tests**

```bash
python -m pytest tests/test_build_video_concat.py -v
```
Expected: 2 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add build_video.py tests/test_build_video_concat.py
git commit -m "feat: add _assign_cut_durations and _concat_clips to build_video"
```

---

## Task 3: Wire multi-clip assembly into build_video()

**Files:**
- Modify: `build_video.py:182–228` — replace single-clip block with multi-clip path

- [ ] **Step 1: Read the current single-clip block in build_video()**

The current flow (lines ~207–228) is:

```python
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
```

- [ ] **Step 2: Replace the single-clip block**

Replace everything from the `if clip_path` block through `actual_video_path = optimizer.trim_video_segment(audio_duration)` with:

```python
    voiceover_path = Path("outputs/voiceover.mp3")
    if not voiceover_path.exists():
        raise FileNotFoundError(f"Audio file not found: {voiceover_path}")

    # Detect encoder from any available clip (just needs to read ffmpeg caps)
    all_clips = sorted(dog_footage_dir.iterdir())
    first_clip = next(
        (c for c in all_clips if c.suffix.lower() in {".mp4", ".mov"}), None
    )
    if not first_clip:
        raise FileNotFoundError(f"No clips found in {dog_footage_dir}")
    optimizer = VideoOptimizer(str(first_clip))
    enc_params = optimizer.get_encoding_params()

    if clip_path and Path(clip_path).exists():
        # Topic-matched: single clip, use existing trim logic
        log(f"📹 Using topic-matched clip: {Path(clip_path).name}")
        single_optimizer = VideoOptimizer(clip_path)
        actual_video_path = single_optimizer.trim_video_segment(audio_duration)
        log(f"✂️  Single-clip mode (topic match)")
    else:
        # Multi-clip: LRU rotation + 2-3s cuts
        clips = get_clips_for_video(dog_footage_dir, audio_duration)
        log(f"📹 Multi-clip mode: {len(clips)} cuts from LRU rotation")
        for i, c in enumerate(clips):
            log(f"   [{i+1}] {c.name}")
        actual_video_path = _concat_clips(clips, audio_duration)
        log(f"✂️  Concat complete: {actual_video_path}")
```

- [ ] **Step 3: Verify the full pipeline imports cleanly**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
source venv/bin/activate
python -c "from build_video import build_video, _concat_clips, _assign_cut_durations; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/test_clip_scheduler.py tests/test_build_video_concat.py tests/test_caption_engine.py tests/test_script_length.py tests/test_chars_to_words.py -v
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add build_video.py
git commit -m "feat: wire multi-clip LRU assembly into build_video()"
```

---

## Task 4: Run make_sample.py end-to-end and verify cuts

- [ ] **Step 1: Run the sample generator**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
source venv/bin/activate
python make_sample.py
```

Expected log output includes lines like:
```
📹 Multi-clip mode: 12 cuts from LRU rotation
   [1] pexels_16622195_dog_fun.mp4
   [2] pexels_31546556_dog_fun.mp4
   ...
✂️  Concat complete: /tmp/canine_concat.mp4
✅ SAMPLE READY: outputs/sample_2026-05-22.mp4
```

- [ ] **Step 2: Verify clip_usage state was written**

```bash
python -c "
from harness.storage import atomic_read
from pathlib import Path
state = atomic_read(Path('harness/data/state.json'))
usage = state.get('clip_usage', {})
print(f'Clips tracked: {len(usage)}')
for name, ts in sorted(usage.items()):
    print(f'  {ts}  {name}')
"
```
Expected: list of clip names with today's timestamp.

- [ ] **Step 3: Open the sample video**

Open `outputs/sample_2026-05-22.mp4` and verify:
- Video cuts to a new clip every 2–3 seconds
- Yellow word-by-word captions visible throughout
- Hook overlay text visible in first 1.5 seconds
- Total duration 25–35 seconds

- [ ] **Step 4: Run a second time to verify LRU rotation**

```bash
python make_sample.py
```

Then check state again — the second run should pick different clips (the previously unused ones if any, or the ones not used most recently).

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "chore: verify multi-clip pipeline end-to-end with LRU rotation"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| `get_clips_for_video(footage_dir, audio_duration)` public interface | Task 1 |
| `n_clips = ceil(audio_duration / 2.5)` | Task 1 (scheduler), Task 2 (duration math) |
| LRU via `lock_state()` | Task 1 |
| Never-used clips sorted before used | Task 1 (test + implementation) |
| Wrap/cycle when n_clips > available | Task 1 |
| State key `"clip_usage"` | Task 1 |
| `_assign_cut_durations()` proportional scaling | Task 2 |
| `_concat_clips()` segment extraction + concat demuxer | Task 2 |
| Single-clip path preserved for topic-matched override | Task 3 |
| Multi-clip path used when no topic override | Task 3 |
| End-to-end verification | Task 4 |

**Placeholder scan:** No TBDs, TODOs, or vague steps found.

**Type consistency:** `get_clips_for_video` returns `List[Path]` — consumed by `_concat_clips(clip_paths: list, ...)` which iterates with `.name` and `str(clip)` — consistent. `_assign_cut_durations(n_clips: int, audio_duration: float) -> list` — called inside `_concat_clips` with `len(clip_paths)` — consistent.
