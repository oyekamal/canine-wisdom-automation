"""
Deterministic eval: are learnings.json entries still backed by recent data?
Stale entries (last_seen > 14 days) are downgraded in confidence.
Zero-sample entries older than 30 days are removed.
Passes if learnings has >= 3 medium/high confidence entries combined.
"""
from datetime import datetime, timedelta

from harness.evals.base import EvalResult
from harness.tools.learnings import read_learnings, _write_learnings

EVAL_NAME = "learnings_freshness_eval"
THRESHOLD = 1.0  # hard pass/fail
STALE_DAYS = 14
REMOVE_DAYS = 30
MIN_MEDIUM_HIGH = 3

CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
DEMOTE = {"high": "medium", "medium": "low", "low": "low"}


def learnings_freshness_eval() -> EvalResult:
    """
    Check and maintain learnings.json entry freshness.
    Returns EvalResult: passes if >= MIN_MEDIUM_HIGH entries have medium/high confidence.
    """
    data = read_learnings()
    today = datetime.now()
    stale_cutoff = (today - timedelta(days=STALE_DAYS)).strftime("%Y-%m-%d")
    remove_cutoff = (today - timedelta(days=REMOVE_DAYS)).strftime("%Y-%m-%d")
    changed = False

    def process_entries(entries: list) -> list:
        nonlocal changed
        kept = []
        for e in entries:
            last_seen = e.get("last_seen", "1970-01-01")
            sample_size = e.get("sample_size", 0)
            if sample_size == 0 and last_seen < remove_cutoff:
                changed = True
                continue  # remove
            if last_seen < stale_cutoff:
                old_conf = e.get("confidence", "low")
                new_conf = DEMOTE.get(old_conf, "low")
                if new_conf != old_conf:
                    e = {**e, "confidence": new_conf}
                    changed = True
            kept.append(e)
        return kept

    data["hook_patterns"] = process_entries(data.get("hook_patterns", []))
    data["title_formulas"] = process_entries(data.get("title_formulas", []))

    if changed:
        _write_learnings(data)

    all_entries = data.get("hook_patterns", []) + data.get("title_formulas", [])
    medium_high = sum(
        1 for e in all_entries
        if CONFIDENCE_ORDER.get(e.get("confidence", "low"), 0) >= 1
    )

    if medium_high >= MIN_MEDIUM_HIGH:
        return EvalResult(
            eval_name=EVAL_NAME, score=10.0, threshold=THRESHOLD,
            reasoning=f"Learnings healthy: {medium_high} medium/high confidence entries"
        )
    return EvalResult(
        eval_name=EVAL_NAME, score=0.0, threshold=THRESHOLD,
        reasoning=f"Learnings sparse: only {medium_high} medium/high entries (need {MIN_MEDIUM_HIGH})"
    )
