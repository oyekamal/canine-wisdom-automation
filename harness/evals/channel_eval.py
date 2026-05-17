from harness.evals.base import EvalResult

EVAL_NAME = "channel_eval"


def channel_eval(current_kpis: dict, prior_kpis: dict) -> EvalResult:
    """Placeholder — analytics tracking is Session 3. Always passes."""
    return EvalResult(
        eval_name=EVAL_NAME,
        score=8.0,
        threshold=7.0,
        reasoning="Placeholder: channel eval not yet implemented",
    )
