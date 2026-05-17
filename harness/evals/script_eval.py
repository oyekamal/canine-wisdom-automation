from anthropic import Anthropic
from harness.evals.base import EvalResult, _parse_llm_score

THRESHOLD = 7.0
EVAL_NAME = "script_eval"

BASE_PROMPT = """\
You are a YouTube Shorts expert evaluating a dog-facts script.

{covered_topics_context}

Score the script 0–10 across three dimensions, then give a single combined score:
- Factual accuracy (does it sound credible, not invented?)
- Novelty (is this topic fresh? penalise heavily if it repeats a covered topic above)
- Pacing (is it energetic, conversational, under 60 words?)

Script:
{script}

Respond ONLY with valid JSON, no markdown:
{{"score": <float 0-10>, "reasoning": "<one sentence covering all three>"}}"""


def _build_covered_context(recent_topics: list) -> str:
    try:
        from harness.tools.learnings import get_covered_topics
        from_learnings = get_covered_topics(days=30)
        all_topics = list(set(recent_topics + from_learnings))
    except Exception:
        all_topics = recent_topics

    if not all_topics:
        return "Topics covered in the last 30 days: none"
    return "Topics covered in the last 30 days (DO NOT repeat): " + ", ".join(all_topics[:20])


def script_eval(script_text: str, recent_topics: list) -> EvalResult:
    """Score full script for accuracy, novelty, and pacing. Threshold: 7/10."""
    covered_context = _build_covered_context(recent_topics)
    prompt = BASE_PROMPT.format(covered_topics_context=covered_context, script=script_text)
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
