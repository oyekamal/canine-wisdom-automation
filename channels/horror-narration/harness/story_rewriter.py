"""
Rewrite a Reddit horror story into an original narration script using Claude.
Includes voice selection based on story mood.
"""
import json
import os
import re
import anthropic


VOICE_MAP = {
    # mood → (short_voice_key, long_voice_key)
    "dread":      ("short_creepy",       "long_form_narrator"),
    "eerie":      ("short_creepy",       "long_form_narrator"),
    "intense":    ("intense",            "intense"),
    "mysterious": ("paranormal_female",  "paranormal_female"),
}
DEFAULT_VOICE_KEYS = ("short_creepy", "long_form_narrator")

# Words that signal sensory-lead angle
_SENSORY_WORDS = {"heard", "smell", "smelled", "breath", "breathing", "cold", "warm",
                  "felt", "sound", "noise", "touch", "tasted", "saw", "light", "dark"}
# Words that signal action-lead angle
_ACTION_WORDS = {"ran", "running", "chased", "grabbed", "dragged", "escaped",
                 "trapped", "locked", "broke", "slammed", "hit", "blocked"}


def _detect_emotional_angle(story: dict) -> str:
    """
    Detect the strongest emotional angle for this story's source material.
    Returns: "sensory" | "action" | "delayed-answer"
    """
    words = set(re.findall(r"[a-z']+", story["text"].lower()))
    sensory_count = len(words & _SENSORY_WORDS)
    action_count = len(words & _ACTION_WORDS)
    if sensory_count >= action_count and sensory_count >= 2:
        return "sensory"
    if action_count >= 2:
        return "action"
    return "delayed-answer"


_ANGLE_GUIDANCE = {
    "sensory": (
        "The source story is SENSORY-RICH. Lead the hook with a specific physical sensation: "
        "a sound, smell, temperature, or texture. The sensory detail is the delayed-answer — "
        "name the sensation before naming the threat."
    ),
    "action": (
        "The source story is ACTION-DRIVEN. Lead with the moment of immediate danger or escape. "
        "Use the delayed-answer technique: describe the action before naming what caused it. "
        "'I ran' before 'I saw what was behind me.'"
    ),
    "delayed-answer": (
        "The source story has no dominant sensory or action signal. Use the delayed-answer hook: "
        "name an impossibility or wrongness without yet naming the full situation. "
        "'There's never been a second door in this hallway.' Let the reader ask why."
    ),
}


def pick_voice(mood: str, target: str, voices_config: dict) -> str:
    short_key, long_key = VOICE_MAP.get(mood, DEFAULT_VOICE_KEYS)
    key = short_key if target == "short" else long_key
    return voices_config.get(key, voices_config.get("long_form_narrator", ""))


def _build_rewrite_prompt(story: dict, target: str) -> str:
    word_target = "60-90 words" if target == "short" else "800-1400 words"
    angle = _detect_emotional_angle(story)
    angle_text = _ANGLE_GUIDANCE[angle]

    return (
        f"Rewrite the following Reddit story as an original horror narration script.\n"
        f"Target format: {target} ({word_target}).\n"
        f"Source: posted by u/{story['author']} on r/{story['subreddit']}\n"
        f"Original URL: {story['url']}\n\n"
        f"EMOTIONAL BEAT GUIDANCE for this story:\n"
        f"Hook angle: {angle_text}\n"
        f"Ending requirement: End on a HIGH-AROUSAL state. Do NOT end on sadness or calm dread alone. "
        f"The final image must be active and unresolved — something still happening, still present, "
        f"still watching. The reader must feel energized to send this to someone, not sit quietly.\n\n"
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
    import time
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY") or _load_api_key())
    user_content = _build_rewrite_prompt(story, target)

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=prompt_text,
                messages=[{"role": "user", "content": user_content}],
            )
            raw = message.content[0].text.strip()
            if not raw:
                raise json.JSONDecodeError("Empty response", "", 0)
            result = json.loads(raw)
            break
        except json.JSONDecodeError:
            if attempt < 2:
                time.sleep(3)
                continue
            raise RuntimeError(f"Claude returned empty/invalid JSON after 3 attempts for story {story['id']}")

    if result.get("error") == "policy":
        raise ValueError(f"Story declined by policy filter: {story['id']}")

    return result


def _load_api_key() -> str:
    from config import load_config
    return load_config()["anthropic_api_key"]
