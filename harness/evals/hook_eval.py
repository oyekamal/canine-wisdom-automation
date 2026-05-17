from anthropic import Anthropic
from harness.evals.base import EvalResult, _parse_llm_score

THRESHOLD = 7.0
EVAL_NAME = "hook_eval"

PROMPT = """\
You are a YouTube Shorts expert evaluating the hook strength of a dog-facts video.
The hook is the FIRST sentence of the script — it must create instant curiosity or emotion.

Rate this hook from 0–10, where:
- 0–4: weak (generic, boring, no surprise)
- 5–6: average (mild interest but forgettable)
- 7–8: good (creates clear curiosity or emotion)
- 9–10: excellent (stops the scroll immediately)

Hook to evaluate:
{hook}

Respond ONLY with valid JSON, no markdown:
{{"score": <float 0-10>, "reasoning": "<one sentence>"}}"""


def hook_eval(hook_text: str) -> EvalResult:
    """Score the first-sentence hook. Threshold: 7/10."""
    client = Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": PROMPT.format(hook=hook_text)}],
    )
    if not msg.content or msg.content[0].type != "text":
        raise ValueError(f"{EVAL_NAME}: unexpected response content: {msg.content}")
    score, reasoning = _parse_llm_score(msg.content[0].text, EVAL_NAME)
    return EvalResult(eval_name=EVAL_NAME, score=score, threshold=THRESHOLD, reasoning=reasoning)
