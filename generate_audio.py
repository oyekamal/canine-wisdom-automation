"""
Audio generation module for Canine Wisdom YouTube Shorts Pipeline.

Generates voiceover using ElevenLabs with word-level timestamp alignment.
"""

import base64
import json
import subprocess
import requests
from pathlib import Path
from config import load_config, ELEVENLABS_API_BASE
from utils import log, retry_with_backoff


def generate_audio() -> tuple:
    """
    Generate voiceover using ElevenLabs with word-level timestamps.

    Returns:
        tuple: (audio_duration_seconds: float, word_timestamps: list[dict])
               word_timestamps format: [{"word": str, "start": float, "end": float}, ...]
    """
    cfg = load_config()
    api_key = cfg["elevenlabs_api_key"]
    voice_id = cfg["elevenlabs_voice_id"]
    outputs_dir = cfg["outputs_dir"]

    script_path = outputs_dir / "script.txt"
    with open(script_path, "r", encoding="utf-8") as f:
        script_text = f.read().strip()

    log("🎙️ Step 2: Generating voiceover with timestamps...")

    def call_elevenlabs():
        url = f"{ELEVENLABS_API_BASE}/v1/text-to-speech/{voice_id}/with-timestamps"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": script_text,
            "model_id": "eleven_turbo_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8},
        }

        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()

    data = retry_with_backoff(call_elevenlabs, max_retries=1, step_name="ElevenLabs API")

    # Decode and save audio
    audio_bytes = base64.b64decode(data["audio_base64"])
    audio_path = outputs_dir / "voiceover.mp3"
    with open(audio_path, "wb") as f:
        f.write(audio_bytes)

    # Extract word-level timestamps from character alignment
    alignment = data.get("alignment", {})
    chars = alignment.get("characters", [])
    char_starts = alignment.get("character_start_times_seconds", [])
    char_ends = alignment.get("character_end_times_seconds", [])

    word_timestamps = _chars_to_words(chars, char_starts, char_ends)

    # Save timestamps alongside audio for debugging
    ts_path = outputs_dir / "word_timestamps.json"
    with open(ts_path, "w") as f:
        json.dump(word_timestamps, f, indent=2)

    # Get real duration via ffprobe
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "csv=p=0", str(audio_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    audio_duration = float(result.stdout.strip())

    log(f"✅ Audio generated: {audio_duration:.1f}s, {len(word_timestamps)} words")
    return audio_duration, word_timestamps


def _chars_to_words(chars, starts, ends):
    """Convert character-level alignment to word-level timestamps."""
    if not chars:
        return []

    words = []
    current_word_chars = []
    current_word_start = None

    for i, (ch, s, e) in enumerate(zip(chars, starts, ends)):
        if ch == " " or ch == "\n":
            if current_word_chars:
                words.append({
                    "word": "".join(current_word_chars),
                    "start": current_word_start,
                    "end": ends[i - 1] if i > 0 else e,
                })
                current_word_chars = []
                current_word_start = None
        else:
            if current_word_start is None:
                current_word_start = s
            current_word_chars.append(ch)

    if current_word_chars:
        words.append({
            "word": "".join(current_word_chars),
            "start": current_word_start,
            "end": ends[-1],
        })

    return words
