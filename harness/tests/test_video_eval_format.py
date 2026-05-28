import inspect
from harness.evals.video_eval import video_eval
from config import VideoFormat


def test_video_eval_accepts_fmt_param():
    """video_eval must accept an optional fmt keyword argument."""
    sig = inspect.signature(video_eval)
    assert "fmt" in sig.parameters, "video_eval must have a fmt parameter"


def test_video_eval_default_fmt_is_short():
    """Default fmt must be SHORT so existing callers are unaffected."""
    sig = inspect.signature(video_eval)
    param = sig.parameters["fmt"]
    assert param.default == VideoFormat.SHORT
