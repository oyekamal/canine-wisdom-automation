# HyperFrames Asset Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace live overlay rendering with a pre-rendered asset library — HyperFrames renders overlay WebMs into `assets/overlays/<channel>/` keyed by content, and `build_video.py` picks and composites the right one; also fix the VP9 alpha black-screen bug in FFmpeg compositing.

**Architecture:** A new `overlay_library.py` module handles rendering and caching: given a channel slug + overlay type + content dict, it renders to `assets/overlays/<channel>/<type>/<hash>.webm` and returns that path (returning cached path on subsequent calls with same content). `build_video.py` calls `get_or_render_overlay()` instead of `render_overlay()` directly, and the FFmpeg composite command is fixed to force VP9 decoding so alpha is read correctly. The existing `overlay_renderer.py` is kept as the low-level Node bridge; `overlay_library.py` sits on top of it.

**Tech Stack:** Python, FFmpeg (VP9 alpha fix: `-vcodec libvpx-vp9` on WebM input), HyperFrames Node CLI (unchanged), hashlib for cache keys.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `overlay_library.py` | Cache-aware overlay rendering: hash content → render if miss → return path |
| Create | `tests/test_overlay_library.py` | Unit tests for overlay_library.py |
| Modify | `build_video.py:293-311` | Fix `composite_overlay()` VP9 alpha decode bug |
| Modify | `build_video.py:509-553` | Replace live `render_overlay()` call with `get_or_render_overlay()` |
| Modify | `harness/orchestrator.py:286-297` | Pass `script_data` and `channel_slug` consistently (already done; verify) |

---

## Task 1: Fix VP9 Alpha Black-Screen Bug in composite_overlay()

**Files:**
- Modify: `build_video.py:293-311`
- Test: manual ffprobe check

The black screen happens because FFmpeg auto-selects the h264 decoder for a VP9 stream when it encounters it as the second input. Adding `-vcodec libvpx-vp9` before the WebM `-i` forces correct decoding and exposes the alpha plane.

- [ ] **Step 1: Verify the bug exists**

```bash
ffprobe -v error -show_streams -select_streams v outputs/final_video.mp4 2>/dev/null | grep codec_name
```

Run a test composite with a known WebM that has alpha:
```bash
ffmpeg -y \
  -i /tmp/test_base.mp4 \
  -i /tmp/test_dog_overlay.webm \
  -filter_complex "[0:v][1:v]overlay=0:0[v]" \
  -map "[v]" -map "0:a?" -c:v libx264 -crf 18 -preset fast \
  -pix_fmt yuv420p -shortest /tmp/alpha_broken.mp4
```

Open `/tmp/alpha_broken.mp4` — expect black where transparent should show through.

- [ ] **Step 2: Replace composite_overlay() in build_video.py**

Find lines 293–311 in `build_video.py` and replace the entire function:

```python
def composite_overlay(base_video: str, overlay_webm: str, output_path: str) -> str:
    """Composite a transparent VP9 WebM overlay over a base MP4.

    -vcodec libvpx-vp9 before the WebM input forces FFmpeg to decode the
    alpha plane; without it FFmpeg silently ignores alpha and renders black.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", base_video,
        "-vcodec", "libvpx-vp9",
        "-i", overlay_webm,
        "-filter_complex", "[0:v][1:v]overlay=0:0[v]",
        "-map", "[v]",
        "-map", "0:a?",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "slow",
        "-c:a", "copy",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path,
    ]
    subprocess.run(cmd, check=True, timeout=300)
    return output_path
```

- [ ] **Step 3: Verify the fix works**

Re-run the same composite test:
```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
venv/bin/python3 -c "
from build_video import composite_overlay
composite_overlay('/tmp/test_base.mp4', '/tmp/test_dog_overlay.webm', '/tmp/alpha_fixed.mp4')
print('done')
"
```

Open `/tmp/alpha_fixed.mp4` — the emoji and text should be visible over the black base video. The background should be transparent (black base shows through where alpha=0).

- [ ] **Step 4: Commit**

```bash
git add build_video.py
git commit -m "fix: force VP9 decoder for WebM overlay so alpha channel is not black"
```

---

## Task 2: Create overlay_library.py (Cache-Aware Renderer)

**Files:**
- Create: `overlay_library.py`
- Create: `assets/overlays/.gitkeep` (so directory is tracked)
- Test: `tests/test_overlay_library.py`

This module is the asset library. Given a channel slug, overlay type, and content dict, it:
1. Computes a deterministic hash of the content
2. Returns the cached WebM path if it already exists
3. Otherwise renders via `overlay_renderer.render_overlay()` and saves to `assets/overlays/<channel>/<type>/<hash>.webm`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_overlay_library.py
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from overlay_library import get_or_render_overlay, _content_hash, OverlayRequest


def test_content_hash_is_deterministic():
    """Same content always produces same hash."""
    content = {"hook_text": "Dogs can smell cancer!", "emoji": "🐕", "duration": "3"}
    assert _content_hash(content) == _content_hash(content)


def test_content_hash_differs_for_different_content():
    """Different content produces different hash."""
    a = {"hook_text": "Fact A"}
    b = {"hook_text": "Fact B"}
    assert _content_hash(a) != _content_hash(b)


def test_get_or_render_returns_cached_path(tmp_path):
    """Returns existing file path without calling render_overlay."""
    # Pre-create the cached file
    overlay_dir = tmp_path / "canine-wisdom" / "hook"
    overlay_dir.mkdir(parents=True)
    content = {"{{HOOK_TEXT}}": "Test", "{{EMOJI}}": "🐕", "{{DURATION}}": "3"}
    hash_val = _content_hash(content)
    cached = overlay_dir / f"{hash_val}.webm"
    cached.write_bytes(b"fake webm")

    req = OverlayRequest(
        channel_slug="canine-wisdom",
        template_name="hook",
        placeholders=content,
        width=1080,
        height=1920,
        duration=3.0,
    )

    with patch("overlay_library.OVERLAYS_DIR", tmp_path):
        with patch("overlay_library.render_overlay") as mock_render:
            result = get_or_render_overlay(req)
            mock_render.assert_not_called()

    assert result == str(cached)


def test_get_or_render_calls_render_on_cache_miss(tmp_path):
    """Calls render_overlay when cached file does not exist."""
    content = {"{{HOOK_TEXT}}": "New Fact", "{{EMOJI}}": "🐾", "{{DURATION}}": "3"}
    hash_val = _content_hash(content)
    expected_path = tmp_path / "canine-wisdom" / "hook" / f"{hash_val}.webm"

    req = OverlayRequest(
        channel_slug="canine-wisdom",
        template_name="hook",
        placeholders=content,
        width=1080,
        height=1920,
        duration=3.0,
    )

    def fake_render(config):
        Path(config.output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(config.output_path).write_bytes(b"rendered")
        return config.output_path

    with patch("overlay_library.OVERLAYS_DIR", tmp_path):
        with patch("overlay_library.render_overlay", side_effect=fake_render):
            result = get_or_render_overlay(req)

    assert result == str(expected_path)
    assert expected_path.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
venv/bin/python3 -m pytest tests/test_overlay_library.py -v
```

Expected: `ModuleNotFoundError: No module named 'overlay_library'`

- [ ] **Step 3: Implement overlay_library.py**

```python
# overlay_library.py
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from overlay_renderer import render_overlay, OverlayConfig

OVERLAYS_DIR = Path(__file__).parent / "assets" / "overlays"


@dataclass
class OverlayRequest:
    channel_slug: str       # e.g. "canine-wisdom"
    template_name: str      # e.g. "hook", "lower-third"
    placeholders: dict      # e.g. {"{{HOOK_TEXT}}": "Dogs smell cancer!", "{{EMOJI}}": "🐕"}
    width: int
    height: int
    duration: float


def _content_hash(placeholders: dict) -> str:
    """Deterministic 12-char hash of placeholder content for cache keying."""
    canonical = json.dumps(placeholders, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def get_or_render_overlay(req: OverlayRequest) -> str:
    """
    Return path to a rendered WebM overlay for the given request.
    Renders and caches to assets/overlays/<channel>/<type>/<hash>.webm on first call;
    returns cached path on subsequent calls with identical content.
    """
    cache_key = _content_hash(req.placeholders)
    output_path = OVERLAYS_DIR / req.channel_slug / req.template_name / f"{cache_key}.webm"

    if output_path.exists():
        return str(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    config = OverlayConfig(
        channel_slug=req.channel_slug,
        template_name=req.template_name,
        placeholders=req.placeholders,
        width=req.width,
        height=req.height,
        duration=req.duration,
        output_path=str(output_path),
    )
    render_overlay(config)
    return str(output_path)
```

- [ ] **Step 4: Create the assets/overlays directory**

```bash
mkdir -p assets/overlays
touch assets/overlays/.gitkeep
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
venv/bin/python3 -m pytest tests/test_overlay_library.py -v
```

Expected:
```
tests/test_overlay_library.py::test_content_hash_is_deterministic PASSED
tests/test_overlay_library.py::test_content_hash_differs_for_different_content PASSED
tests/test_overlay_library.py::test_get_or_render_returns_cached_path PASSED
tests/test_overlay_library.py::test_get_or_render_calls_render_on_cache_miss PASSED
```

- [ ] **Step 6: Commit**

```bash
git add overlay_library.py tests/test_overlay_library.py assets/overlays/.gitkeep
git commit -m "feat: add overlay_library with content-hash cache (assets/overlays/)"
```

---

## Task 3: Wire overlay_library into build_video.py

**Files:**
- Modify: `build_video.py:16` (imports)
- Modify: `build_video.py:509-553` (overlay block)

Replace the live `render_overlay()` call in `build_video.py` with `get_or_render_overlay()`. This means if the same hook text was used in a previous run, the WebM is reused instantly; otherwise it renders and caches it.

- [ ] **Step 1: Update the import at the top of build_video.py**

Find line 16:
```python
from overlay_renderer import render_overlay, OverlayConfig
```

Replace with:
```python
from overlay_library import get_or_render_overlay, OverlayRequest
```

(Keep `overlay_renderer` import only if it's used elsewhere in the file — check with `grep -n "render_overlay\|OverlayConfig" build_video.py`. If only used in the overlay block, remove entirely.)

- [ ] **Step 2: Replace the HyperFrames overlay block**

Find lines 509–553 in `build_video.py` (the `# HyperFrames animated hook overlay` block). Replace the entire block with:

```python
    # HyperFrames animated hook overlay — uses asset library (cached per content)
    if script_data:
        hook_text = script_data.get("hook_overlay", "") or script_data.get("hook", "") or script_data.get("hook_text", "")
        if hook_text:
            try:
                composited = final_video.replace(".mp4", "_composited.mp4")

                if channel_slug == "horror-narration":
                    placeholders = {
                        "{{HOOK_TEXT}}": hook_text,
                        "{{SUBTITLE}}": script_data.get("subtitle", ""),
                        "{{DURATION}}": "4",
                    }
                    overlay_duration = 4.0
                else:
                    placeholders = {
                        "{{HOOK_TEXT}}": hook_text,
                        "{{EMOJI}}": script_data.get("emoji", "🐕"),
                        "{{DURATION}}": "3",
                    }
                    overlay_duration = 3.0

                req = OverlayRequest(
                    channel_slug=channel_slug,
                    template_name="hook",
                    placeholders=placeholders,
                    width=1080,
                    height=1920,
                    duration=overlay_duration,
                )
                log("🎨 Getting overlay from asset library...")
                overlay_webm = get_or_render_overlay(req)
                log("🎞️  Compositing overlay onto video...")
                composite_overlay(final_video, overlay_webm, composited)
                os.replace(composited, final_video)
                log("✅ HyperFrames overlay composited!")
            except Exception as overlay_err:
                print(f"[WARNING] HyperFrames overlay failed, continuing without it: {overlay_err}")
```

Note: no `os.unlink(overlay_webm)` — the WebM stays in `assets/overlays/` as the cache.

- [ ] **Step 3: Verify import works**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
venv/bin/python3 -c "import build_video; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Run existing overlay renderer tests**

```bash
venv/bin/python3 -m pytest tests/test_overlay_renderer.py tests/test_overlay_library.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add build_video.py
git commit -m "feat: use overlay_library (cached assets) in build_video instead of live render"
```

---

## Task 4: End-to-End Smoke Test

**No new files — run the full pipeline and verify the overlay is visible (not black).**

- [ ] **Step 1: Run the canine-wisdom pipeline**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
CHANNEL_SLUG=canine-wisdom venv/bin/python3 main.py 2>&1 | tee /tmp/smoke_library.log
```

- [ ] **Step 2: Check that the asset was cached**

```bash
ls -lh assets/overlays/canine-wisdom/hook/
```

Expected: one `.webm` file with a 12-char hex name (e.g. `a3f9e1b2cd4f.webm`), size > 0.

- [ ] **Step 3: Check the log for cache vs render**

```bash
grep -i "overlay\|asset library\|composit" /tmp/smoke_library.log
```

Expected lines like:
```
🎨 Getting overlay from asset library...
🎞️  Compositing overlay onto video...
✅ HyperFrames overlay composited!
```

- [ ] **Step 4: Open the output video and verify overlay is visible**

```bash
ls -lh outputs/final_video.mp4
ffprobe -v error -show_entries stream=codec_name,width,height -of csv outputs/final_video.mp4
```

Visually inspect: the hook text and emoji should be visible over the dog footage in the first 3 seconds — NOT a black box.

- [ ] **Step 5: Run again — verify cache hit (no re-render)**

The second run with the same hook text should log "Getting overlay from asset library..." and skip the HyperFrames render step (much faster, no Node process spawned).

If you want to test cache hit explicitly without a full pipeline run:
```bash
venv/bin/python3 -c "
from overlay_library import get_or_render_overlay, OverlayRequest
import time

req = OverlayRequest(
    channel_slug='canine-wisdom',
    template_name='hook',
    placeholders={'{{HOOK_TEXT}}': 'Test cache hit', '{{EMOJI}}': '🐕', '{{DURATION}}': '3'},
    width=1080, height=1920, duration=3.0,
)

t0 = time.time()
path1 = get_or_render_overlay(req)   # first call: renders
print(f'First call ({time.time()-t0:.1f}s): {path1}')

t0 = time.time()
path2 = get_or_render_overlay(req)   # second call: cache hit
print(f'Second call ({time.time()-t0:.3f}s): {path2}')
assert path1 == path2, 'Cache returned different path!'
print('PASS: cache hit works')
"
```

Expected: first call ~15–20s (renders), second call < 0.01s (instant cache hit).

- [ ] **Step 6: Commit**

```bash
git commit --allow-empty -m "chore: overlay asset library smoke-tested — alpha fix confirmed, cache working"
```

---

## Self-Review

**Spec coverage:**
- ✅ VP9 alpha fix: Task 1 (force `-vcodec libvpx-vp9` before WebM input)
- ✅ Pre-rendered asset library: Task 2 (`overlay_library.py`, `assets/overlays/<channel>/<type>/<hash>.webm`)
- ✅ Video build picks from library: Task 3 (`build_video.py` uses `get_or_render_overlay`)
- ✅ Cache reuse (same content = same hash = instant return): Task 2 logic + Task 4 smoke test
- ✅ Both channels supported: `channel_slug` routing in Task 3 block

**Placeholder scan:** None found.

**Type consistency:**
- `OverlayRequest` defined in Task 2, imported and used in Tasks 3 and 4 — consistent.
- `get_or_render_overlay(req: OverlayRequest) -> str` — same signature throughout.
- `composite_overlay(base_video, overlay_webm, output_path)` — unchanged signature, used in Task 3.
- `_content_hash(placeholders: dict) -> str` — defined Task 2, tested Task 2, not referenced elsewhere.

**Note on `assets/overlays/` gitignore:** The WebM files in `assets/overlays/` are generated artifacts. You may want to add `assets/overlays/**/*.webm` to `.gitignore` to avoid committing rendered video files to git. This is optional — committing them means the cache persists across clones, but at the cost of repo size. Decision left to operator.
