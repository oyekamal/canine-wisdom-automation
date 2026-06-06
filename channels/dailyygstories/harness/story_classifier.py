"""
Claude-powered story type classifier for dailyygstories.

Given a story candidate (title + text snippet), asks Claude to decide:
  - story_type: one of 7 types (true_crime, paranormal, creature_encounter, etc.)
  - format: "short" | "long"

Falls back gracefully to (paranormal, short/long based on word count) on any failure.
Never raises — always returns a valid dict.
"""
import json
import os

import anthropic

VALID_TYPES = {
    "true_crime", "paranormal", "creature_encounter",
    "unsolved_mystery", "real_news_horror", "two_sentence_horror", "night_shift_stories"
}
VALID_FORMATS = {"short", "long"}

LONG_FORM_TYPES = {"true_crime", "unsolved_mystery", "real_news_horror"}
SHORT_FORM_TYPES = {"two_sentence_horror", "creature_encounter"}


def classify_story(candidate: dict) -> dict:
    """
    Classify a story candidate into type and format using Claude.

    Args:
        candidate: dict with keys 'title' and 'text' (the story snippet)

    Returns:
        dict with keys:
        - story_type: str, one of VALID_TYPES
        - format: str, one of VALID_FORMATS
        - reasoning: str, Claude's reasoning (may be empty on fallback)

    Never raises. Returns fallback on any error.
    """
    title = candidate.get("title", "")
    text_snippet = candidate.get("text", "")[:600]

    prompt = (
        f"Classify this story for a horror YouTube channel.\n\n"
        f"Title: {title}\n"
        f"Text snippet: {text_snippet}\n\n"
        f"Pick ONE story_type from: true_crime | paranormal | creature_encounter | "
        f"unsolved_mystery | real_news_horror | two_sentence_horror | night_shift_stories\n\n"
        f"Pick ONE format: short (under 90 words, YouTube Short) OR long (700-1400 words, 8-15min video).\n\n"
        f"Rules:\n"
        f"- true_crime, unsolved_mystery, real_news_horror → prefer long\n"
        f"- two_sentence_horror, creature_encounter → always short\n"
        f"- paranormal, night_shift_stories → short if text < 400 words, else long\n\n"
        f"Return ONLY JSON: {{\"story_type\": \"...\", \"format\": \"...\", \"reasoning\": \"one sentence\"}}"
    )

    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            from config import load_config
            api_key = load_config()["anthropic_api_key"]

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        result = json.loads(raw)

        story_type = result.get("story_type", "paranormal")
        fmt = result.get("format", "short")

        # Sanitize to valid values
        if story_type not in VALID_TYPES:
            story_type = "paranormal"
        if fmt not in VALID_FORMATS:
            fmt = "short"

        return {
            "story_type": story_type,
            "format": fmt,
            "reasoning": result.get("reasoning", "")
        }

    except Exception as e:
        print(f"[story_classifier] classify failed ({e}) — using fallback")
        word_count = len(candidate.get("text", "").split())
        fallback_fmt = "long" if word_count >= 700 else "short"
        return {
            "story_type": "paranormal",
            "format": fallback_fmt,
            "reasoning": "fallback"
        }
