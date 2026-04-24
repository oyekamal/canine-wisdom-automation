"""
Audio generation module for Canine Wisdom YouTube Shorts Pipeline.

Generates energetic voiceover from script text using ElevenLabs API.
"""

import requests
from pathlib import Path
from config import load_config, ELEVENLABS_API_BASE
from utils import log, retry_with_backoff


def generate_audio() -> float:
    """
    Generate energetic voiceover from script using ElevenLabs API.

    Process:
    1. Load configuration
    2. Read script from outputs/script.txt
    3. Call ElevenLabs text-to-speech API with voice settings
    4. Write audio to outputs/voiceover.mp3
    5. Calculate estimated duration
    6. Return duration as float

    Returns:
        float: Estimated audio duration in seconds.

    Raises:
        FileNotFoundError: If script.txt does not exist.
        ValueError: If ElevenLabs API returns 400 error.
        Exception: If ElevenLabs API returns unexpected error.
    """

    # ========================================================================
    # Step 1: Load Configuration
    # ========================================================================

    cfg = load_config()
    api_key = cfg["elevenlabs_api_key"]
    voice_id = cfg["elevenlabs_voice_id"]
    outputs_dir = cfg["outputs_dir"]

    # ========================================================================
    # Step 2: Log Start
    # ========================================================================

    log("🎤 Step 2: Creating energetic voiceover...")

    # ========================================================================
    # Step 3: Read Script from outputs/script.txt
    # ========================================================================

    script_file = outputs_dir / "script.txt"
    if not script_file.exists():
        raise FileNotFoundError(
            f"Script file not found at {script_file}. "
            "Run generate_script() first."
        )

    with open(script_file, "r", encoding="utf-8") as f:
        script_text = f.read()

    # ========================================================================
    # Step 4: Define Nested call_elevenlabs() Function
    # ========================================================================

    def call_elevenlabs() -> bytes:
        """
        Call ElevenLabs text-to-speech API.

        Returns:
            bytes: Audio data in MP3 format.

        Raises:
            ValueError: If API returns 400 error.
            Exception: If API returns unexpected status code.
        """

        # Construct API URL
        url = f"{ELEVENLABS_API_BASE}/v1/text-to-speech/{voice_id}"

        # Set request headers
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json"
        }

        # Construct request data with voice settings
        request_data = {
            "text": script_text,
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.8,
                "style": 0.6,
                "use_speaker_boost": True
            }
        }

        # Make POST request to ElevenLabs API (30s timeout)
        response = requests.post(
            url,
            headers=headers,
            json=request_data,
            timeout=30
        )

        # ====================================================================
        # Handle Error Responses
        # ====================================================================

        if response.status_code == 401:
            raise Exception(
                "ElevenLabs API key invalid. Check ELEVENLABS_API_KEY in .env"
            )
        elif response.status_code == 400:
            raise ValueError(response.text)
        elif response.status_code not in (200, 201):
            raise Exception(
                f"ElevenLabs API error: {response.status_code}\n{response.text}"
            )

        # Return binary audio data
        return response.content

    # ========================================================================
    # Step 5: Call ElevenLabs with Retry Logic
    # ========================================================================

    audio_data = retry_with_backoff(
        call_elevenlabs,
        max_retries=1,
        step_name="ElevenLabs API"
    )

    # ========================================================================
    # Step 6: Write audio to outputs/voiceover.mp3
    # ========================================================================

    audio_file = outputs_dir / "voiceover.mp3"
    with open(audio_file, "wb") as f:
        f.write(audio_data)

    # ========================================================================
    # Step 7: Calculate Estimated Duration
    # ========================================================================

    # Audio bitrate is 192kbps (from config.py: AUDIO_BITRATE = "192k")
    # 192 kbps = 192 kilobits per second = 24 kilobytes per second
    audio_size_kb = len(audio_data) / 1024
    estimated_duration = audio_size_kb / 24

    # ========================================================================
    # Step 8: Log Completion
    # ========================================================================

    log("✅ Energetic voiceover created!")

    # ========================================================================
    # Step 9: Return Estimated Duration
    # ========================================================================

    return estimated_duration
