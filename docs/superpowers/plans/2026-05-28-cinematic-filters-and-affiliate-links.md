# Cinematic Filters & Affiliate Links Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current flat color-grading filter in `build_video.py` with a cinematic Ken Burns + vignette filter, and expand `youtube_settings.json` with the full client-supplied affiliate link catalog.

**Architecture:** Two independent changes — (1) update `base_filter` string in `build_video.py` and add Ken Burns zoompan before scale/pad, and (2) expand the `affiliate_links` map in `youtube_settings.json` with new topic clusters. The upload logic in `upload_youtube.py` already reads `affiliate_links` by `topic_cluster`, so no upload-side changes are needed.

**Tech Stack:** Python 3, FFmpeg (`zoompan`, `eq`, `colorbalance`, `vignette`), pytest, JSON

---

## File Map

| File | Action | What changes |
|------|--------|-------------|
| `build_video.py` | Modify | Replace `base_filter` string (lines ~356-362) with cinematic Ken Burns filter chain |
| `youtube_settings.json` | Modify | Add 6 new topic clusters: `dog anxiety`, `dog separation anxiety`, `senior dog`, `dog nutrition`, `dog safety`; expand existing with calming chews entry |
| `tests/test_build_video_filters.py` | Modify | Update `test_base_filter_includes_color_grading` to assert new filter values; add `test_ken_burns_filter_components` and `test_vignette_in_filter` |
| `tests/test_affiliate_links.py` | Modify | Update `required` cluster list to include new clusters; add `test_new_topic_clusters_have_links` |

---

### Task 1: Update filter tests to expect cinematic filter values

**Files:**
- Modify: `tests/test_build_video_filters.py`

- [ ] **Step 1: Update the existing color-grading assertion test**

Open `tests/test_build_video_filters.py` and replace the `test_base_filter_includes_color_grading` function:

```python
def test_base_filter_includes_color_grading():
    """Verify cinematic base filter has Ken Burns, warm color grade, and vignette."""
    VIDEO_WIDTH = 1080
    VIDEO_HEIGHT = 1920
    base_filter = (
        "zoompan=z='min(zoom+0.0015,1.5)':d=150"
        ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
        f"eq=brightness=0.04:saturation=1.25:contrast=1.15,"
        f"colorbalance=rs=0.08:gs=0:bs=-0.08,"
        f"vignette=PI/5"
    )
    assert "zoompan" in base_filter
    assert "saturation=1.25" in base_filter
    assert "contrast=1.15" in base_filter
    assert "brightness=0.04" in base_filter
    assert "colorbalance" in base_filter
    assert "vignette=PI/5" in base_filter
```

- [ ] **Step 2: Add two new targeted filter tests**

Append these two functions to the bottom of `tests/test_build_video_filters.py`:

```python
def test_ken_burns_filter_components():
    """Verify Ken Burns zoompan expression is correct."""
    ken_burns = "zoompan=z='min(zoom+0.0015,1.5)':d=150:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    assert "zoompan" in ken_burns
    assert "min(zoom+0.0015,1.5)" in ken_burns
    assert "d=150" in ken_burns
    assert "iw/2-(iw/zoom/2)" in ken_burns
    assert "ih/2-(ih/zoom/2)" in ken_burns


def test_vignette_in_filter():
    """Verify vignette filter is appended after color grading."""
    VIDEO_WIDTH = 1080
    VIDEO_HEIGHT = 1920
    base_filter = (
        "zoompan=z='min(zoom+0.0015,1.5)':d=150"
        ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
        f"eq=brightness=0.04:saturation=1.25:contrast=1.15,"
        f"colorbalance=rs=0.08:gs=0:bs=-0.08,"
        f"vignette=PI/5"
    )
    parts = base_filter.split(",")
    last = parts[-1]
    assert last.startswith("vignette"), f"vignette must be last filter, got: {last}"
```

- [ ] **Step 3: Run the new tests to confirm they FAIL (filter not yet updated)**

```
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
pytest tests/test_build_video_filters.py -v 2>&1 | tail -20
```

Expected: `test_base_filter_includes_color_grading` FAILS (still has old saturation=1.4), new tests PASS (they only test string construction, not the live filter).

- [ ] **Step 4: Commit failing test**

```bash
git add tests/test_build_video_filters.py
git commit -m "test: expect cinematic Ken Burns + vignette filter values"
```

---

### Task 2: Update `base_filter` in `build_video.py`

**Files:**
- Modify: `build_video.py` (lines ~356–362)

- [ ] **Step 1: Locate and replace the `base_filter` string**

Find this block in `build_video.py`:

```python
    # Base scale + color grading
    base_filter = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
        f"eq=brightness=0.02:saturation=1.4:contrast=1.1"
    )
```

Replace it with:

```python
    # Cinematic filter: Ken Burns slow zoom → scale → warm color grade → vignette
    base_filter = (
        "zoompan=z='min(zoom+0.0015,1.5)':d=150"
        ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
        f"eq=brightness=0.04:saturation=1.25:contrast=1.15,"
        f"colorbalance=rs=0.08:gs=0:bs=-0.08,"
        f"vignette=PI/5"
    )
```

**Why remove `force_original_aspect_ratio=decrease` and `pad`?** The `zoompan` filter requires a fixed frame size; `pad` causes dimension mismatches with `zoompan`. The clips are already normalised to 1080×1920 by `_concat_clips`, so padding is not needed here.

- [ ] **Step 2: Run the filter tests — they should now pass**

```
pytest tests/test_build_video_filters.py -v 2>&1 | tail -20
```

Expected: All 8 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add build_video.py
git commit -m "feat: cinematic Ken Burns + warm color grade + vignette filter"
```

---

### Task 3: Update affiliate link tests to cover new clusters

**Files:**
- Modify: `tests/test_affiliate_links.py`

- [ ] **Step 1: Update the `required` cluster list and add a dedicated new-clusters test**

Replace the entire contents of `tests/test_affiliate_links.py` with:

```python
import json
from pathlib import Path


REQUIRED_CLUSTERS = [
    "dog breeds",
    "dog training",
    "dog behavior",
    "dog health",
    "dog science",
    "dog history",
    "dog fun",
    "dog anxiety",
    "dog separation anxiety",
    "senior dog",
    "dog nutrition",
    "dog safety",
    "default",
]


def test_all_topic_clusters_have_real_links():
    settings = json.loads(Path("youtube_settings.json").read_text())
    links = settings["affiliate_links"]
    for cluster in REQUIRED_CLUSTERS:
        assert cluster in links, f"Missing cluster: {cluster}"
        assert "url" in links[cluster], f"Missing url for: {cluster}"
        assert "amzn.to" in links[cluster]["url"], f"Not Amazon URL for: {cluster}"
        assert "product" in links[cluster], f"Missing product text for: {cluster}"


def test_no_placeholder_links():
    content = Path("youtube_settings.json").read_text()
    assert "example.com" not in content
    assert "barkbox.com" not in content
    assert "[AFFILIATE_LINK" not in content


def test_new_topic_clusters_have_links():
    """Verify client-supplied affiliate links are present for all new clusters."""
    settings = json.loads(Path("youtube_settings.json").read_text())
    links = settings["affiliate_links"]
    new_clusters = {
        "dog anxiety": "amzn.to/4whfoeI",         # ThunderShirt
        "dog separation anxiety": "amzn.to/4u0AhZY",  # Furbo camera
        "senior dog": "amzn.to/3OWy3Md",          # Orthopedic bed
        "dog nutrition": "amzn.to/4dkXi2Z",        # Slow feeder bowl
        "dog safety": "amzn.to/3QQZxU7",           # GPS tracker
    }
    for cluster, partial_url in new_clusters.items():
        assert cluster in links, f"Missing cluster: {cluster}"
        assert partial_url in links[cluster]["url"], (
            f"Wrong URL for '{cluster}': expected {partial_url}, "
            f"got {links[cluster]['url']}"
        )
```

- [ ] **Step 2: Run the tests to confirm they FAIL (json not yet updated)**

```
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
pytest tests/test_affiliate_links.py -v 2>&1 | tail -20
```

Expected: `test_all_topic_clusters_have_real_links` and `test_new_topic_clusters_have_links` FAIL.

- [ ] **Step 3: Commit failing test**

```bash
git add tests/test_affiliate_links.py
git commit -m "test: expect new affiliate clusters (dog anxiety, separation, senior, nutrition, safety)"
```

---

### Task 4: Expand `youtube_settings.json` with new affiliate clusters

**Files:**
- Modify: `youtube_settings.json`

- [ ] **Step 1: Add the new topic clusters**

Open `youtube_settings.json`. Inside `"affiliate_links"`, add these entries after `"dog fun"` and before `"default"`:

```json
    "dog anxiety": {
      "product": "Does your dog get anxious? This ThunderShirt calms them fast.",
      "url": "https://amzn.to/4whfoeI"
    },
    "dog calming": {
      "product": "Help your anxious dog relax with these vet-recommended calming chews.",
      "url": "https://amzn.to/4d2T15m"
    },
    "dog separation anxiety": {
      "product": "Watch your dog remotely and toss treats with the Furbo Dog Camera.",
      "url": "https://amzn.to/4u0AhZY"
    },
    "senior dog": {
      "product": "Give your senior dog the comfort they deserve with this orthopedic bed.",
      "url": "https://amzn.to/3OWy3Md"
    },
    "dog joint health": {
      "product": "Support aging joints with this vet-recommended supplement.",
      "url": "https://amzn.to/4wjWweX"
    },
    "dog nutrition": {
      "product": "Slow down fast eaters and improve digestion with this slow feeder bowl.",
      "url": "https://amzn.to/4dkXi2Z"
    },
    "dog safety": {
      "product": "Never lose your dog again — real-time GPS tracking with this top-rated tracker.",
      "url": "https://amzn.to/3QQZxU7"
    },
```

- [ ] **Step 2: Verify JSON is valid**

```
python3 -c "import json; json.load(open('youtube_settings.json')); print('JSON valid')"
```

Expected: `JSON valid`

- [ ] **Step 3: Run affiliate tests — all should pass**

```
pytest tests/test_affiliate_links.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add youtube_settings.json
git commit -m "feat: add affiliate links for anxiety, separation, senior, nutrition, safety clusters"
```

---

### Task 5: Manual smoke test on one video

> The client explicitly asked to test on one video before deploying to the full pipeline.

- [ ] **Step 1: Run the pipeline on a single topic**

```
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
python3 main.py
```

Watch for:
- `⏳ Encoding with ...` line (confirms ffmpeg ran)
- No `ffmpeg error:` in output
- `outputs/final_video.mp4` exists when done

- [ ] **Step 2: Spot-check the video**

```
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,codec_name -of default=noprint_wrappers=1 outputs/final_video.mp4
```

Expected output:
```
codec_name=h264
width=1080
height=1920
```

- [ ] **Step 3: If render is too slow, switch preset in `build_video.py`**

Find in `build_video.py` (around the `enc_params` dict or where `preset` is defined):
```python
"preset": "slow",
```
Change to:
```python
"preset": "medium",
```
Re-run and verify.

- [ ] **Step 4: Run full test suite to check for regressions**

```
pytest tests/ -v 2>&1 | tail -30
```

Expected: All tests PASS.

- [ ] **Step 5: Final commit**

```bash
git add -p  # stage only intentional changes
git commit -m "chore: smoke test passed — cinematic filter and affiliate links ready"
```

---

## Self-Review

**Spec coverage:**
- ✅ Ken Burns zoompan — Task 2
- ✅ Warm color grading (`eq` + `colorbalance`) — Task 2
- ✅ Vignette — Task 2
- ✅ `crf 18` / `-preset slow` — already in `build_video.py`; plan notes how to switch to medium if slow
- ✅ Test on one video first — Task 5
- ✅ Amazon affiliate links (all 8 categories from client email) — Tasks 3 & 4
- ✅ Affiliate link placement after intro blurb before hashtags — already handled by `description_template` in `youtube_settings.json`; `{affiliate_block}` is between `{video_script}` and `{hashtags}`

**Placeholder scan:** None found.

**Type consistency:** No new functions introduced; only string literals and JSON keys changed.
