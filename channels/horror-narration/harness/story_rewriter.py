"""
Rewrite a Reddit horror story into an original narration script using Claude.
Includes voice selection based on story mood.
"""
import json
import os
import anthropic


VOICE_MAP = {
    # mood → (short_voice_key, long_voice_key)
    "dread":      ("short_creepy",       "long_form_narrator"),
    "eerie":      ("short_creepy",       "long_form_narrator"),
    "intense":    ("intense",            "intense"),
    "mysterious": ("paranormal_female",  "paranormal_female"),
}
DEFAULT_VOICE_KEYS = ("short_creepy", "long_form_narrator")


def pick_voice(mood: str, target: str, voices_config: dict) -> str:
    """
    Select the best ElevenLabs voice ID for a given mood and format.

    Args:
        mood: one of "dread", "eerie", "intense", "mysterious"
        target: "short" or "long"
        voices_config: dict mapping key names to voice IDs (from settings.json)

    Returns:
        ElevenLabs voice ID string
    """
    short_key, long_key = VOICE_MAP.get(mood, DEFAULT_VOICE_KEYS)
    key = short_key if target == "short" else long_key
    return voices_config.get(key, voices_config.get("long_form_narrator", ""))


def _build_rewrite_prompt(story: dict, target: str) -> str:
    word_target = "60-90 words" if target == "short" else "800-1400 words"
    return (
        f"Rewrite the following Reddit story as an original horror narration script.\n"
        f"Target format: {target} ({word_target}).\n"
        f"Source: posted by u/{story['author']} on r/{story['subreddit']}\n"
        f"Original URL: {story['url']}\n\n"
        f"--- STORY START ---\n{story['text']}\n--- STORY END ---\n\n"
        f"Respond with a JSON object only. No markdown. No explanation."
    )


def rewrite_story(story: dict, target: str, prompt_text: str) -> dict:
    """
    Send a story to Claude for rewriting.

    Returns dict with keys: script, title, hook_overlay, hashtags,
                            topic_cluster, mood, source_attribution, format

    Raises:
        ValueError: if Claude returns a policy error
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY") or _load_api_key())

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=prompt_text,
        messages=[{"role": "user", "content": _build_rewrite_prompt(story, target)}],
    )

    raw = message.content[0].text.strip()
    result = json.loads(raw)

    if result.get("error") == "policy":
        raise ValueError(f"Story declined by policy filter: {story['id']}")

    return result


def _load_api_key() -> str:
    """Load API key via config as fallback."""
    from config import load_config
    return load_config()["anthropic_api_key"]
