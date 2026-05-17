from anthropic import Anthropic
from harness.evals.base import EvalResult, _parse_llm_score

THRESHOLD = 7.0
EVAL_NAME = "hook_eval"

BASE_PROMPT = """\
You are a YouTube Shorts expert evaluating the hook strength of a dog-facts video.
The hook is the FIRST sentence of the script — it must create instant curiosity or emotion.

{learnings_context}

Rate this hook from 0–10, where:
- 0–4: weak (generic, boring, no surprise)
- 5–6: average (mild interest but forgettable)
- 7–8: good (creates clear curiosity or emotion, similar structure to top patterns)
- 9–10: excellent (stops the scroll immediately)

Hook to evaluate:
{hook}

Respond ONLY with valid JSON, no markdown:
{{"score": <float 0-10>, "reasoning": "<one sentence>"}}"""


def _build_learnings_context() -> str:
    try:
        from harness.tools.learnings import get_top_hook_patterns
        patterns = get_top_hook_patterns(min_confidence="low", n=3)
        if not patterns:
            return ""
        lines = ["Top-performing hook patterns for this channel:"]
        for i, p in enumerate(patterns, 1):
            conf = p.get("confidence", "low")
            retention = p.get("avg_3sec_retention_proxy", 0)
            n = p.get("sample_size", 0)
            lines.append(f'{i}. "{p["pattern"]}" — {retention:.0%} retention ({n} samples, {conf} confidence)')
        return "\n".join(lines)
    except Exception:
        return ""


def hook_eval(hook_text: str) -> EvalResult:
    """Score the first-sentence hook. Threshold: 7/10. Uses learnings context if available."""
    context = _build_learnings_context()
    prompt = BASE_PROMPT.format(
        learnings_context=context if context else "(No learnings data yet — score on general quality)",
        hook=hook_text,
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
