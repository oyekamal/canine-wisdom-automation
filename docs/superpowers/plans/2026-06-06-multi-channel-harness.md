# Multi-Channel Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the user runs `python3 main.py` (or says "run harness"), both `canine-wisdom` and `horror-narration` channels run their full pipelines and upload to their respective YouTube channels.

**Architecture:** `main.py` becomes a multi-channel orchestrator — it reads a list of active channel slugs, runs the full pipeline (script → audio → video → upload) for each one sequentially, and uses each channel's own `token.json` + `settings.json` for credentials and config. All existing per-module `channel_config` support is already in place; only `main.py` and `generate_audio.py` need wiring.

**Tech Stack:** Python 3, existing `channel_config.py`, `generate_script.py`, `generate_audio.py`, `build_video.py`, `upload_youtube.py`

---

## Files to Create / Modify

| File | Action | What changes |
|------|--------|-------------|
| `main.py` | Modify | Loop over `["canine-wisdom", "horror-narration"]`, pass `channel_config` through all steps |
| `generate_audio.py` | Modify | Accept `channel_config` param, use `channel_config.voice_id` instead of hardcoded env var |
| `config.py` | Read only | Confirm `ACTIVE_CHANNELS` can live in `main.py` (no env changes needed) |

---

## Task 1: Wire `channel_config` into `generate_audio`

`generate_audio.py` currently reads `voice_id` from config/env. It needs to accept a `channel_config` param so each channel uses its own voice.

**Files:**
- Modify: `generate_audio.py`
- Test: `test_generate_audio.py`

- [ ] **Step 1: Read the current signature**

Open `generate_audio.py` and find the `generate_audio()` function signature (around line 1-30). Note what it currently uses for `voice_id`.

- [ ] **Step 2: Write the failing test**

Add this test to `test_generate_audio.py`:

```python
def test_generate_audio_uses_channel_voice_id(tmp_path, monkeypatch):
    """generate_audio should use channel_config.voice_id when provided."""
    from unittest.mock import MagicMock, patch
    from channel_config import ChannelConfig

    fake_cfg = MagicMock(spec=ChannelConfig)
    fake_cfg.voice_id = "HORROR_VOICE_123"

    captured = {}

    def fake_elevenlabs_call(voice_id, **kwargs):
        captured["voice_id"] = voice_id
        return b"fakeaudio"

    with patch("generate_audio._call_elevenlabs", side_effect=fake_elevenlabs_call):
        # Should not raise, should use horror voice
        try:
            generate_audio(channel_config=fake_cfg)
        except Exception:
            pass  # other errors are fine, we just want to check voice_id was passed

    assert captured.get("voice_id") == "HORROR_VOICE_123"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
source venv/bin/activate && pytest test_generate_audio.py::test_generate_audio_uses_channel_voice_id -v
```

Expected: FAIL — `generate_audio()` doesn't accept `channel_config` yet.

- [ ] **Step 4: Modify `generate_audio` to accept `channel_config`**

Find the `generate_audio(` function definition. Change its signature and voice_id resolution:

```python
def generate_audio(channel_config=None) -> tuple[float, list]:
    config = load_config()
    # Use channel-specific voice_id if provided, else fall back to env/config
    voice_id = (
        channel_config.voice_id
        if channel_config is not None
        else config.get("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")
    )
    # ... rest of function unchanged, replace any hardcoded voice_id var with this one
```

Grep for every place `voice_id` is used inside `generate_audio.py` and make sure they all reference this local variable (not re-reading from config).

- [ ] **Step 5: Run test to verify it passes**

```bash
source venv/bin/activate && pytest test_generate_audio.py::test_generate_audio_uses_channel_voice_id -v
```

Expected: PASS

- [ ] **Step 6: Run full audio test suite to check no regressions**

```bash
source venv/bin/activate && pytest test_generate_audio.py -v
```

Expected: all previously passing tests still PASS.

- [ ] **Step 7: Commit**

```bash
git add generate_audio.py test_generate_audio.py
git commit -m "feat: generate_audio accepts channel_config for per-channel voice_id"
```

---

## Task 2: Refactor `main.py` into a multi-channel orchestrator

`main.py` currently runs one hardcoded channel. Replace it with a loop over active channels.

**Files:**
- Modify: `main.py`
- Test: `test_main.py`

- [ ] **Step 1: Write the failing test**

Add this to `test_main.py`:

```python
def test_main_runs_both_channels(monkeypatch):
    """main() should invoke the pipeline once per active channel."""
    from unittest.mock import MagicMock, patch, call
    import main as main_module

    ran_channels = []

    def fake_run_channel(slug, run_id):
        ran_channels.append(slug)

    monkeypatch.setattr(main_module, "run_channel_pipeline", fake_run_channel)

    main_module.main()

    assert "canine-wisdom" in ran_channels
    assert "horror-narration" in ran_channels
    assert len(ran_channels) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source venv/bin/activate && pytest test_main.py::test_main_runs_both_channels -v
```

Expected: FAIL — `run_channel_pipeline` doesn't exist yet.

- [ ] **Step 3: Rewrite `main.py`**

Replace the entire content of `main.py` with:

```python
#!/usr/bin/env python3
"""
Multi-channel YouTube Shorts automation pipeline.
Runs all active channels sequentially on each invocation.
"""

import sys
from datetime import datetime
from pathlib import Path
from channel_config import load_channel_config
from utils import init_logger, log, clear_outputs_dir, move_outputs_to_archive
from generate_script import generate_script
from generate_audio import generate_audio
from build_video import build_video
from upload_youtube import upload_youtube

ACTIVE_CHANNELS = ["canine-wisdom", "horror-narration"]


def run_channel_pipeline(slug: str, run_id: str) -> None:
    """Run the full pipeline for a single channel slug."""
    log(f"\n{'='*60}")
    log(f"📺 Starting pipeline for channel: {slug}")
    log(f"{'='*60}")

    channel_config = load_channel_config(slug)

    clear_outputs_dir()

    # Step 1: Script
    log("")
    metadata = generate_script(channel_config=channel_config)

    # Step 2: Audio
    log("")
    audio_duration, word_timestamps = generate_audio(channel_config=channel_config)

    # Step 3: Video
    log("")
    video_path = build_video(
        audio_duration,
        word_timestamps=word_timestamps,
        script_data=metadata,
        channel_config=channel_config,
        channel_slug=slug,
    )

    # Step 4: Upload
    log("")
    try:
        video_url = upload_youtube(channel_config=channel_config)
        log("")
        log(f"🎉 [{slug}] Short is LIVE!")
        log(f"📺 Watch here: {video_url}")
    except FileNotFoundError:
        log(f"⏭️  [{slug}] YouTube upload skipped (credentials not found)")
        log(f"   Video ready at: outputs/final_video.mp4")

    log("")
    move_outputs_to_archive(f"{run_id}_{slug}")


def main() -> int:
    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    init_logger(run_id)

    log("🚀 Multi-Channel YouTube Shorts Pipeline")
    log(f"📋 Active channels: {', '.join(ACTIVE_CHANNELS)}")

    failed = []
    for slug in ACTIVE_CHANNELS:
        try:
            run_channel_pipeline(slug, run_id)
        except KeyboardInterrupt:
            log("❌ Pipeline interrupted by user")
            return 1
        except Exception as e:
            log(f"❌ [{slug}] Pipeline failed: {str(e)}", level="error")
            log(f"📋 Check run_logs/ for details")
            failed.append(slug)
            continue  # keep going for the next channel

    if failed:
        log(f"\n⚠️  Failed channels: {', '.join(failed)}")
        return 1

    log(f"\n✅ All {len(ACTIVE_CHANNELS)} channels complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the new test**

```bash
source venv/bin/activate && pytest test_main.py::test_main_runs_both_channels -v
```

Expected: PASS

- [ ] **Step 5: Run full main test suite**

```bash
source venv/bin/activate && pytest test_main.py -v
```

Fix any broken tests before continuing.

- [ ] **Step 6: Commit**

```bash
git add main.py test_main.py
git commit -m "feat: main.py runs all active channels sequentially"
```

---

## Task 3: Smoke-test the full pipeline end-to-end

Verify both channels run and produce separate uploads without manual steps.

**Files:** No file changes — this is a validation task.

- [ ] **Step 1: Run the pipeline**

```bash
source venv/bin/activate && python3 main.py 2>&1 | tee run_logs/test_multichannel.log
```

- [ ] **Step 2: Verify canine-wisdom uploaded**

Check the log for:
```
[canine-wisdom] Short is LIVE!
📺 Watch here: https://youtube.com/shorts/...
```

- [ ] **Step 3: Verify horror-narration uploaded to dailyygstories**

Check the log for:
```
[horror-narration] Short is LIVE!
📺 Watch here: https://youtube.com/shorts/...
```

Open the URL — confirm it appears on the **dailyygstories** YouTube channel, not canine wisdom.

- [ ] **Step 4: Verify archives are separate**

```bash
ls archive/ | tail -4
```

Expected: two entries ending in `_canine-wisdom` and `_horror-narration` for this run.

- [ ] **Step 5: Commit**

```bash
git add run_logs/test_multichannel.log
git commit -m "chore: multi-channel smoke test log"
```

---

## Self-Review

**Spec coverage:**
- ✅ "run harness" runs both channels → Task 2 (ACTIVE_CHANNELS loop in main.py)
- ✅ Horror uploads to dailyygstories (separate token.json) → already in place, Task 3 verifies
- ✅ Each channel uses its own voice → Task 1
- ✅ Each channel uses its own footage/music → already wired in build_video.py via channel_config
- ✅ Each channel uses its own script prompt → already wired in generate_script.py via channel_config

**Placeholder scan:** None found.

**Type consistency:** `run_channel_pipeline(slug: str, run_id: str)` defined in Task 2 step 3, referenced in test in Task 2 step 1 — consistent.
