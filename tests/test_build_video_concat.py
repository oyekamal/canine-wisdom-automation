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
    """All assigned durations must be positive."""
    from build_video import _assign_cut_durations

    durations = _assign_cut_durations(12, 30.0)
    assert all(d > 0 for d in durations)
