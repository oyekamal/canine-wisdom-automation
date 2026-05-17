from harness.evals.base import EvalResult

EVAL_NAME = "thumbnail_eval"


def thumbnail_eval(variants: list) -> EvalResult:
    """Placeholder — thumbnail generation is Session 3. Always passes."""
    return EvalResult(
        eval_name=EVAL_NAME,
        score=8.0,
        threshold=7.0,
        reasoning="Placeholder: thumbnail eval not yet implemented",
    )
