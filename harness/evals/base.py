import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from harness.storage import atomic_write, DATA_DIR


@dataclass
class EvalResult:
    eval_name: str
    score: float
    threshold: float
    reasoning: str
    passed: bool = field(init=False)

    def __post_init__(self):
        self.passed = self.score >= self.threshold


def save_eval_result(result: EvalResult, video_id: str) -> None:
    """Persist eval result to data/eval_runs/{date}/{video_id}/{eval_name}.json."""
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    out_dir = DATA_DIR / "eval_runs" / date_str / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "eval": result.eval_name,
        "video_id": video_id,
        "run_at": now.isoformat(),
        "score": result.score,
        "passed": result.passed,
        "threshold": result.threshold,
        "reasoning": result.reasoning,
    }
    atomic_write(out_dir / f"{result.eval_name}.json", record)


def _parse_llm_score(text: str, eval_name: str) -> tuple[float, str]:
    """Extract score and reasoning from Claude JSON response."""
    try:
        data = json.loads(text)
        return float(data["score"]), str(data.get("reasoning", ""))
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        raise ValueError(f"{eval_name}: failed to parse LLM response: {e}\nRaw: {text}")
