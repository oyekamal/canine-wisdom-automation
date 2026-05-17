"""
Script generation module for Canine Wisdom YouTube Shorts Pipeline.

Generates viral dog fact scripts using Claude API.
"""

import json
from pathlib import Path
from anthropic import Anthropic
from config import load_config, ANTHROPIC_MODEL, ANTHROPIC_MAX_TOKENS
from utils import log, retry_with_backoff


def generate_script() -> dict:
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

        # Build learnings context for the prompt
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
            covered_text = ", ".join(covered[:10]) or "none"
        except Exception:
            hooks_text = "- No data yet"
            titles_text = "- No data yet"
            covered_text = "none"

        # Define the prompt for Claude
        prompt = f"""You are a viral YouTube Shorts scriptwriter specializing in dog facts.

Top-performing hook patterns (use one of these or a similar structure):
{hooks_text}

Top-performing title formulas (use one of these or a similar structure):
{titles_text}

Topics covered in the last 30 days (DO NOT repeat these):
{covered_text}

Write a 45-second dog fact script that would go VIRAL on YouTube Shorts. Rules:
1. Start with a HOOK as the first sentence (surprising or emotional, matching a top pattern above)
2. Keep language simple and conversational
3. Include an emotional angle that makes people care
4. End with exactly: "Follow for daily dog facts!"
5. Make it energetic and exciting

Return ONLY valid JSON (no markdown, no extra text) with these exact fields:
{{
    "script": "Full 45-second script text here",
    "title": "Clickbait title under 60 chars",
    "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
    "topic": "2-5 word description of the dog fact topic",
    "topic_cluster": "one of: dog health, dog behavior, dog breeds, dog training, dog history, dog science, dog fun",
    "hook_pattern_used": "the hook pattern template you used (e.g. 'Did you know dogs can [fact]?')",
    "title_formula_used": "the title formula template you used (e.g. '[Surprising claim] Before [Authority]')"
}}"""

        # Call Claude API
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=ANTHROPIC_MAX_TOKENS,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        # Extract text response
        response_text = message.content[0].text

        # Parse JSON
        try:
            metadata = json.loads(response_text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON response from Claude: {str(e)}\n"
                f"Response text: {response_text}"
            )

        # Validate required fields
        required_fields = {"script", "title", "hashtags", "topic", "topic_cluster",
                           "hook_pattern_used", "title_formula_used"}
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
