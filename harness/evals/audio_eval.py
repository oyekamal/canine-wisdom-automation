import subprocess
from pathlib import Path

from harness.evals.base import EvalResult

EVAL_NAME = "audio_eval"
MIN_DURATION = 10.0
MAX_DURATION = 90.0


def audio_eval(audio_path: Path) -> EvalResult:
    """Deterministic check: file exists, duration 10–90s via ffprobe."""
    audio_path = Path(audio_path)

    if not audio_path.exists():
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning=f"Audio file not found: {audio_path}"
        )

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(audio_path)],
            capture_output=True, text=True, timeout=15
        )
        duration = float(result.stdout.strip())
    except Exception as e:
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning=f"ffprobe failed: {e}"
        )

    if duration < MIN_DURATION:
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning=f"Audio too short: {duration:.1f}s (min {MIN_DURATION}s)"
        )

    if duration > MAX_DURATION:
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning=f"Audio too long: {duration:.1f}s (max {MAX_DURATION}s)"
        )

    return EvalResult(
        eval_name=EVAL_NAME, score=10.0, threshold=1.0,
        reasoning=f"Audio OK: {duration:.1f}s"
    )
