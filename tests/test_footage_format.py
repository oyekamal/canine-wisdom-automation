import inspect
from harness.tools.footage import fetch_footage_for_topic
from config import VideoFormat


def test_fetch_footage_accepts_fmt():
    """fetch_footage_for_topic must accept an optional fmt keyword argument."""
    sig = inspect.signature(fetch_footage_for_topic)
    assert "fmt" in sig.parameters, "fetch_footage_for_topic must have a fmt parameter"


def test_fetch_footage_default_fmt_is_short():
    sig = inspect.signature(fetch_footage_for_topic)
    param = sig.parameters["fmt"]
    assert param.default == VideoFormat.SHORT
