# HyperFrames Overlay Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate HyperFrames (HTML-to-video renderer) into the Python pipeline so both channels can use animated overlays — emoji, styled text, shapes, lower-thirds, and callout boxes — rendered as transparent WebM/PNG sequences and composited by FFmpeg on top of existing video.

**Architecture:** HyperFrames runs as a Node.js subprocess called from Python. Python builds an HTML template per video (populated with script data: hook text, channel branding, emojis), HyperFrames renders it to a transparent `overlay.webm`, then FFmpeg composites it over the footage+audio output. This keeps the entire Python orchestration unchanged — we only add a pre-composite step.

**Tech Stack:** Node.js 22+, `@hyperframes/producer`, FFmpeg (already present), Python `subprocess`, Jinja2 for HTML templating.

---

## Scope

Two independent subsystems are created and then wired together:

1. **HyperFrames renderer** — Node.js project with HTML templates per channel, CLI wrapper
2. **Python bridge** — `overlay_renderer.py` calls the renderer subprocess; `build_video.py` consumes the output

Each task produces testable, working code on its own.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `hyperframes/package.json` | Node deps for `@hyperframes/producer` |
| Create | `hyperframes/render.js` | CLI: `node render.js --template <path> --output <path>` |
| Create | `hyperframes/templates/canine-wisdom/hook.html` | Dog channel hook overlay (animated title + emoji) |
| Create | `hyperframes/templates/canine-wisdom/lower-third.html` | Dog channel lower-third callout box |
| Create | `hyperframes/templates/horror-narration/hook.html` | Horror channel hook overlay (dark, glitch style) |
| Create | `hyperframes/templates/horror-narration/lower-third.html` | Horror channel lower-third |
| Create | `overlay_renderer.py` | Python: renders HTML template via Node subprocess, returns path to overlay WebM |
| Modify | `build_video.py` | Add composite step: layer overlay WebM over final video before encoding |
| Modify | `channel_config.py` | Add `overlay_templates` dict mapping channel slug → template paths |
| Create | `tests/test_overlay_renderer.py` | Unit tests for overlay_renderer.py |

---

## Task 1: Set Up HyperFrames Node Project

**Files:**
- Create: `hyperframes/package.json`
- Create: `hyperframes/render.js`

- [ ] **Step 1: Install Node.js 22+**

Run:
```bash
node --version
```
Expected: `v22.x.x` or higher. If not, install via `nvm install 22 && nvm use 22`.

- [ ] **Step 2: Write package.json**

```json
{
  "name": "hyperframes-renderer",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "render": "node render.js"
  },
  "dependencies": {
    "@hyperframes/producer": "latest"
  }
}
```

Save to `hyperframes/package.json`.

- [ ] **Step 3: Install dependencies**

```bash
cd hyperframes && npm install
```

Expected: `node_modules/@hyperframes/producer` directory created, no errors.

- [ ] **Step 4: Write render.js**

```js
// render.js — CLI wrapper: node render.js --template <html_path> --output <webm_path> --width 1080 --height 1920 --duration 5
import { produce } from '@hyperframes/producer';
import { parseArgs } from 'node:util';
import { readFileSync } from 'node:fs';

const { values } = parseArgs({
  options: {
    template: { type: 'string' },
    output:   { type: 'string' },
    width:    { type: 'string', default: '1080' },
    height:   { type: 'string', default: '1920' },
    duration: { type: 'string', default: '5' },
  }
});

if (!values.template || !values.output) {
  console.error('Usage: node render.js --template <path> --output <path>');
  process.exit(1);
}

const html = readFileSync(values.template, 'utf8');

await produce({
  html,
  output: values.output,
  width:  parseInt(values.width),
  height: parseInt(values.height),
  duration: parseFloat(values.duration),
  codec: 'vp9',
  transparent: true,
});

console.log('OK: ' + values.output);
```

Save to `hyperframes/render.js`.

- [ ] **Step 5: Smoke-test render.js with a minimal HTML**

```bash
mkdir -p /tmp/hf_test
cat > /tmp/hf_test/test.html << 'EOF'
<!DOCTYPE html>
<html>
<body style="margin:0;background:transparent;">
  <div data-start="0s" data-duration="3s"
       style="position:absolute;top:100px;left:50px;font-size:80px;color:yellow;">
    🐕 Hello Dog
  </div>
</body>
</html>
EOF

node hyperframes/render.js \
  --template /tmp/hf_test/test.html \
  --output /tmp/hf_test/out.webm \
  --width 1080 --height 1920 --duration 3
```

Expected: `OK: /tmp/hf_test/out.webm` printed, file exists ~200KB+.

- [ ] **Step 6: Commit**

```bash
git add hyperframes/package.json hyperframes/package-lock.json hyperframes/render.js
git commit -m "feat: add HyperFrames Node renderer CLI"
```

---

## Task 2: Dog Channel HTML Templates

**Files:**
- Create: `hyperframes/templates/canine-wisdom/hook.html`
- Create: `hyperframes/templates/canine-wisdom/lower-third.html`

These templates use `{{HOOK_TEXT}}`, `{{EMOJI}}`, `{{CALLOUT}}` as literal placeholder strings that Python will `str.replace()` before writing to a temp file.

- [ ] **Step 1: Write hook.html for canine-wisdom**

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: transparent; width: 1080px; height: 1920px; overflow: hidden; font-family: 'Impact', sans-serif; }
  .hook-wrap {
    position: absolute;
    top: 140px;
    left: 0; right: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
  }
  .emoji {
    font-size: 96px;
    line-height: 1;
    opacity: 0;
    transform: scale(0.5);
    animation: popIn 0.4s 0.1s ease-out forwards;
  }
  .hook-text {
    font-size: 68px;
    font-weight: 900;
    color: #fff;
    text-align: center;
    padding: 0 60px;
    text-shadow: 4px 4px 0 #000, -4px -4px 0 #000, 4px -4px 0 #000, -4px 4px 0 #000;
    opacity: 0;
    transform: translateY(30px);
    animation: slideUp 0.5s 0.3s ease-out forwards;
  }
  @keyframes popIn {
    to { opacity: 1; transform: scale(1); }
  }
  @keyframes slideUp {
    to { opacity: 1; transform: translateY(0); }
  }
</style>
</head>
<body>
  <div class="hook-wrap" data-start="0s" data-duration="{{DURATION}}s">
    <div class="emoji">{{EMOJI}}</div>
    <div class="hook-text">{{HOOK_TEXT}}</div>
  </div>
</body>
</html>
```

Save to `hyperframes/templates/canine-wisdom/hook.html`.

- [ ] **Step 2: Write lower-third.html for canine-wisdom**

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: transparent; width: 1080px; height: 1920px; overflow: hidden; font-family: 'Arial Rounded MT Bold', 'Arial', sans-serif; }
  .lower {
    position: absolute;
    bottom: 320px;
    left: 60px; right: 60px;
    background: rgba(255, 165, 0, 0.88);
    border-radius: 20px;
    padding: 24px 36px;
    display: flex;
    align-items: center;
    gap: 20px;
    opacity: 0;
    transform: translateX(-40px);
    animation: slideRight 0.4s 0.1s ease-out forwards;
  }
  .lower-icon { font-size: 52px; flex-shrink: 0; }
  .lower-text {
    font-size: 38px;
    font-weight: 700;
    color: #1a1a1a;
    line-height: 1.3;
  }
  @keyframes slideRight {
    to { opacity: 1; transform: translateX(0); }
  }
</style>
</head>
<body>
  <div class="lower" data-start="{{START}}s" data-duration="{{DURATION}}s">
    <div class="lower-icon">{{ICON}}</div>
    <div class="lower-text">{{CALLOUT}}</div>
  </div>
</body>
</html>
```

Save to `hyperframes/templates/canine-wisdom/lower-third.html`.

- [ ] **Step 3: Verify hook template renders**

```bash
cat > /tmp/hf_dog_test.html << 'EOF'
$(sed 's/{{EMOJI}}/🐕/g; s/{{HOOK_TEXT}}/Did you know this about dogs?/g; s/{{DURATION}}/3/g' hyperframes/templates/canine-wisdom/hook.html)
EOF

node hyperframes/render.js \
  --template /tmp/hf_dog_test.html \
  --output /tmp/hf_dog_hook.webm \
  --width 1080 --height 1920 --duration 3
```

Expected: `OK: /tmp/hf_dog_hook.webm`, file ~200KB+.

Open `/tmp/hf_dog_hook.webm` in a media player to confirm animated text on transparent background.

- [ ] **Step 4: Commit**

```bash
git add hyperframes/templates/canine-wisdom/
git commit -m "feat: add dog channel HyperFrames HTML templates"
```

---

## Task 3: Horror Channel HTML Templates

**Files:**
- Create: `hyperframes/templates/horror-narration/hook.html`
- Create: `hyperframes/templates/horror-narration/lower-third.html`

- [ ] **Step 1: Write hook.html for horror-narration**

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: transparent; width: 1080px; height: 1920px; overflow: hidden; font-family: 'Georgia', serif; }
  .hook-wrap {
    position: absolute;
    top: 120px;
    left: 0; right: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
  }
  .horror-text {
    font-size: 62px;
    font-weight: 900;
    font-style: italic;
    color: #e00;
    text-align: center;
    padding: 0 60px;
    text-shadow: 0 0 20px rgba(220,0,0,0.8), 3px 3px 0 #000, -3px -3px 0 #000;
    opacity: 0;
    animation: flicker 0.6s 0.2s ease-in forwards;
    letter-spacing: 2px;
  }
  .sub-text {
    font-size: 36px;
    color: #ccc;
    text-align: center;
    padding: 0 80px;
    text-shadow: 2px 2px 0 #000;
    opacity: 0;
    animation: fadeIn 0.5s 0.7s ease-in forwards;
  }
  @keyframes flicker {
    0%   { opacity: 0; transform: scaleX(1.05); }
    30%  { opacity: 0.8; }
    50%  { opacity: 0.3; }
    70%  { opacity: 0.9; }
    100% { opacity: 1; transform: scaleX(1); }
  }
  @keyframes fadeIn {
    to { opacity: 1; }
  }
</style>
</head>
<body>
  <div class="hook-wrap" data-start="0s" data-duration="{{DURATION}}s">
    <div class="horror-text">{{HOOK_TEXT}}</div>
    <div class="sub-text">{{SUBTITLE}}</div>
  </div>
</body>
</html>
```

Save to `hyperframes/templates/horror-narration/hook.html`.

- [ ] **Step 2: Write lower-third.html for horror-narration**

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: transparent; width: 1080px; height: 1920px; overflow: hidden; font-family: 'Georgia', serif; }
  .lower {
    position: absolute;
    bottom: 300px;
    left: 60px; right: 60px;
    background: rgba(10, 0, 0, 0.85);
    border-left: 6px solid #e00;
    border-radius: 6px;
    padding: 20px 30px;
    opacity: 0;
    animation: fadeSlide 0.4s 0.1s ease-out forwards;
  }
  .lower-text {
    font-size: 36px;
    color: #ddd;
    font-style: italic;
    line-height: 1.4;
    text-shadow: 1px 1px 3px rgba(200,0,0,0.5);
  }
  @keyframes fadeSlide {
    0%  { opacity: 0; transform: translateY(10px); }
    100%{ opacity: 1; transform: translateY(0); }
  }
</style>
</head>
<body>
  <div class="lower" data-start="{{START}}s" data-duration="{{DURATION}}s">
    <div class="lower-text">{{CALLOUT}}</div>
  </div>
</body>
</html>
```

Save to `hyperframes/templates/horror-narration/lower-third.html`.

- [ ] **Step 3: Verify horror hook template renders**

```bash
cat > /tmp/hf_horror_test.html << 'EOF'
$(sed 's/{{HOOK_TEXT}}/Something is watching you/g; s/{{SUBTITLE}}/A true story from r\/nosleep/g; s/{{DURATION}}/4/g' hyperframes/templates/horror-narration/hook.html)
EOF

node hyperframes/render.js \
  --template /tmp/hf_horror_test.html \
  --output /tmp/hf_horror_hook.webm \
  --width 1080 --height 1920 --duration 4
```

Expected: `OK: /tmp/hf_horror_hook.webm`, flickering red text on transparent background.

- [ ] **Step 4: Commit**

```bash
git add hyperframes/templates/horror-narration/
git commit -m "feat: add horror channel HyperFrames HTML templates"
```

---

## Task 4: Python Overlay Renderer

**Files:**
- Create: `overlay_renderer.py`
- Create: `tests/test_overlay_renderer.py`

This module is the Python↔Node bridge. It fills template placeholders, writes a temp HTML file, calls `node render.js`, and returns the path to the rendered WebM.

- [ ] **Step 1: Write failing test**

```python
# tests/test_overlay_renderer.py
import os
import pytest
from unittest.mock import patch, MagicMock
from overlay_renderer import render_overlay, OverlayConfig

def test_render_overlay_returns_existing_file(tmp_path):
    """render_overlay must return a path to a file that exists."""
    fake_webm = tmp_path / "overlay.webm"
    fake_webm.write_bytes(b"fake")

    config = OverlayConfig(
        channel_slug="canine-wisdom",
        template_name="hook",
        placeholders={"{{HOOK_TEXT}}": "Test hook", "{{EMOJI}}": "🐕", "{{DURATION}}": "3"},
        width=1080,
        height=1920,
        duration=3.0,
        output_path=str(fake_webm),
    )

    with patch("overlay_renderer._call_node_renderer", return_value=0):
        result = render_overlay(config)

    assert os.path.exists(result)
    assert result.endswith(".webm")


def test_render_overlay_raises_on_nonzero_exit(tmp_path):
    config = OverlayConfig(
        channel_slug="canine-wisdom",
        template_name="hook",
        placeholders={"{{HOOK_TEXT}}": "Test", "{{EMOJI}}": "🐕", "{{DURATION}}": "3"},
        width=1080,
        height=1920,
        duration=3.0,
        output_path=str(tmp_path / "overlay.webm"),
    )
    with patch("overlay_renderer._call_node_renderer", return_value=1):
        with pytest.raises(RuntimeError, match="HyperFrames render failed"):
            render_overlay(config)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_overlay_renderer.py -v
```

Expected: `ModuleNotFoundError: No module named 'overlay_renderer'`

- [ ] **Step 3: Implement overlay_renderer.py**

```python
# overlay_renderer.py
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

HYPERFRAMES_DIR = Path(__file__).parent / "hyperframes"
TEMPLATES_DIR = HYPERFRAMES_DIR / "templates"


@dataclass
class OverlayConfig:
    channel_slug: str          # e.g. "canine-wisdom"
    template_name: str         # e.g. "hook" or "lower-third"
    placeholders: dict         # e.g. {"{{HOOK_TEXT}}": "Did you know?", "{{EMOJI}}": "🐕"}
    width: int
    height: int
    duration: float
    output_path: str


def render_overlay(config: OverlayConfig) -> str:
    """
    Fill template placeholders, render via HyperFrames Node CLI,
    return path to output WebM. Raises RuntimeError on render failure.
    """
    template_path = TEMPLATES_DIR / config.channel_slug / f"{config.template_name}.html"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    html = template_path.read_text(encoding="utf-8")
    for placeholder, value in config.placeholders.items():
        html = html.replace(placeholder, str(value))

    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False, encoding="utf-8") as f:
        f.write(html)
        tmp_html = f.name

    try:
        exit_code = _call_node_renderer(
            template=tmp_html,
            output=config.output_path,
            width=config.width,
            height=config.height,
            duration=config.duration,
        )
        if exit_code != 0:
            raise RuntimeError(f"HyperFrames render failed (exit {exit_code}): {config.output_path}")
    finally:
        os.unlink(tmp_html)

    return config.output_path


def _call_node_renderer(template: str, output: str, width: int, height: int, duration: float) -> int:
    render_js = HYPERFRAMES_DIR / "render.js"
    result = subprocess.run(
        ["node", str(render_js),
         "--template", template,
         "--output", output,
         "--width", str(width),
         "--height", str(height),
         "--duration", str(duration)],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    return result.returncode
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_overlay_renderer.py -v
```

Expected:
```
tests/test_overlay_renderer.py::test_render_overlay_returns_existing_file PASSED
tests/test_overlay_renderer.py::test_render_overlay_raises_on_nonzero_exit PASSED
```

- [ ] **Step 5: Commit**

```bash
git add overlay_renderer.py tests/test_overlay_renderer.py
git commit -m "feat: add Python overlay_renderer bridge for HyperFrames"
```

---

## Task 5: Wire Overlay Into channel_config.py

**Files:**
- Modify: `channel_config.py`

- [ ] **Step 1: Read current channel_config.py**

```bash
cat channel_config.py
```

Note the existing structure — specifically the dict/dataclass returned per channel.

- [ ] **Step 2: Add overlay_templates field**

In the channel config loader, add `overlay_templates` to the returned config (dict or dataclass — match whatever pattern is already used). Add it right after existing fields. Example if dict-based:

```python
# Inside the function that builds channel config from settings.json:
config["overlay_templates"] = {
    "hook": settings.get("overlay_hook_template", "hook"),
    "lower_third": settings.get("overlay_lower_third_template", "lower-third"),
}
```

This lets individual channels override template names in `settings.json` without code changes.

- [ ] **Step 3: Verify channel_config loads without errors**

```bash
python -c "from channel_config import load_channel_config; c = load_channel_config('canine-wisdom'); print(c)"
```

Expected: Config printed with `overlay_templates` key present.

```bash
python -c "from channel_config import load_channel_config; c = load_channel_config('horror-narration'); print(c)"
```

Expected: Same for horror channel.

- [ ] **Step 4: Commit**

```bash
git add channel_config.py
git commit -m "feat: add overlay_templates to channel config"
```

---

## Task 6: Composite Overlay in build_video.py

**Files:**
- Modify: `build_video.py`

This is the core integration. After FFmpeg produces `final_video.mp4` (footage + audio + ASS captions), we:
1. Call `render_overlay()` to produce `hook_overlay.webm`
2. Run FFmpeg again to composite the WebM over the video using `overlay` filter

- [ ] **Step 1: Read build_video.py to find the final ffmpeg call**

```bash
grep -n "ffmpeg\|output\|final" build_video.py | head -40
```

Note the exact line where the main FFmpeg command is built and the output path.

- [ ] **Step 2: Add import at top of build_video.py**

Find the imports block and add:
```python
from overlay_renderer import render_overlay, OverlayConfig
```

- [ ] **Step 3: Add `composite_overlay()` function**

Add this function before the main `build_video()` function in `build_video.py`:

```python
def composite_overlay(base_video: str, overlay_webm: str, output_path: str) -> str:
    """
    Composite a transparent WebM overlay over a base MP4.
    Returns output_path on success. Raises subprocess.CalledProcessError on failure.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", base_video,
        "-i", overlay_webm,
        "-filter_complex", "[0:v][1:v]overlay=0:0[v]",
        "-map", "[v]",
        "-map", "0:a",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "slow",
        "-c:a", "copy",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    subprocess.run(cmd, check=True)
    return output_path
```

- [ ] **Step 4: Call overlay rendering after main video build**

Find the place in `build_video()` where the final output MP4 path is returned (after all FFmpeg filters). After that point, add:

```python
    # --- HyperFrames overlay ---
    script_data = kwargs.get("script_data", {})   # hook_text, emoji passed from generate_script
    channel_slug = kwargs.get("channel_slug", "canine-wisdom")

    hook_text = script_data.get("hook", "")
    emoji = script_data.get("emoji", "🐕") if channel_slug == "canine-wisdom" else ""

    if hook_text:
        overlay_webm = output_path.replace(".mp4", "_overlay.webm")
        composited = output_path.replace(".mp4", "_composited.mp4")

        placeholders = {
            "{{HOOK_TEXT}}": hook_text,
            "{{EMOJI}}": emoji,
            "{{DURATION}}": "3",
        }
        if channel_slug == "horror-narration":
            placeholders = {
                "{{HOOK_TEXT}}": hook_text,
                "{{SUBTITLE}}": script_data.get("subtitle", ""),
                "{{DURATION}}": "4",
            }

        overlay_cfg = OverlayConfig(
            channel_slug=channel_slug,
            template_name="hook",
            placeholders=placeholders,
            width=1080,
            height=1920,
            duration=float(placeholders.get("{{DURATION}}", "3")),
            output_path=overlay_webm,
        )
        render_overlay(overlay_cfg)
        composite_overlay(output_path, overlay_webm, composited)
        os.replace(composited, output_path)   # overwrite original with composited
        os.unlink(overlay_webm)
    # --- end HyperFrames overlay ---
```

- [ ] **Step 5: Verify build_video.py imports and parses cleanly**

```bash
python -c "import build_video; print('OK')"
```

Expected: `OK` with no import errors.

- [ ] **Step 6: Commit**

```bash
git add build_video.py
git commit -m "feat: composite HyperFrames overlay in build_video pipeline"
```

---

## Task 7: End-to-End Smoke Test

**No new files — running the full pipeline.**

- [ ] **Step 1: Run pipeline for canine-wisdom in dry-run / test mode**

```bash
python main.py --channel canine-wisdom --dry-run 2>&1 | tail -30
```

If no `--dry-run` flag exists, run normally and monitor output:

```bash
python main.py --channel canine-wisdom 2>&1 | tee /tmp/smoke_test.log
```

- [ ] **Step 2: Verify overlay was created and composited**

```bash
grep -i "overlay\|HyperFrames\|webm\|composited" /tmp/smoke_test.log
```

Expected: Lines showing `OK: ...overlay.webm` and the composite step.

- [ ] **Step 3: Inspect final video**

Open the output MP4 in a media player:
```bash
ls -lh outputs/
```

Confirm: animated hook text/emoji appears in the first 3 seconds over the dog footage.

- [ ] **Step 4: Run pipeline for horror-narration**

```bash
python main.py --channel horror-narration 2>&1 | tee /tmp/smoke_horror.log
grep -i "overlay\|HyperFrames\|webm" /tmp/smoke_horror.log
```

Confirm: flickering red horror hook text appears in the first 4 seconds.

- [ ] **Step 5: Commit final smoke-test pass note**

```bash
git commit --allow-empty -m "chore: HyperFrames overlay smoke-tested on both channels"
```

---

## Self-Review

**Spec coverage:**
- ✅ HyperFrames Node project created (Task 1)
- ✅ Dog channel templates: hook + lower-third (Task 2)
- ✅ Horror channel templates: hook + lower-third (Task 3)
- ✅ Python bridge with error handling and tests (Task 4)
- ✅ Channel config extension (Task 5)
- ✅ FFmpeg compositing wired (Task 6)
- ✅ End-to-end smoke test (Task 7)
- ✅ Lower-third templates created but not wired — lower-thirds can be triggered manually via `render_overlay()` with `template_name="lower-third"` once the hook integration is stable

**Placeholder scan:** None found — all steps have concrete code blocks.

**Type consistency:** `OverlayConfig` defined in Task 4 used consistently in Tasks 6 and 7. `composite_overlay()` defined in Task 6, called in same task. No inconsistencies.

---

## Notes on Lower-Thirds

The lower-third templates are created in Tasks 2 and 3 but not automatically triggered in Task 6 (to keep the scope manageable). Once the hook overlay is working, lower-thirds can be added by:
1. Extending the `script_data` from `generate_script.py` to include a `callout` field
2. Rendering `lower-third` template alongside `hook` template
3. Compositing both in a single FFmpeg `filter_complex` with two overlay inputs stacked

This is a natural follow-on task.
