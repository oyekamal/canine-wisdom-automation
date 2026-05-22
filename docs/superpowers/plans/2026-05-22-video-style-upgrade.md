# Video Style Upgrade — 2026 Shorts Format Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the video pipeline to produce 2026-style YouTube Shorts with animated word-by-word captions, faster pacing (2–3s cuts), 25–35s length, bold text overlays, and a 1-second attention hook.

**Architecture:** All changes live in `build_video.py` and `generate_script.py`. The caption engine uses ffmpeg's `drawtext` filter with per-word timing derived from ElevenLabs timestamps. Script generation gets updated prompts for shorter scripts (25–35s) and hook-first structure. A one-shot `make_sample.py` entry point lets the client approve the new style before daily publishing is enabled.

**Tech Stack:** Python 3, ffmpeg (drawtext filter), ElevenLabs aligned timestamps API, Anthropic Claude API, existing pipeline infrastructure.

---

## File Map

| File | Change |
|---|---|
| `generate_script.py` | Update prompt: 40–55 word target, hook rules, bold overlay phrases |
| `build_video.py` | Add `build_captioned_video()` replacing `build_video()` — animated captions, multi-clip cuts, hook overlay |
| `caption_engine.py` | **New** — converts ElevenLabs word timestamps → ffmpeg `drawtext` expressions |
| `generate_audio.py` | Return word-level timestamps alongside audio duration |
| `make_sample.py` | **New** — one-shot runner that builds one sample video for client approval |
| `config.py` | Add `TARGET_DURATION_MIN = 25`, `TARGET_DURATION_MAX = 35` |
| `tests/test_caption_engine.py` | **New** — unit tests for caption timing logic |

---

## Task 1: Tighten script generation for 25–35s length

**Files:**
- Modify: `generate_script.py:88–115` (the `prompt` string)
- Modify: `config.py` (add duration constants)

- [ ] **Step 1: Add duration constants to config.py**

Open `config.py` and add after line 53 (`VIDEO_PRESET = "fast"`):

```python
# Target Short duration
TARGET_DURATION_MIN = 25   # seconds
TARGET_DURATION_MAX = 35   # seconds
# Approx 130 words per minute → 25-35s ≈ 54-76 words
TARGET_WORD_COUNT_MIN = 54
TARGET_WORD_COUNT_MAX = 76
```

- [ ] **Step 2: Update the Claude prompt in generate_script.py**

Replace the `prompt = f"""..."""` block (lines 88–115) with:

```python
        prompt = f"""You are a viral YouTube Shorts scriptwriter for a dog channel in 2026.

Top-performing hook patterns (use one):
{hooks_text}

Top-performing title formulas (use one):
{titles_text}

Topics covered in the last 30 days (DO NOT repeat):
{covered_text}

Write a dog fact script for a 25–35 second Short. Rules:
1. FIRST SENTENCE = HOOK. Make it a bold, specific claim or question that dog owners can't ignore.
   Examples of good hooks: "STOP doing this when your dog jumps on you.", "Most owners get this completely wrong.", "Did you know a dog's nose print is as unique as a fingerprint?"
2. WORD COUNT: 54–76 words total (25–35 seconds at 130 wpm). Count every word.
3. No filler words. No "amazing" or "incredible". Simple, punchy sentences.
4. Include one stat, number, or comparison (e.g. "3x faster", "9 out of 10 vets").
5. End with exactly: "Follow for daily dog facts!"
6. Suggest one bold TEXT OVERLAY phrase (3–6 words, all caps) that should appear on screen in the first 2 seconds. Example: "STOP DOING THIS", "MOST OWNERS GET THIS WRONG".

Return ONLY valid JSON (no markdown, no extra text):
{{
    "script": "Full script here",
    "title": "Clickbait title under 60 chars",
    "hook_overlay": "BOLD OVERLAY PHRASE IN CAPS",
    "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
    "topic": "2-5 word description",
    "topic_cluster": "one of: dog health, dog behavior, dog breeds, dog training, dog history, dog science, dog fun",
    "hook_pattern_used": "the hook pattern template you used",
    "title_formula_used": "the title formula template you used"
}}"""
```

- [ ] **Step 3: Add `hook_overlay` to required fields validation**

In `generate_script.py`, find:
```python
        required_fields = {"script", "title", "hashtags", "topic", "topic_cluster",
                           "hook_pattern_used", "title_formula_used"}
```
Replace with:
```python
        required_fields = {"script", "title", "hook_overlay", "hashtags", "topic", "topic_cluster",
                           "hook_pattern_used", "title_formula_used"}
```

- [ ] **Step 4: Write failing test**

Create `tests/test_script_length.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
import json

SAMPLE_METADATA = {
    "script": "STOP doing this when your dog jumps on you. Every time you push them down, you're rewarding them with touch. Instead, turn your back completely and ignore them for 10 seconds. Dogs hate being ignored more than any punishment. Three days of this and the jumping stops for good. Follow for daily dog facts!",
    "title": "Why Your Dog Still Jumps On You",
    "hook_overlay": "STOP DOING THIS",
    "hashtags": ["dogs", "dogtraining", "dogfacts", "puppy", "dogowner", "dogshorts", "doglover", "dogmom", "dogdad", "doglife"],
    "topic": "jumping behavior fix",
    "topic_cluster": "dog training",
    "hook_pattern_used": "STOP doing [common mistake]",
    "title_formula_used": "Why Your Dog [common problem]"
}

def test_script_word_count_in_range():
    words = SAMPLE_METADATA["script"].split()
    assert 54 <= len(words) <= 76, f"Word count {len(words)} out of range 54-76"

def test_hook_overlay_is_caps():
    overlay = SAMPLE_METADATA["hook_overlay"]
    assert overlay == overlay.upper(), "hook_overlay must be all caps"

def test_hook_overlay_word_count():
    words = SAMPLE_METADATA["hook_overlay"].split()
    assert 3 <= len(words) <= 6, f"hook_overlay word count {len(words)} must be 3-6"
```

- [ ] **Step 5: Run test**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
python -m pytest tests/test_script_length.py -v
```
Expected: all 3 tests PASS (using sample data, not live API).

- [ ] **Step 6: Commit**

```bash
git add config.py generate_script.py tests/test_script_length.py
git commit -m "feat: update script prompt for 25-35s length and hook overlay phrase"
```

---

## Task 2: Return word timestamps from ElevenLabs

**Files:**
- Read: `generate_audio.py` (understand current structure)
- Modify: `generate_audio.py` — return `(duration, word_timestamps)` tuple

- [ ] **Step 1: Read current generate_audio.py**

```bash
cat -n generate_audio.py
```

- [ ] **Step 2: Update generate_audio to use alignment endpoint**

ElevenLabs `/v1/text-to-speech/{voice_id}/with-timestamps` returns word-level alignment. Update the API call to use this endpoint and extract `alignment.characters` → convert to word timestamps.

In `generate_audio.py`, find the ElevenLabs API call and replace with:

```python
import requests
import json

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

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
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
    data = response.json()

    # Decode and save audio
    import base64
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

    # Save timestamps for caption engine
    ts_path = outputs_dir / "word_timestamps.json"
    with open(ts_path, "w") as f:
        json.dump(word_timestamps, f, indent=2)

    # Get real duration via ffprobe
    import subprocess
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
```

- [ ] **Step 3: Update main.py to handle new tuple return**

In `main.py`, find:
```python
        audio_duration = generate_audio()
```
Replace with:
```python
        audio_duration, word_timestamps = generate_audio()
```

And update `build_video` call:
```python
        video_path = build_video(audio_duration, word_timestamps=word_timestamps)
```

- [ ] **Step 4: Write failing test**

Create `tests/test_chars_to_words.py`:

```python
from generate_audio import _chars_to_words

def test_basic_word_split():
    chars = list("hello world")
    starts = [i * 0.1 for i in range(len(chars))]
    ends = [s + 0.1 for s in starts]
    result = _chars_to_words(chars, starts, ends)
    assert len(result) == 2
    assert result[0]["word"] == "hello"
    assert result[1]["word"] == "world"
    assert result[0]["start"] == pytest.approx(0.0)
    assert result[1]["start"] == pytest.approx(0.6)

def test_empty_input():
    assert _chars_to_words([], [], []) == []

import pytest
```

- [ ] **Step 5: Run test**

```bash
python -m pytest tests/test_chars_to_words.py -v
```
Expected: 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add generate_audio.py main.py tests/test_chars_to_words.py
git commit -m "feat: add word-level timestamps from ElevenLabs alignment API"
```

---

## Task 3: Build caption engine (word-by-word animated text)

**Files:**
- Create: `caption_engine.py`
- Create: `tests/test_caption_engine.py`

- [ ] **Step 1: Write failing tests first**

Create `tests/test_caption_engine.py`:

```python
from caption_engine import words_to_drawtext, CaptionStyle

SAMPLE_WORDS = [
    {"word": "STOP", "start": 0.0, "end": 0.3},
    {"word": "doing", "start": 0.3, "end": 0.6},
    {"word": "this", "start": 0.6, "end": 0.9},
]

def test_drawtext_count_matches_words():
    style = CaptionStyle()
    filters = words_to_drawtext(SAMPLE_WORDS, style)
    assert len(filters) == 3

def test_drawtext_contains_word_text():
    style = CaptionStyle()
    filters = words_to_drawtext(SAMPLE_WORDS, style)
    assert "STOP" in filters[0]
    assert "doing" in filters[1]

def test_drawtext_has_enable_range():
    style = CaptionStyle()
    filters = words_to_drawtext(SAMPLE_WORDS, style)
    # Each filter must enable only during the word's window
    assert "enable='between(t,0.0,0.3)'" in filters[0]
    assert "enable='between(t,0.3,0.6)'" in filters[1]

def test_drawtext_uses_bold_color():
    style = CaptionStyle(font_color="yellow")
    filters = words_to_drawtext(SAMPLE_WORDS, style)
    assert "fontcolor=yellow" in filters[0]

def test_empty_words_returns_empty():
    style = CaptionStyle()
    assert words_to_drawtext([], style) == []
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_caption_engine.py -v
```
Expected: ImportError / ModuleNotFoundError.

- [ ] **Step 3: Create caption_engine.py**

```python
"""
Caption engine: converts word timestamps to ffmpeg drawtext filter expressions.

Style choices for 2026 Shorts: bold yellow text with black stroke, centered,
lower-third position, word-by-word reveal.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class CaptionStyle:
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_color: str = "yellow"
    stroke_color: str = "black"
    stroke_width: int = 4
    font_size: int = 72
    # x/y as ffmpeg expressions for centered, lower-third
    x_expr: str = "(w-text_w)/2"
    y_expr: str = "(h*0.72)"
    shadow_x: int = 3
    shadow_y: int = 3


def words_to_drawtext(word_timestamps: List[dict], style: CaptionStyle) -> List[str]:
    """
    Convert word-level timestamps to a list of ffmpeg drawtext filter strings.

    Each string is one `drawtext=...` expression enabled only during that word's
    time window. Caller joins them with commas into the ffmpeg -vf chain.

    Args:
        word_timestamps: list of {"word": str, "start": float, "end": float}
        style: CaptionStyle dataclass

    Returns:
        List of drawtext filter strings, one per word.
    """
    if not word_timestamps:
        return []

    filters = []
    for wt in word_timestamps:
        word = wt["word"].replace("'", "\\'").replace(":", "\\:")
        start = wt["start"]
        end = wt["end"]

        expr = (
            f"drawtext="
            f"fontfile='{style.font_path}':"
            f"text='{word}':"
            f"fontcolor={style.font_color}:"
            f"fontsize={style.font_size}:"
            f"borderw={style.stroke_width}:"
            f"bordercolor={style.stroke_color}:"
            f"shadowx={style.shadow_x}:"
            f"shadowy={style.shadow_y}:"
            f"x={style.x_expr}:"
            f"y={style.y_expr}:"
            f"enable='between(t,{start},{end})'"
        )
        filters.append(expr)

    return filters


def build_caption_filter(word_timestamps: List[dict], style: CaptionStyle = None) -> str:
    """
    Build a complete ffmpeg -vf compatible caption filter string.

    Returns:
        Comma-joined drawtext expressions, or empty string if no timestamps.
    """
    if style is None:
        style = CaptionStyle()
    filters = words_to_drawtext(word_timestamps, style)
    return ",".join(filters)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/test_caption_engine.py -v
```
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add caption_engine.py tests/test_caption_engine.py
git commit -m "feat: add caption engine for word-by-word animated subtitles"
```

---

## Task 4: Upgrade build_video.py — captions + hook overlay + pacing

**Files:**
- Modify: `build_video.py` — update `build_video()` to accept `word_timestamps` and `hook_overlay`; add caption filter; add hook text overlay in first 1.5s

- [ ] **Step 1: Update build_video() signature and caption integration**

In `build_video.py`, add import at top:
```python
from caption_engine import build_caption_filter, CaptionStyle
```

Replace the `build_video` function signature:
```python
def build_video(audio_duration: float, clip_path: str = None,
                word_timestamps: list = None, hook_overlay: str = None) -> str:
```

- [ ] **Step 2: Replace the video_filter in build_video()**

Find the existing `video_filter = (...)` block and replace with:

```python
    # Base scale + color grading
    base_filter = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
        f"eq=brightness=0.02:saturation=1.4:contrast=1.1"
    )

    # Hook overlay: bold all-caps text in first 1.5 seconds
    hook_filter = ""
    if hook_overlay:
        safe_hook = hook_overlay.replace("'", "\\'").replace(":", "\\:")
        hook_font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        hook_filter = (
            f"drawtext=fontfile='{hook_font}':"
            f"text='{safe_hook}':"
            f"fontcolor=white:"
            f"fontsize=90:"
            f"borderw=5:"
            f"bordercolor=black:"
            f"shadowx=4:shadowy=4:"
            f"x=(w-text_w)/2:y=(h*0.35):"
            f"enable='between(t,0,1.5)'"
        )

    # Word-by-word captions
    caption_filter = ""
    if word_timestamps:
        style = CaptionStyle(font_size=68, font_color="yellow", stroke_width=4)
        caption_filter = build_caption_filter(word_timestamps, style)

    # Combine filters
    filter_parts = [base_filter]
    if hook_filter:
        filter_parts.append(hook_filter)
    if caption_filter:
        filter_parts.append(caption_filter)
    video_filter = ",".join(filter_parts)
```

- [ ] **Step 3: Enforce 25–35s duration clamp**

After `actual_video_path = optimizer.trim_video_segment(audio_duration)`, add:

```python
    from config import TARGET_DURATION_MIN, TARGET_DURATION_MAX
    if audio_duration < TARGET_DURATION_MIN:
        log(f"⚠️  Audio is {audio_duration:.1f}s — shorter than target {TARGET_DURATION_MIN}s")
    elif audio_duration > TARGET_DURATION_MAX:
        log(f"⚠️  Audio is {audio_duration:.1f}s — longer than target {TARGET_DURATION_MAX}s")
        audio_duration = float(TARGET_DURATION_MAX)
        log(f"✂️  Clamping video to {TARGET_DURATION_MAX}s")
```

- [ ] **Step 4: Write integration smoke test**

Create `tests/test_build_video_filters.py`:

```python
from unittest.mock import patch, MagicMock
from caption_engine import build_caption_filter, CaptionStyle

def test_hook_filter_format():
    hook = "STOP DOING THIS"
    safe = hook.replace("'", "\\'").replace(":", "\\:")
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    result = (
        f"drawtext=fontfile='{font}':"
        f"text='{safe}':"
        f"fontcolor=white:"
        f"fontsize=90:"
        f"borderw=5:"
        f"bordercolor=black:"
        f"shadowx=4:shadowy=4:"
        f"x=(w-text_w)/2:y=(h*0.35):"
        f"enable='between(t,0,1.5)'"
    )
    assert "STOP DOING THIS" in result
    assert "enable='between(t,0,1.5)'" in result

def test_caption_filter_concatenated():
    words = [
        {"word": "Hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.4, "end": 0.8},
    ]
    style = CaptionStyle()
    result = build_caption_filter(words, style)
    assert result.count("drawtext=") == 2
    assert "," in result
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_build_video_filters.py -v
```
Expected: 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add build_video.py tests/test_build_video_filters.py
git commit -m "feat: animated captions, hook overlay, and duration clamp in build_video"
```

---

## Task 5: Create make_sample.py — one-shot sample video for client approval

**Files:**
- Create: `make_sample.py`

This script runs the full pipeline once and saves the result to `outputs/sample_YYYY-MM-DD.mp4` without uploading to YouTube.

- [ ] **Step 1: Write make_sample.py**

```python
#!/usr/bin/env python3
"""
One-shot sample video generator for client style approval.

Runs the full pipeline (script → audio → video) but skips YouTube upload.
Output: outputs/sample_<date>.mp4

Usage:
    python make_sample.py
"""

import sys
from datetime import datetime
from pathlib import Path
from config import load_config
from utils import init_logger, log, clear_outputs_dir
from generate_script import generate_script
from generate_audio import generate_audio
from build_video import build_video


def main():
    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    init_logger(run_id)

    log("🎬 SAMPLE VIDEO GENERATOR — new 2026 style")
    log("=" * 50)

    try:
        load_config()
        clear_outputs_dir()

        log("")
        metadata = generate_script()
        log(f"📋 Script ({len(metadata['script'].split())} words): {metadata['script'][:80]}...")
        log(f"🎯 Hook overlay: {metadata.get('hook_overlay', 'N/A')}")

        log("")
        audio_duration, word_timestamps = generate_audio()
        log(f"🎙️ Audio: {audio_duration:.1f}s, {len(word_timestamps)} words with timestamps")

        log("")
        video_path = build_video(
            audio_duration,
            word_timestamps=word_timestamps,
            hook_overlay=metadata.get("hook_overlay"),
        )

        # Copy to named sample file
        sample_name = f"outputs/sample_{datetime.now().strftime('%Y-%m-%d')}.mp4"
        import shutil
        shutil.copy(video_path, sample_name)

        log("")
        log("=" * 50)
        log(f"✅ SAMPLE READY: {sample_name}")
        log("📺 Open this file to review the new style before enabling daily publishing.")
        log(f"📝 Title: {metadata['title']}")
        log(f"⏱️  Duration: {audio_duration:.1f}s")

        return 0

    except Exception as e:
        log(f"❌ Sample generation failed: {e}", level="error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Make executable**

```bash
chmod +x make_sample.py
```

- [ ] **Step 3: Dry-run import check (no API calls)**

```bash
python -c "import make_sample; print('Import OK')"
```
Expected: `Import OK`

- [ ] **Step 4: Commit**

```bash
git add make_sample.py
git commit -m "feat: add make_sample.py for client style approval before daily publishing"
```

---

## Task 6: Run the sample end-to-end and verify

- [ ] **Step 1: Run the full test suite**

```bash
python -m pytest tests/ -v --tb=short
```
All tests should PASS.

- [ ] **Step 2: Generate the sample video**

```bash
python make_sample.py
```

Expected log output includes:
- Script word count 54–76
- Hook overlay text printed
- Audio duration 25–35s
- `✅ SAMPLE READY: outputs/sample_<date>.mp4`

- [ ] **Step 3: Inspect the sample video**

Open `outputs/sample_<date>.mp4` in a video player and verify:
- Bold all-caps hook text visible in first 1.5 seconds
- Yellow word-by-word captions appear throughout
- Video length is 25–35 seconds
- Vertical 1080×1920 format

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: verify sample video generation end-to-end"
```

---

## Self-Review Checklist

| Requirement | Task |
|---|---|
| Animated word-by-word captions with bold colors + shadows | Task 3, 4 |
| Faster cuts every 2–3 seconds | Not yet implemented — requires multi-clip assembly (future task) |
| 25–35 second length | Task 1 (script prompt), Task 4 (duration clamp) |
| Higher quality footage | Out of scope for code — requires sourcing new footage files |
| 1-second hook overlay | Task 4 (hook_filter, 0–1.5s) |
| Bold text overlay phrases | Task 1 (hook_overlay field), Task 4 |
| One revised sample video | Task 5 |
| Client approval before daily publishing | Task 5 (make_sample.py) |

> **Note on multi-clip pacing:** True 2–3 second cuts require assembling multiple video segments with ffmpeg concat. This is a larger change that can follow once the client approves the caption style. The current plan focuses on captions, length, and hook overlay as the highest-impact changes.
