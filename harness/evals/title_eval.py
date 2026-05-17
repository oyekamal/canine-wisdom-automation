from anthropic import Anthropic
from harness.evals.base import EvalResult, _parse_llm_score

THRESHOLD = 7.0
EVAL_NAME = "title_eval"

PROMPT = """\
You are a YouTube Shorts CTR expert evaluating a video title for a dog-facts channel.

Score the title 0–10 where:
- 0–4: generic, no click-bait, too long or vague
- 5–6: okay but forgettable
- 7–8: creates curiosity, under 60 chars, emotionally engaging
- 9–10: scroll-stopper, uses numbers/surprise/emotion perfectly

Title: {title}

Respond ONLY with valid JSON, no markdown:
{{"score": <float 0-10>, "reasoning": "<one sentence>"}}"""


def title_eval(title: str) -> EvalResult:
    """Score the video title for CTR potential. Threshold: 7/10."""
    client = Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": PROMPT.format(title=title)}],
    )
    if not msg.content or msg.content[0].type != "text":
        raise ValueError(f"{EVAL_NAME}: unexpected response content: {msg.content}")
    score, reasoning = _parse_llm_score(msg.content[0].text, EVAL_NAME)
    return EvalResult(eval_name=EVAL_NAME, score=score, threshold=THRESHOLD, reasoning=reasoning)
