from pathlib import Path


def test_concat_encode_flags_include_no_bframes():
    """-bf 0 must be in _concat_clips to prevent B-frame freeze."""
    src = Path("build_video.py").read_text()
    assert '"-bf", "0"' in src, "build_video.py must pass -bf 0 to ffmpeg in _concat_clips"


def test_concat_encode_flags_include_cfr():
    """-vsync cfr must be in _concat_clips for constant frame rate."""
    src = Path("build_video.py").read_text()
    assert '"-vsync", "cfr"' in src, "build_video.py must pass -vsync cfr to ffmpeg in _concat_clips"


def test_concat_encode_flags_force_30fps():
    """-r 30 must appear at least twice in _concat_clips (looped + normal path)."""
    src = Path("build_video.py").read_text()
    assert src.count('"-r", "30"') >= 2, \
        "build_video.py must pass -r 30 at least twice in _concat_clips"
