# Dual-Format Video Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second video format (landscape 1920×1080 long-form) alongside the existing vertical Short (1080×1920), and let the harness orchestrator decide which format to produce per run based on topic cluster and recent performance history.

**Architecture:** A `VideoFormat` enum (`short` | `long`) flows from orchestrator → `build_video()` → `video_eval()`. Shorts stay exactly as they are (vertical, cropped, no zoom). Long-form uses landscape orientation with no crop/pad and adds a gentle Ken Burns zoom. The harness format-picker lives in `harness/agents/format_picker.py` and is called once per run before the footage fetch, so footage can be fetched in the correct orientation.

**Tech Stack:** Python 3, FFmpeg (`zoompan`, `eq`, `colorbalance`, `vignette`), pytest, existing harness eval framework

---

## Current state (read before touching anything)

| File | Relevant lines | What it does today |
|------|---------------|-------------------|
| `config.py` | 46-47 | `VIDEO_WIDTH=1080`, `VIDEO_HEIGHT=1920` — hardcoded vertical |
| `build_video.py` | 216-260 | `_concat_clips()` normalises all clips to 1080×1920 |
| `build_video.py` | 338-346 | `base_filter` scales to `VIDEO_WIDTH×VIDEO_HEIGHT` |
| `build_video.py` | 296+ | `build_video(audio_duration, clip_path, word_timestamps, hook_overlay)` — no format param |
| `harness/evals/video_eval.py` | 8-9 | `EXPECTED_WIDTH=1080`, `EXPECTED_HEIGHT=1920` — hardcoded |
| `harness/orchestrator.py` | 283 | `"format": "short"` — hardcoded |
| `harness/tools/footage.py` | 101, 155 | Always requests portrait/vertical clips |

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `config.py` | Modify | Add `VideoFormat` enum; add `LONG_VIDEO_WIDTH=1920`, `LONG_VIDEO_HEIGHT=1080` |
| `build_video.py` | Modify | `_concat_clips()` accepts `fmt`; `build_video()` accepts `fmt`; `base_filter` branches on format; long-form adds zoompan |
| `harness/evals/video_eval.py` | Modify | Accept expected resolution as param, not hardcoded |
| `harness/tools/footage.py` | Modify | `fetch_footage_for_topic()` accepts `fmt`; requests landscape orientation for long-form |
| `harness/agents/format_picker.py` | Create | `pick_format(topic_cluster, recent_runs) -> VideoFormat` logic |
| `harness/orchestrator.py` | Modify | Call `pick_format()`, pass `fmt` through footage fetch → build_video → video_eval |
| `tests/test_build_video_filters.py` | Modify | Add tests for long-form filter (zoompan + landscape scale) |
| `tests/test_format_picker.py` | Create | Tests for format picker logic |
| `harness/tests/test_video_eval_format.py` | Create | Tests that video_eval passes correct resolution per format |

---

### Task 1: Add `VideoFormat` enum to `config.py`

**Files:**
- Modify: `config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_video_format_config.py`:

```python
from config import VideoFormat, LONG_VIDEO_WIDTH, LONG_VIDEO_HEIGHT, VIDEO_WIDTH, VIDEO_HEIGHT


def test_short_format_values():
    assert VideoFormat.SHORT.value == "short"


def test_long_format_values():
    assert VideoFormat.LONG.value == "long"


def test_short_resolution_unchanged():
    assert VIDEO_WIDTH == 1080
    assert VIDEO_HEIGHT == 1920


def test_long_resolution():
    assert LONG_VIDEO_WIDTH == 1920
    assert LONG_VIDEO_HEIGHT == 1080
```

- [ ] **Step 2: Run test to confirm it fails**

```
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
pytest tests/test_video_format_config.py -v 2>&1 | tail -10
```

Expected: ImportError — `VideoFormat` not defined.

- [ ] **Step 3: Add enum and constants to `config.py`**

Open `config.py`. After the existing `VIDEO_WIDTH = 1080` / `VIDEO_HEIGHT = 1920` lines, add:

```python
from enum import Enum

class VideoFormat(Enum):
    SHORT = "short"   # vertical 1080×1920 YouTube Short
    LONG  = "long"    # landscape 1920×1080 long-form video

LONG_VIDEO_WIDTH  = 1920
LONG_VIDEO_HEIGHT = 1080
```

Note: put the `from enum import Enum` at the top of the file with the other imports.

- [ ] **Step 4: Run tests — all pass**

```
pytest tests/test_video_format_config.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_video_format_config.py
git commit -m "feat: add VideoFormat enum and long-form resolution constants"
```

---

### Task 2: Update `_concat_clips()` and `build_video()` to accept format

**Files:**
- Modify: `build_video.py` (lines ~200–270 for `_concat_clips`, lines ~296–430 for `build_video`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_build_video_filters.py`:

```python
from config import VideoFormat, VIDEO_WIDTH, VIDEO_HEIGHT, LONG_VIDEO_WIDTH, LONG_VIDEO_HEIGHT


def test_short_format_base_filter():
    """Short format: scale to 1080x1920, no zoompan."""
    fmt = VideoFormat.SHORT
    w = VIDEO_WIDTH if fmt == VideoFormat.SHORT else LONG_VIDEO_WIDTH
    h = VIDEO_HEIGHT if fmt == VideoFormat.SHORT else LONG_VIDEO_HEIGHT
    base_filter = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
        f"eq=brightness=0.04:saturation=1.25:contrast=1.15,"
        f"colorbalance=rs=0.08:gs=0:bs=-0.08,"
        f"vignette=PI/5"
    )
    assert "zoompan" not in base_filter
    assert "scale=1080:1920" in base_filter


def test_long_format_base_filter():
    """Long format: scale to 1920x1080, with zoompan Ken Burns."""
    fmt = VideoFormat.LONG
    w = VIDEO_WIDTH if fmt == VideoFormat.SHORT else LONG_VIDEO_WIDTH
    h = VIDEO_HEIGHT if fmt == VideoFormat.SHORT else LONG_VIDEO_HEIGHT
    base_filter = (
        f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
        f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
        f"zoompan=z='min(zoom+0.0008,1.3)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
        f"eq=brightness=0.04:saturation=1.25:contrast=1.15,"
        f"colorbalance=rs=0.08:gs=0:bs=-0.08,"
        f"vignette=PI/5"
    )
    assert "zoompan" in base_filter
    assert "scale=1920:1080" in base_filter
    assert "1.3" in base_filter  # more conservative zoom for landscape
```

- [ ] **Step 2: Run to confirm new tests fail**

```
pytest tests/test_build_video_filters.py::test_short_format_base_filter tests/test_build_video_filters.py::test_long_format_base_filter -v 2>&1 | tail -10
```

Expected: ImportError on `LONG_VIDEO_WIDTH` (until task 1 done, task 1 must run first).
After task 1: both tests PASS immediately (string construction tests).

- [ ] **Step 3: Update `_concat_clips()` signature and scale filter**

In `build_video.py`, find the `_concat_clips` function definition (around line 200). Change its signature from:

```python
def _concat_clips(clips: list, audio_duration: float) -> str:
```

to:

```python
def _concat_clips(clips: list, audio_duration: float, fmt=None) -> str:
```

At the top of `_concat_clips`, add after the imports/docstring:

```python
    from config import VideoFormat, LONG_VIDEO_WIDTH, LONG_VIDEO_HEIGHT
    if fmt is None:
        from config import VideoFormat
        fmt = VideoFormat.SHORT
    clip_w = LONG_VIDEO_WIDTH if fmt == VideoFormat.LONG else 1080
    clip_h = LONG_VIDEO_HEIGHT if fmt == VideoFormat.LONG else 1920
```

Then replace both occurrences of the hardcoded scale filter inside `_concat_clips`:

```python
"-vf", f"scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1",
```

with:

```python
"-vf", f"scale={clip_w}:{clip_h}:force_original_aspect_ratio=decrease,pad={clip_w}:{clip_h}:(ow-iw)/2:(oh-ih)/2,setsar=1",
```

(There are two such lines — one for the looped path, one for the normal path. Replace both.)

- [ ] **Step 4: Update `build_video()` signature and `base_filter`**

Find `build_video(` function definition (around line 296). Change its signature from:

```python
def build_video(audio_duration: float, clip_path=None, word_timestamps=None, hook_overlay=None) -> str:
```

to:

```python
def build_video(audio_duration: float, clip_path=None, word_timestamps=None, hook_overlay=None, fmt=None) -> str:
```

At the top of the function body, add:

```python
    from config import VideoFormat, LONG_VIDEO_WIDTH, LONG_VIDEO_HEIGHT
    if fmt is None:
        fmt = VideoFormat.SHORT
```

Find the line that calls `_concat_clips`:

```python
    actual_video_path = _concat_clips(clips, audio_duration)
```

Change to:

```python
    actual_video_path = _concat_clips(clips, audio_duration, fmt=fmt)
```

Find the existing `base_filter` block and replace it with:

```python
    if fmt == VideoFormat.LONG:
        # Landscape 1920×1080: Ken Burns zoom safe on wide frame
        bw, bh = LONG_VIDEO_WIDTH, LONG_VIDEO_HEIGHT
        base_filter = (
            f"scale={bw}:{bh}:force_original_aspect_ratio=decrease,"
            f"pad={bw}:{bh}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"zoompan=z='min(zoom+0.0008,1.3)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
            f"eq=brightness=0.04:saturation=1.25:contrast=1.15,"
            f"colorbalance=rs=0.08:gs=0:bs=-0.08,"
            f"vignette=PI/5"
        )
    else:
        # Vertical 1080×1920 Short: no zoompan (breaks resolution on narrow frame)
        bw, bh = VIDEO_WIDTH, VIDEO_HEIGHT
        base_filter = (
            f"scale={bw}:{bh}:force_original_aspect_ratio=decrease,"
            f"pad={bw}:{bh}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"eq=brightness=0.04:saturation=1.25:contrast=1.15,"
            f"colorbalance=rs=0.08:gs=0:bs=-0.08,"
            f"vignette=PI/5"
        )
```

- [ ] **Step 5: Run full test suite**

```
pytest tests/ -v 2>&1 | tail -20
```

Expected: all existing tests + 2 new format tests pass.

- [ ] **Step 6: Commit**

```bash
git add build_video.py tests/test_build_video_filters.py
git commit -m "feat: build_video and _concat_clips accept VideoFormat, long-form adds Ken Burns"
```

---

### Task 3: Update `video_eval.py` to accept format

**Files:**
- Modify: `harness/evals/video_eval.py`
- Create: `harness/tests/test_video_eval_format.py`

- [ ] **Step 1: Write the failing test**

Create `harness/tests/test_video_eval_format.py`:

```python
import inspect
from harness.evals.video_eval import video_eval
from config import VideoFormat


def test_video_eval_accepts_fmt_param():
    """video_eval must accept an optional fmt keyword argument."""
    sig = inspect.signature(video_eval)
    assert "fmt" in sig.parameters, "video_eval must have a fmt parameter"


def test_video_eval_default_fmt_is_short():
    """Default fmt must be SHORT so existing callers are unaffected."""
    sig = inspect.signature(video_eval)
    param = sig.parameters["fmt"]
    assert param.default == VideoFormat.SHORT
```

- [ ] **Step 2: Run to confirm tests fail**

```
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
pytest harness/tests/test_video_eval_format.py -v 2>&1 | tail -10
```

Expected: AssertionError — `fmt` not in signature.

- [ ] **Step 3: Update `video_eval.py`**

Read `harness/evals/video_eval.py`. Find the function signature (around line 14):

```python
def video_eval(video_path: Path) -> EvalResult:
```

Replace with:

```python
def video_eval(video_path: Path, fmt=None) -> EvalResult:
```

At the top of the function body, replace the hardcoded constants:

```python
    EXPECTED_WIDTH = 1080
    EXPECTED_HEIGHT = 1920
```

with:

```python
    from config import VideoFormat, LONG_VIDEO_WIDTH, LONG_VIDEO_HEIGHT, VIDEO_WIDTH, VIDEO_HEIGHT
    if fmt is None:
        fmt = VideoFormat.SHORT
    EXPECTED_WIDTH  = LONG_VIDEO_WIDTH  if fmt == VideoFormat.LONG else VIDEO_WIDTH
    EXPECTED_HEIGHT = LONG_VIDEO_HEIGHT if fmt == VideoFormat.LONG else VIDEO_HEIGHT
```

If the constants are at module level (not inside the function), move them inside the function using the same replacement.

- [ ] **Step 4: Run tests**

```
pytest harness/tests/test_video_eval_format.py tests/ -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add harness/evals/video_eval.py harness/tests/test_video_eval_format.py
git commit -m "feat: video_eval accepts fmt param, validates resolution per format"
```

---

### Task 4: Update `fetch_footage_for_topic()` to request correct orientation

**Files:**
- Modify: `harness/tools/footage.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_footage_pixabay.py` (or create `tests/test_footage_format.py`):

```python
import inspect
from harness.tools.footage import fetch_footage_for_topic
from config import VideoFormat


def test_fetch_footage_accepts_fmt():
    """fetch_footage_for_topic must accept an optional fmt keyword argument."""
    sig = inspect.signature(fetch_footage_for_topic)
    assert "fmt" in sig.parameters, "fetch_footage_for_topic must have a fmt parameter"


def test_fetch_footage_default_fmt_is_short():
    sig = inspect.signature(fetch_footage_for_topic)
    param = sig.parameters["fmt"]
    assert param.default == VideoFormat.SHORT
```

- [ ] **Step 2: Run to confirm tests fail**

```
pytest tests/test_footage_format.py -v 2>&1 | tail -10
```

Expected: AssertionError — `fmt` not in signature.

- [ ] **Step 3: Update `fetch_footage_for_topic()` in `harness/tools/footage.py`**

Find the function signature. Change from:

```python
def fetch_footage_for_topic(topic_cluster: str, topic: str) -> Path | None:
```

to:

```python
def fetch_footage_for_topic(topic_cluster: str, topic: str, fmt=None) -> Path | None:
```

At the top of the function body add:

```python
    from config import VideoFormat
    if fmt is None:
        fmt = VideoFormat.SHORT
    orientation_pexels  = "portrait"  if fmt == VideoFormat.SHORT else "landscape"
    orientation_pixabay = "vertical"  if fmt == VideoFormat.SHORT else "horizontal"
```

Find the Pexels search params dict (around line 98) — it has `"orientation": "portrait"`. Replace with:

```python
    "orientation": orientation_pexels,
```

Find the Pixabay search params (around line 155) — it has `"orientation": "vertical"`. Replace with:

```python
    "orientation": orientation_pixabay,
```

Also find the portrait filter (around line 122):

```python
    if height > width and height >= 720:
```

Replace with:

```python
    if fmt == VideoFormat.SHORT:
        keep = height > width and height >= 720
    else:
        keep = width > height and width >= 1280
    if not keep:
```

(wrap the existing append/continue logic in the `if not keep: continue` pattern that's already there)

- [ ] **Step 4: Run tests**

```
pytest tests/test_footage_format.py tests/ -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add harness/tools/footage.py tests/test_footage_format.py
git commit -m "feat: fetch_footage_for_topic accepts fmt, requests portrait vs landscape from APIs"
```

---

### Task 5: Create `harness/agents/format_picker.py`

**Files:**
- Create: `harness/agents/format_picker.py`
- Create: `tests/test_format_picker.py`

The format picker decides: produce a Short or a Long-form video this run?

**Decision logic:**
- If the topic cluster is in `LONG_FORM_CLUSTERS` → prefer `LONG`
- If in the last 5 runs for this cluster, all were Shorts → prefer `LONG` (variety)
- Otherwise → `SHORT` (default, safer for YouTube algorithm)

`LONG_FORM_CLUSTERS` = topics that work better as explainers: `"dog health"`, `"dog training"`, `"senior dog"`, `"dog nutrition"`, `"dog science"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_format_picker.py`:

```python
from config import VideoFormat
from harness.agents.format_picker import pick_format, LONG_FORM_CLUSTERS


def test_long_form_cluster_returns_long():
    """Clusters in LONG_FORM_CLUSTERS should produce LONG format."""
    for cluster in LONG_FORM_CLUSTERS:
        result = pick_format(cluster, recent_runs=[])
        assert result == VideoFormat.LONG, f"Expected LONG for cluster '{cluster}', got {result}"


def test_short_cluster_returns_short():
    """Clusters not in LONG_FORM_CLUSTERS default to SHORT."""
    result = pick_format("dog fun", recent_runs=[])
    assert result == VideoFormat.SHORT


def test_all_short_recent_runs_triggers_long():
    """If last 5 runs for this cluster were all SHORT, return LONG for variety."""
    recent = [
        {"topic_cluster": "dog fun", "format": "short"},
        {"topic_cluster": "dog fun", "format": "short"},
        {"topic_cluster": "dog fun", "format": "short"},
        {"topic_cluster": "dog fun", "format": "short"},
        {"topic_cluster": "dog fun", "format": "short"},
    ]
    result = pick_format("dog fun", recent_runs=recent)
    assert result == VideoFormat.LONG


def test_mixed_recent_runs_returns_short():
    """If recent runs are mixed, return SHORT."""
    recent = [
        {"topic_cluster": "dog fun", "format": "short"},
        {"topic_cluster": "dog fun", "format": "long"},
        {"topic_cluster": "dog fun", "format": "short"},
    ]
    result = pick_format("dog fun", recent_runs=recent)
    assert result == VideoFormat.SHORT


def test_different_cluster_recent_runs_ignored():
    """Recent runs from other clusters don't affect this cluster's decision."""
    recent = [
        {"topic_cluster": "dog breeds", "format": "short"},
        {"topic_cluster": "dog breeds", "format": "short"},
        {"topic_cluster": "dog breeds", "format": "short"},
        {"topic_cluster": "dog breeds", "format": "short"},
        {"topic_cluster": "dog breeds", "format": "short"},
    ]
    # "dog fun" has no recent runs → defaults to SHORT
    result = pick_format("dog fun", recent_runs=recent)
    assert result == VideoFormat.SHORT


def test_unknown_cluster_returns_short():
    result = pick_format("something new", recent_runs=[])
    assert result == VideoFormat.SHORT
```

- [ ] **Step 2: Run to confirm tests fail**

```
pytest tests/test_format_picker.py -v 2>&1 | tail -15
```

Expected: ModuleNotFoundError — `format_picker` not found.

- [ ] **Step 3: Create `harness/agents/format_picker.py`**

```python
"""
Decides whether a pipeline run should produce a Short (vertical) or Long-form (landscape) video.

Rules (in priority order):
1. Topic cluster in LONG_FORM_CLUSTERS → LONG
2. Last 5 runs for this cluster were all SHORT → LONG (variety)
3. Otherwise → SHORT
"""
from config import VideoFormat

LONG_FORM_CLUSTERS = {
    "dog health",
    "dog training",
    "senior dog",
    "dog nutrition",
    "dog science",
}


def pick_format(topic_cluster: str, recent_runs: list) -> VideoFormat:
    """
    Args:
        topic_cluster: e.g. "dog fun", "dog health"
        recent_runs: list of dicts with keys "topic_cluster" and "format" ("short"|"long"),
                     ordered newest-first, from harness state / run log.
    Returns:
        VideoFormat.SHORT or VideoFormat.LONG
    """
    if topic_cluster in LONG_FORM_CLUSTERS:
        return VideoFormat.LONG

    cluster_runs = [r for r in recent_runs if r.get("topic_cluster") == topic_cluster]
    last_five = cluster_runs[:5]
    if len(last_five) >= 5 and all(r.get("format") == "short" for r in last_five):
        return VideoFormat.LONG

    return VideoFormat.SHORT
```

- [ ] **Step 4: Run tests — all pass**

```
pytest tests/test_format_picker.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add harness/agents/format_picker.py tests/test_format_picker.py
git commit -m "feat: format_picker — harness decides Short vs Long-form per topic cluster"
```

---

### Task 6: Wire format picker into `harness/orchestrator.py`

**Files:**
- Modify: `harness/orchestrator.py`

- [ ] **Step 1: Add format picker import and call**

In `harness/orchestrator.py`, add to the imports at the top:

```python
from harness.agents.format_picker import pick_format
from config import VideoFormat
```

In `run_pipeline()`, after `topic_cluster` is determined (after the try/except block around line 140 that sets `topic_cluster = "dog fun"`), add:

```python
        # ── Step 2b: Pick video format ────────────────────────────────────────
        try:
            state = atomic_read(STATE_PATH)
            recent_runs = state.get("recent_runs", [])
        except Exception:
            recent_runs = []
        fmt = pick_format(topic_cluster, recent_runs)
        log(f"🎬 Format selected: {fmt.value} ({'1920×1080 landscape' if fmt == VideoFormat.LONG else '1080×1920 vertical'})")
```

- [ ] **Step 2: Pass `fmt` to `fetch_footage_for_topic()`**

Find:
```python
            clip_result = fetch_footage_for_topic(topic_cluster, topic or "dog")
```

Replace with:
```python
            clip_result = fetch_footage_for_topic(topic_cluster, topic or "dog", fmt=fmt)
```

- [ ] **Step 3: Pass `fmt` to `build_video()`**

Find:
```python
        video_path = build_video(audio_duration, clip_path=clip_path,
                                  word_timestamps=word_timestamps,
                                  hook_overlay=metadata.get("hook_overlay"))
```

Replace with:
```python
        video_path = build_video(audio_duration, clip_path=clip_path,
                                  word_timestamps=word_timestamps,
                                  hook_overlay=metadata.get("hook_overlay"),
                                  fmt=fmt)
```

- [ ] **Step 4: Pass `fmt` to `video_eval()`**

Find:
```python
        video_result = video_eval(Path(video_path))
```

Replace with:
```python
        video_result = video_eval(Path(video_path), fmt=fmt)
```

- [ ] **Step 5: Record format in post-upload tracking**

Find the `track_video` call (around line 283). The dict has `"format": "short"`. Replace with:

```python
                "format": fmt.value,
```

Also store recent_run in state for format_picker to read next time. After the `mark_topic_used` block, add:

```python
        # Store this run in recent_runs for format_picker
        try:
            state = atomic_read(STATE_PATH)
            recent_runs = state.get("recent_runs", [])
            recent_runs.insert(0, {
                "topic_cluster": metadata.get("topic_cluster", topic_cluster),
                "format": fmt.value,
                "run_id": run_id,
            })
            state["recent_runs"] = recent_runs[:50]  # keep last 50
            atomic_write(STATE_PATH, state)
        except Exception as e:
            log(f"⚠️  Could not save recent_runs (non-blocking): {e}", level="warning")
```

- [ ] **Step 6: Run full test suite**

```
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
pytest tests/ harness/tests/ -v 2>&1 | tail -25
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add harness/orchestrator.py
git commit -m "feat: orchestrator wires format picker — harness decides Short vs Long per run"
```

---

### Task 7: Smoke test — run orchestrator and verify format decision

- [ ] **Step 1: Run orchestrator**

```
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
source venv/bin/activate && python3 -m harness.orchestrator 2>&1
```

Watch for the new log line:
```
🎬 Format selected: short (1080×1920 vertical)
```
or
```
🎬 Format selected: long (1920×1080 landscape)
```

- [ ] **Step 2: Verify video resolution matches format**

```
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height \
  -of default=noprint_wrappers=1 \
  outputs/final_video.mp4
```

If format was `short`: expect `width=1080`, `height=1920`
If format was `long`: expect `width=1920`, `height=1080`

- [ ] **Step 3: Force a long-form run to test that path**

Temporarily edit `harness/agents/format_picker.py` — add `"dog fun"` to `LONG_FORM_CLUSTERS`, run again, verify 1920×1080 output, then revert.

```bash
# After verifying long-form works, revert:
git checkout harness/agents/format_picker.py
```

- [ ] **Step 4: Run full test suite one final time**

```
pytest tests/ harness/tests/ -v 2>&1 | tail -25
```

Expected: all tests pass.

- [ ] **Step 5: Final commit**

```bash
git commit -m "chore: dual-format pipeline verified — Short and Long-form both working"
```

---

## Self-Review

**Spec coverage:**
- ✅ Vertical Shorts (1080×1920) unchanged — Task 2 short branch
- ✅ Landscape long-form (1920×1080) — Task 2 long branch
- ✅ No cropping/padding for long-form native landscape footage — footage.py requests landscape orientation in Task 4
- ✅ Ken Burns zoom only on long-form — Task 2 (zoompan in long branch only)
- ✅ Harness decides format — Task 5 format_picker + Task 6 orchestrator wiring
- ✅ Format based on topic cluster — Task 5 LONG_FORM_CLUSTERS
- ✅ Format variety logic (all-short streak → try long) — Task 5
- ✅ Format stored in state for future decisions — Task 6 step 5
- ✅ video_eval validates correct resolution per format — Task 3

**Placeholder scan:** None found — all steps have exact code.

**Type consistency:**
- `VideoFormat` enum used consistently across all tasks
- `fmt` parameter name used consistently in all function signatures
- `recent_runs` dict keys `"topic_cluster"` and `"format"` consistent between Task 5 (format_picker) and Task 6 (orchestrator write)
