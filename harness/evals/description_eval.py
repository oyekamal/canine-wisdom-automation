from anthropic import Anthropic
from harness.evals.base import EvalResult, _parse_llm_score

THRESHOLD = 7.0
EVAL_NAME = "description_eval"

PROMPT = """\
You are a YouTube SEO expert evaluating a Shorts video description.

Score 0–10 based on:
- Keyword coverage (does it include relevant dog-facts keywords?)
- CTA presence (does it ask viewers to follow/subscribe?)
- Length (50–300 chars is ideal for Shorts)
- Hashtag quality (>=5 relevant hashtags?)

Description:
{description}

Respond ONLY with valid JSON, no markdown:
{{"score": <float 0-10>, "reasoning": "<one sentence>"}}"""


def description_eval(description: str) -> EvalResult:
    """Score the video description for SEO quality. Threshold: 7/10."""
    client = Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": PROMPT.format(description=description)}],
    )
    score, reasoning = _parse_llm_score(msg.content[0].text, EVAL_NAME)
    return EvalResult(eval_name=EVAL_NAME, score=score, threshold=THRESHOLD, reasoning=reasoning)
