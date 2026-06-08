"""
Script generation module for Canine Wisdom YouTube Shorts Pipeline.

Generates viral dog fact scripts using Claude API.
"""

import json
from pathlib import Path
from anthropic import Anthropic
from config import load_config, ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS
from utils import log, retry_with_backoff


HARDCODED_TOPIC_CLUSTERS = [
    "dog health", "dog behavior", "dog breeds", "dog training",
    "dog history", "dog science", "dog fun"
]


def _build_prompt(channel_config=None) -> str:
    """
    Build the Claude prompt for script generation.

    If channel_config is provided and its prompt_path exists, read and return
    the prompt from that file (full override).

    If channel_config is provided but prompt_path does not exist, substitute
    channel_config.niche and channel_config.topic_clusters into the template.

    If channel_config is None, return the existing hardcoded prompt unchanged
    (learnings context is injected by the caller).
    """
    # Build learnings context (needed for both file-based and inline prompts)
    try:
        from harness.tools.learnings import get_top_hook_patterns, get_top_title_formulas, get_covered_topics
        top_hooks = get_top_hook_patterns(min_confidence="low", n=3)
        top_titles = get_top_title_formulas(min_confidence="low", n=3)
        covered = get_covered_topics(days=30)
        hooks_text = "\n".join(
            f'- "{h["pattern"]}" (retention proxy: {h["avg_3sec_retention_proxy"]:.0%})'
            for h in top_hooks
        ) or "- No data yet"
        titles_text = "\n".join(
            f'- "{t["formula"]}" (CTR: {t["avg_ctr"]:.1%})'
            for t in top_titles
        ) or "- No data yet"
        covered_text = ", ".join(covered[:30]) or "none"
    except Exception:
        hooks_text = "- No data yet"
        titles_text = "- No data yet"
        covered_text = "none"

    # If channel has a prompt file, substitute learnings placeholders into it
    if channel_config is not None and channel_config.prompt_path.exists():
        raw = channel_config.prompt_path.read_text(encoding="utf-8")
        return raw.replace("{hooks_text}", hooks_text) \
                   .replace("{titles_text}", titles_text) \
                   .replace("{covered_text}", covered_text)

    if channel_config is not None:
        niche = channel_config.niche
        clusters = channel_config.topic_clusters
        topic_cluster_values = ", ".join(clusters)
    else:
        niche = "dog channel"
        clusters = HARDCODED_TOPIC_CLUSTERS
        topic_cluster_values = "dog health, dog behavior, dog breeds, dog training, dog history, dog science, dog fun"

    channel_description = f"a {niche}" if channel_config is not None else "a dog channel"

    return f"""You are a viral YouTube Shorts scriptwriter for {channel_description} in 2026.

Top-performing hook patterns (use one):
{hooks_text}

Top-performing title formulas (use one):
{titles_text}

Topics covered in the last 30 days (DO NOT repeat):
{covered_text}

Write a script for a 25–35 second Short. Rules:
1. FIRST SENTENCE = HOOK. It must stop the scroll in under 1.5 seconds. Use urgency, fear, or curiosity directed personally at the viewer.
   REQUIRED hook styles (pick one):
   - Accusation/secret: "YOUR DOG IS HIDING THIS FROM YOU." / "VET WON'T TELL YOU THIS."
   - Challenge: "MOST OWNERS GET THIS COMPLETELY WRONG." / "YOU'VE BEEN DOING THIS WRONG YOUR WHOLE LIFE."
   - Surprising fact with personal stakes: "Your dog's [X] is 40% [worse/better] than you think — and it's your fault."
   NEVER start with: "Did you know", "Have you ever", or any gentle question. Always personal and direct.
2. WORD COUNT: 54–76 words total (25–35 seconds at 130 wpm). Count every word.
3. No filler words. No "amazing" or "incredible". Simple, punchy sentences.
4. Include one stat, number, or comparison (e.g. "3x faster", "9 out of 10 vets").
5. End with exactly: "Follow for daily dog facts!"
6. Suggest one TEXT OVERLAY phrase (3–6 words, ALL CAPS) for the first 1.5 seconds. Must be emotionally charged and owner-directed. Examples: "YOUR DOG IS HIDING THIS", "VET WON'T TELL YOU THIS", "STOP DOING THIS NOW", "YOU'RE HURTING YOUR DOG". Never vague or generic.

Return ONLY valid JSON (no markdown, no extra text):
{{
    "script": "Full script here",
    "title": "Clickbait title under 60 chars",
    "hook_overlay": "BOLD OVERLAY PHRASE IN CAPS",
    "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
    "topic": "2-5 word description",
    "topic_cluster": "one of: {topic_cluster_values}",
    "hook_pattern_used": "the hook pattern template you used",
    "title_formula_used": "the title formula template you used"
}}"""


def generate_script(channel_config=None) -> dict:
    """
    Generate a viral dog fact script using Claude API.

    Process:
    1. Load configuration
    2. Create Anthropic client
    3. Call Claude to generate script with metadata
    4. Write script.txt and metadata.json to outputs/
    5. Return metadata dictionary

    Returns:
        Dictionary with keys: script, title, hashtags, topic, topic_cluster,
        hook_pattern_used, title_formula_used

    Raises:
        ValueError: If JSON response is invalid or missing required fields.
        ConfigError: If configuration loading fails.
    """

    # ========================================================================
    # Step 1: Load Configuration
    # ========================================================================

    cfg = load_config()
    api_key = cfg["anthropic_api_key"]
    outputs_dir = cfg["outputs_dir"]

    # ========================================================================
    # Step 2: Log Start
    # ========================================================================

    log("📝 Step 1: Writing viral script + title...")

    # ========================================================================
    # Step 3: Define Nested call_claude() Function
    # ========================================================================

    def call_claude() -> dict:
        """
        Call Claude API to generate viral dog fact script.

        Returns:
            Parsed JSON dictionary with script, title, hashtags, topic, topic_cluster,
            hook_pattern_used, title_formula_used.

        Raises:
            ValueError: If JSON parsing fails or required fields missing.
        """

        # Create Anthropic client
        client = Anthropic(api_key=api_key)

        # Build prompt (handles learnings context internally)
        prompt = _build_prompt(channel_config)

        # Allow channel to override max_tokens (horror needs 2000+, dog facts 500)
        max_tokens = (
            channel_config.anthropic_max_tokens
            if channel_config is not None
            else ANTHROPIC_MAX_TOKENS
        )

        # Call Claude API
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Extract text response, strip markdown code fences if present
        response_text = message.content[0].text.strip()
        if response_text.startswith("```"):
            # Split on first fence: ['', 'json\n{...}\n```']  → take [1]
            response_text = response_text.split("```", 1)[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.rsplit("```", 1)[0].strip()

        # Parse JSON
        try:
            metadata = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON response from Claude: {str(e)}\n"
                f"Response text: {response_text}"
            )

        # Validate required fields — only fields every channel must return
        required_fields = {"script", "title", "hook_overlay", "hashtags", "topic_cluster"}
        missing_fields = required_fields - set(metadata.keys())

        if missing_fields:
            raise ValueError(
                f"Missing required fields in JSON response: {missing_fields}\n"
                f"Response: {metadata}"
            )

        # Validate hashtags is a list
        if not isinstance(metadata.get("hashtags"), list):
            raise ValueError(
                f"hashtags must be a list, got {type(metadata.get('hashtags'))}"
            )

        return metadata

    # ========================================================================
    # Step 4: Call Claude with Retry Logic
    # ========================================================================

    metadata = retry_with_backoff(
        call_claude,
        max_retries=1,
        step_name="Claude API"
    )

    # ========================================================================
    # Step 5: Write script.txt
    # ========================================================================

    script_file = outputs_dir / "script.txt"
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(metadata["script"])

    # ========================================================================
    # Step 6: Write metadata.json
    # ========================================================================

    metadata_file = outputs_dir / "metadata.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # ========================================================================
    # Step 7: Log Completion
    # ========================================================================

    log("✅ Viral script generated!")

    # ========================================================================
    # Step 8: Return Metadata
    # ========================================================================

    return metadata
