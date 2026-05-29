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

# Supertonic TTS — free local CPU fallback when ElevenLabs is unavailable
try:
    from supertonic_mnn import SupertonicTTS as _SupertonicTTS
    SUPERTONIC_AVAILABLE = True
except ImportError:
    SUPERTONIC_AVAILABLE = False

_VOICE_MAP = {
    "pNInz6obpgDQGcFmaJgB": "M1",  # Adam (dog channel default)
    "JBFqnCBsd6RMkjVDRZzb": "M2",  # George (horror long-form)
    "N2lVS1w4EtoT3dr4eOWO": "M1",  # Callum (horror eerie/short)
    "SOYHLrjzK2X1ezoPC6cr": "M2",  # Harry (horror intense)
    "EXAVITQu4vr4xnSDxMaL": "F1",  # Sarah (horror paranormal)
    "CwhRBWXzGAHq8TQ4Fs17": "M1",  # Roger
    "FGY2WhTYpPnrIDTdsKH5": "F2",  # Laura
}


def _map_voice_to_supertonic(elevenlabs_voice_id: str) -> str:
    """Map an ElevenLabs voice ID to the closest Supertonic voice (M1/M2/F1/F2)."""
    return _VOICE_MAP.get(elevenlabs_voice_id, "M1")


def _approximate_word_timestamps(script: str, audio_duration: float) -> list:
    """
    Generate approximate word-level timestamps by evenly distributing words.
    Used when ElevenLabs alignment is unavailable (Supertonic fallback).
    """
    words = script.split()
    if not words:
        return []
    step = audio_duration / len(words)
    return [
        {"word": w, "start": round(i * step, 3), "end": round((i + 1) * step, 3)}
        for i, w in enumerate(words)
    ]


def generate_audio_supertonic(script: str, voice_id: str = None) -> tuple:
    """
    Generate audio using Supertonic local TTS.
    Returns (audio_duration: float, word_timestamps: list) — same as ElevenLabs path.
    Raises RuntimeError if supertonic-mnn not installed.
    """
    if not SUPERTONIC_AVAILABLE:
        raise RuntimeError("supertonic-mnn not installed. Run: pip install supertonic-mnn")

    log("🔄 Using Supertonic TTS (local fallback)...")

    cfg = load_config()
    outputs_dir = cfg["outputs_dir"]

    supertonic_voice = _map_voice_to_supertonic(voice_id or "")
    log(f"🎤 Supertonic voice: {supertonic_voice}")

    wav_path = outputs_dir / "voiceover.wav"
    mp3_path = outputs_dir / "voiceover.mp3"

    tts = _SupertonicTTS()
    tts.synthesize(script, voice=supertonic_voice, output_file=str(wav_path))

    # WAV → MP3 (pipeline expects .mp3)
    result = subprocess.run(
        ["ffmpeg", "-i", str(wav_path), "-codec:a", "libmp3lame", "-qscale:a", "2", "-y", str(mp3_path)],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"WAV→MP3 conversion failed: {result.stderr[-200:]}")

    # Get real duration via ffprobe
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3_path)],
        capture_output=True, text=True, timeout=10,
    )
    audio_duration = float(probe.stdout.strip())

    word_timestamps = _approximate_word_timestamps(script, audio_duration)

    ts_path = outputs_dir / "word_timestamps.json"
    with open(ts_path, "w") as f:
        json.dump(word_timestamps, f, indent=2)

    log(f"✅ Supertonic audio: {audio_duration:.1f}s, {len(word_timestamps)} words (approx timestamps)")
    return audio_duration, word_timestamps


def generate_audio(script: str = None, voice_id: str = None) -> tuple:
    """
    Generate voiceover using ElevenLabs with word-level timestamps.

    Args:
        script: Script text to convert to audio. If None, loads from outputs/script.txt.
        voice_id: ElevenLabs voice ID to use. If None, loads from config.

    Returns:
        tuple: (audio_duration_seconds: float, word_timestamps: list[dict])
               word_timestamps format: [{"word": str, "start": float, "end": float}, ...]
    """
    cfg = load_config()
    api_key = cfg["elevenlabs_api_key"]
    if voice_id is None:
        voice_id = cfg["elevenlabs_voice_id"]
    outputs_dir = cfg["outputs_dir"]

    if script is None:
        script_path = outputs_dir / "script.txt"
        metadata_path = outputs_dir / "metadata.json"
        if script_path.exists():
            with open(script_path, "r", encoding="utf-8") as f:
                script = f.read().strip()
        elif metadata_path.exists():
            import json as _json
            meta = _json.loads(metadata_path.read_text(encoding="utf-8"))
            script = meta["script"]
        else:
            raise FileNotFoundError(f"No script found at {script_path} or {metadata_path}")

    script_text = script

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

    try:
        data = retry_with_backoff(call_elevenlabs, max_retries=1, step_name="ElevenLabs API")

        # Decode and save audio
        audio_bytes = base64.b64decode(data["audio_base64"])
        audio_path = outputs_dir / "voiceover.mp3"
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)

        alignment = data.get("alignment", {})
        chars = alignment.get("characters", [])
        char_starts = alignment.get("character_start_times_seconds", [])
        char_ends = alignment.get("character_end_times_seconds", [])
        word_timestamps = _chars_to_words(chars, char_starts, char_ends)

        ts_path = outputs_dir / "word_timestamps.json"
        with open(ts_path, "w") as f:
            json.dump(word_timestamps, f, indent=2)

        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", str(audio_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        audio_duration = float(result.stdout.strip())

        log(f"✅ Audio generated: {audio_duration:.1f}s, {len(word_timestamps)} words")
        return audio_duration, word_timestamps

    except Exception as elevenlabs_err:
        log(f"⚠️  ElevenLabs failed ({elevenlabs_err}) — falling back to Supertonic TTS",
            level="warning")
        if not SUPERTONIC_AVAILABLE:
            raise RuntimeError(
                f"ElevenLabs failed and supertonic-mnn is not installed. "
                f"Original error: {elevenlabs_err}"
            ) from elevenlabs_err
        return generate_audio_supertonic(script_text, voice_id)


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
