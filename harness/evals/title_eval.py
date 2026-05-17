from anthropic import Anthropic
from harness.evals.base import EvalResult, _parse_llm_score

THRESHOLD = 7.0
EVAL_NAME = "title_eval"

BASE_PROMPT = """\
You are a YouTube Shorts CTR expert evaluating a video title for a dog-facts channel.

{learnings_context}

Score the title 0–10 where:
- 0–4: generic, no click-bait, too long or vague
- 5–6: okay but forgettable
- 7–8: creates curiosity, under 60 chars, matches a proven formula
- 9–10: scroll-stopper, matches a top formula with strong emotion/numbers

Title to evaluate: {title}

Respond ONLY with valid JSON, no markdown:
{{"score": <float 0-10>, "reasoning": "<one sentence>"}}"""


def _build_learnings_context() -> str:
    try:
        from harness.tools.learnings import get_top_title_formulas
        formulas = get_top_title_formulas(min_confidence="low", n=3)
        if not formulas:
            return ""
        lines = ["Top-performing title formulas for this channel:"]
        for i, f in enumerate(formulas, 1):
            conf = f.get("confidence", "low")
            ctr = f.get("avg_ctr", 0)
            n = f.get("sample_size", 0)
            lines.append(f'{i}. "{f["formula"]}" — {ctr:.1%} CTR ({n} samples, {conf} confidence)')
        return "\n".join(lines)
    except Exception:
        return ""


def title_eval(title: str) -> EvalResult:
    """Score the video title for CTR potential. Threshold: 7/10. Uses learnings context if available."""
    context = _build_learnings_context()
    prompt = BASE_PROMPT.format(
        learnings_context=context if context else "(No learnings data yet — score on general quality)",
        title=title,
    )
    client = Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    if not msg.content or msg.content[0].type != "text":
        raise ValueError(f"{EVAL_NAME}: unexpected response content: {msg.content}")
    score, reasoning = _parse_llm_score(msg.content[0].text, EVAL_NAME)
    return EvalResult(eval_name=EVAL_NAME, score=score, threshold=THRESHOLD, reasoning=reasoning)
