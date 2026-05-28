import json
import subprocess
from pathlib import Path

from harness.evals.base import EvalResult
from config import VideoFormat, LONG_VIDEO_WIDTH, LONG_VIDEO_HEIGHT, VIDEO_WIDTH, VIDEO_HEIGHT

EVAL_NAME = "video_eval"


def video_eval(video_path: Path, fmt=VideoFormat.SHORT) -> EvalResult:
    """Deterministic check: file exists, non-zero size, resolution matches format via ffprobe."""
    EXPECTED_WIDTH = LONG_VIDEO_WIDTH if fmt == VideoFormat.LONG else VIDEO_WIDTH
    EXPECTED_HEIGHT = LONG_VIDEO_HEIGHT if fmt == VideoFormat.LONG else VIDEO_HEIGHT

    video_path = Path(video_path)

    if not video_path.exists():
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning=f"Video file not found: {video_path}"
        )

    if video_path.stat().st_size == 0:
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning="Video file is empty (0 bytes)"
        )

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "json", str(video_path)],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
    except Exception as e:
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning=f"ffprobe failed: {e}"
        )

    if width != EXPECTED_WIDTH or height != EXPECTED_HEIGHT:
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning=f"Wrong resolution: {width}x{height} (expected {EXPECTED_WIDTH}x{EXPECTED_HEIGHT})"
        )

    return EvalResult(
        eval_name=EVAL_NAME, score=10.0, threshold=1.0,
        reasoning=f"Video OK: {width}x{height}"
    )
