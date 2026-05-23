import math
from pathlib import Path
from unittest.mock import MagicMock
import pytest
import contextlib


FOOTAGE_DIR = Path("/fake/footage")


def test_new_clips_picked_before_used(tmp_path, monkeypatch):
    """Clips with no usage entry are treated as never used and picked first."""
    from clip_scheduler import get_clips_for_video

    clips = [tmp_path / f"clip_{i}.mp4" for i in range(4)]
    for c in clips:
        c.touch()

    state = {"clip_usage": {"clip_2.mp4": "2026-01-01T00:00:00", "clip_3.mp4": "2026-01-02T00:00:00"}}

    @contextlib.contextmanager
    def fake_lock_state():
        yield state

    monkeypatch.setattr("clip_scheduler.lock_state", fake_lock_state)

    result = get_clips_for_video(tmp_path, audio_duration=5.0)
    names = [r.name for r in result]
    assert names[0] in ("clip_0.mp4", "clip_1.mp4")
    assert names[1] in ("clip_0.mp4", "clip_1.mp4")


def test_state_updated_after_selection(tmp_path, monkeypatch):
    """After get_clips_for_video(), selected clips have updated timestamps in state."""
    from clip_scheduler import get_clips_for_video

    clips = [tmp_path / f"clip_{i}.mp4" for i in range(3)]
    for c in clips:
        c.touch()

    state = {}

    @contextlib.contextmanager
    def fake_lock_state():
        yield state

    monkeypatch.setattr("clip_scheduler.lock_state", fake_lock_state)

    result = get_clips_for_video(tmp_path, audio_duration=5.0)
    for clip in result:
        assert clip.name in state.get("clip_usage", {}), f"{clip.name} not updated in state"


def test_wraps_when_fewer_clips_than_needed(tmp_path, monkeypatch):
    """With 3 clips and n_clips=5 needed, returns 5 paths (some repeated)."""
    from clip_scheduler import get_clips_for_video

    clips = [tmp_path / f"clip_{i}.mp4" for i in range(3)]
    for c in clips:
        c.touch()

    state = {}

    @contextlib.contextmanager
    def fake_lock_state():
        yield state

    monkeypatch.setattr("clip_scheduler.lock_state", fake_lock_state)

    # audio_duration=12.0 → n_clips = ceil(12.0/1.5) = 8 (cut duration avg is 1.5s)
    result = get_clips_for_video(tmp_path, audio_duration=12.0)
    from clip_scheduler import _CUT_DURATION_AVG
    assert len(result) == math.ceil(12.0 / _CUT_DURATION_AVG)


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

    @contextlib.contextmanager
    def fake_lock_state():
        yield state

    monkeypatch.setattr("clip_scheduler.lock_state", fake_lock_state)

    result = get_clips_for_video(tmp_path, audio_duration=5.0)
    assert result[0].name == "clip_1.mp4"
