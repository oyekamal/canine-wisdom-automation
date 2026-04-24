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
        Dictionary with keys: script, title, hashtags

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
            Parsed JSON dictionary with script, title, hashtags.

        Raises:
            ValueError: If JSON parsing fails or required fields missing.
        """

        # Create Anthropic client
        client = Anthropic(api_key=api_key)

        # Define the prompt for Claude
        prompt = """You are a viral YouTube Shorts scriptwriter specializing in dog facts.

Write a 45-second dog fact script that would go VIRAL on YouTube Shorts. Follow these rules:
1. Start with a HOOK as the first sentence (something surprising or emotional)
2. Keep language simple and conversational
3. Include an emotional angle that makes people care
4. End with exactly: "Follow for daily dog facts!"
5. Make it energetic and exciting

Return ONLY valid JSON (no markdown, no extra text) with these exact fields:
{
    "script": "Full 45-second script text here",
    "title": "Clickbait title under 60 chars",
    "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"]
}"""

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
        required_fields = {"script", "title", "hashtags"}
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
