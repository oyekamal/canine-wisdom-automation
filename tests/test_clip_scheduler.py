import json
import math
from pathlib import Path
import pytest


def test_new_clips_picked_before_used(tmp_path):
    """Clips with no usage entry are treated as never used and picked first."""
    from clip_scheduler import get_clips_for_video

    clips = [tmp_path / f"clip_{i}.mp4" for i in range(4)]
    for c in clips:
        c.touch()

    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "clip_usage": {
            "clip_2.mp4": "2026-01-01T00:00:00",
            "clip_3.mp4": "2026-01-02T00:00:00",
        }
    }))

    result = get_clips_for_video(tmp_path, audio_duration=5.0, state_path=state_path)
    names = [r.name for r in result]
    assert names[0] in ("clip_0.mp4", "clip_1.mp4")
    assert names[1] in ("clip_0.mp4", "clip_1.mp4")


def test_state_updated_after_selection(tmp_path):
    """After get_clips_for_video(), selected clips have updated timestamps in state."""
    from clip_scheduler import get_clips_for_video

    clips = [tmp_path / f"clip_{i}.mp4" for i in range(3)]
    for c in clips:
        c.touch()

    state_path = tmp_path / "state.json"
    state_path.write_text("{}")

    result = get_clips_for_video(tmp_path, audio_duration=5.0, state_path=state_path)
    state = json.loads(state_path.read_text())
    for clip in result:
        assert clip.name in state.get("clip_usage", {}), f"{clip.name} not updated in state"


def test_wraps_when_fewer_clips_than_needed(tmp_path):
    """With 3 clips and n_clips=8 needed, returns 8 paths (some repeated)."""
    from clip_scheduler import get_clips_for_video, _CUT_DURATION_AVG

    clips = [tmp_path / f"clip_{i}.mp4" for i in range(3)]
    for c in clips:
        c.touch()

    state_path = tmp_path / "state.json"
    state_path.write_text("{}")

    result = get_clips_for_video(tmp_path, audio_duration=12.0, state_path=state_path)
    assert len(result) == math.ceil(12.0 / _CUT_DURATION_AVG)


def test_oldest_picked_first(tmp_path):
    """Clip with older timestamp is picked before newer one."""
    from clip_scheduler import get_clips_for_video

    clips = [tmp_path / f"clip_{i}.mp4" for i in range(2)]
    for c in clips:
        c.touch()

    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "clip_usage": {
            "clip_0.mp4": "2026-05-01T00:00:00",
            "clip_1.mp4": "2026-01-01T00:00:00",  # older — should be picked first
        }
    }))

    result = get_clips_for_video(tmp_path, audio_duration=5.0, state_path=state_path)
    assert result[0].name == "clip_1.mp4"


def test_footage_index_json_excluded_from_clips(tmp_path):
    """footage_index.json in footage dir is not treated as a video clip."""
    from clip_scheduler import get_clips_for_video

    (tmp_path / "clip_0.mp4").touch()
    (tmp_path / "footage_index.json").write_text("{}")

    state_path = tmp_path / "state.json"
    state_path.write_text("{}")

    result = get_clips_for_video(tmp_path, audio_duration=3.0, state_path=state_path)
    names = [r.name for r in result]
    assert "footage_index.json" not in names
    assert "clip_0.mp4" in names


def test_per_channel_state_isolation(tmp_path):
    """Two channels with separate state_paths have independent LRU rotation."""
    from clip_scheduler import get_clips_for_video

    # Shared footage dir (simulate same clip in two channels)
    footage = tmp_path / "footage"
    footage.mkdir()
    (footage / "clip_0.mp4").touch()
    (footage / "clip_1.mp4").touch()

    state_dog = tmp_path / "dog_state.json"
    state_horror = tmp_path / "horror_state.json"

    # Dog channel has used clip_0 recently
    state_dog.write_text(json.dumps({"clip_usage": {"clip_0.mp4": "2026-05-01T00:00:00"}}))
    # Horror channel has used clip_1 recently
    state_horror.write_text(json.dumps({"clip_usage": {"clip_1.mp4": "2026-05-01T00:00:00"}}))

    dog_result = get_clips_for_video(footage, audio_duration=3.0, state_path=state_dog)
    horror_result = get_clips_for_video(footage, audio_duration=3.0, state_path=state_horror)

    # Dog picks clip_1 (less recently used by dog)
    assert dog_result[0].name == "clip_1.mp4"
    # Horror picks clip_0 (less recently used by horror)
    assert horror_result[0].name == "clip_0.mp4"
