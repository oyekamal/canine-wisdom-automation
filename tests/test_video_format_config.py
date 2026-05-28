from config import VideoFormat, LONG_VIDEO_WIDTH, LONG_VIDEO_HEIGHT, VIDEO_WIDTH, VIDEO_HEIGHT


def test_short_format_values():
    assert VideoFormat.SHORT.value == "short"


def test_long_format_values():
    assert VideoFormat.LONG.value == "long"


def test_short_resolution_unchanged():
    assert VIDEO_WIDTH == 1080
    assert VIDEO_HEIGHT == 1920


def test_long_resolution():
    assert LONG_VIDEO_WIDTH == 1920
    assert LONG_VIDEO_HEIGHT == 1080
