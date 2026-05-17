from anthropic import Anthropic
from harness.evals.base import EvalResult, _parse_llm_score

THRESHOLD = 7.0
EVAL_NAME = "script_eval"

PROMPT = """\
You are a YouTube Shorts expert evaluating a dog-facts script.

Score the script 0–10 across three dimensions, then give a single combined score:
- Factual accuracy (does it sound credible, not invented?)
- Novelty (is this topic fresh vs these recent topics: {recent_topics})
- Pacing (is it energetic, conversational, under 60 words?)

Script:
{script}

Respond ONLY with valid JSON, no markdown:
{{"score": <float 0-10>, "reasoning": "<one sentence covering all three>"}}"""


def script_eval(script_text: str, recent_topics: list) -> EvalResult:
    """Score full script for accuracy, novelty, and pacing. Threshold: 7/10."""
    client = Anthropic()
    topics_str = ", ".join(recent_topics) if recent_topics else "none"
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": PROMPT.format(
            script=script_text, recent_topics=topics_str
        )}],
    )
    score, reasoning = _parse_llm_score(msg.content[0].text, EVAL_NAME)
    return EvalResult(eval_name=EVAL_NAME, score=score, threshold=THRESHOLD, reasoning=reasoning)
