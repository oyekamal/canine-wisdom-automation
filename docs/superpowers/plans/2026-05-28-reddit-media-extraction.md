# Reddit Media Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a Reddit post has an attached image or video (trail cam photo, screenshot, paranormal footage), download it and use it as the primary footage in the horror video instead of a generic Pexels clip.

**Architecture:** A new `extract_media(post_dict)` function in `reddit_harvest.py` detects and downloads post-attached media (images from i.redd.it/imgur, videos from v.redd.it) into the channel's `footage_dir`. The horror orchestrator calls this after story selection — if media is found it becomes `clip_path`, superseding the Pexels footage fetch. Images are converted to video via ffmpeg (`-loop 1 -t <audio_duration>`). Videos are downloaded directly.

**Tech Stack:** Python 3, requests, ffmpeg (`-loop 1` for image-to-video), PullPush API fields (`url`, `domain`, `post_hint`, `is_video`), pytest

---

## What PullPush returns for media posts

| Field | Value | Meaning |
|---|---|---|
| `domain` | `"i.redd.it"` | Direct Reddit image |
| `domain` | `"v.redd.it"` | Reddit-hosted video |
| `domain` | `"i.imgur.com"` | Imgur image |
| `domain` | `"imgur.com"` | Imgur page (need .jpg appended) |
| `post_hint` | `"image"` | Image post |
| `post_hint` | `"hosted:video"` | Reddit video |
| `is_video` | `True` | Has video |
| `url` | ends in `.jpg/.png/.gif/.mp4` | Direct media URL |

**v.redd.it videos** need special handling — the video and audio are separate streams. We use `yt-dlp` to download them (already in requirements).

---

## File Map

| File | Action | What changes |
|---|---|---|
| `channels/horror-narration/harness/reddit_harvest.py` | Modify | Add `extract_media(post_dict, save_dir)` — detects and downloads post media |
| `channels/horror-narration/harness/orchestrator.py` | Modify | After story selection, call `extract_media`; if media found use it as `clip_path`, skip Pexels fetch |
| `channels/horror-narration/tests/test_reddit_harvest.py` | Modify | Add tests for `extract_media` detection and download logic |

---

### Task 1: Add `extract_media()` to `reddit_harvest.py`

**Files:**
- Modify: `channels/horror-narration/harness/reddit_harvest.py`
- Modify: `channels/horror-narration/tests/test_reddit_harvest.py`

- [ ] **Step 1: Write the failing tests**

Append to `channels/horror-narration/tests/test_reddit_harvest.py`:

```python
def test_extract_media_detects_image_post():
    """Posts from i.redd.it with post_hint=image are detected as images."""
    from channels.horror_narration.harness.reddit_harvest import _detect_media
    post = {
        "url": "https://i.redd.it/abc123.jpg",
        "domain": "i.redd.it",
        "post_hint": "image",
        "is_video": False,
    }
    result = _detect_media(post)
    assert result is not None
    assert result["type"] == "image"
    assert result["url"] == "https://i.redd.it/abc123.jpg"


def test_extract_media_detects_imgur():
    """Imgur image domains are detected."""
    from channels.horror_narration.harness.reddit_harvest import _detect_media
    post = {
        "url": "https://i.imgur.com/xyz.jpg",
        "domain": "i.imgur.com",
        "post_hint": "image",
        "is_video": False,
    }
    result = _detect_media(post)
    assert result is not None
    assert result["type"] == "image"


def test_extract_media_detects_reddit_video():
    """v.redd.it posts are detected as video."""
    from channels.horror_narration.harness.reddit_harvest import _detect_media
    post = {
        "url": "https://v.redd.it/abc123",
        "domain": "v.redd.it",
        "post_hint": "hosted:video",
        "is_video": True,
    }
    result = _detect_media(post)
    assert result is not None
    assert result["type"] == "video"
    assert result["url"] == "https://v.redd.it/abc123"


def test_extract_media_returns_none_for_text_post():
    """Text-only posts return None."""
    from channels.horror_narration.harness.reddit_harvest import _detect_media
    post = {
        "url": "https://www.reddit.com/r/nosleep/comments/abc/title/",
        "domain": "self.nosleep",
        "post_hint": "self",
        "is_video": False,
    }
    result = _detect_media(post)
    assert result is None


def test_extract_media_returns_none_for_external_link():
    """External links (not image/video domains) return None."""
    from channels.horror_narration.harness.reddit_harvest import _detect_media
    post = {
        "url": "https://www.youtube.com/watch?v=abc",
        "domain": "youtube.com",
        "post_hint": "rich:video",
        "is_video": False,
    }
    result = _detect_media(post)
    assert result is None


def test_download_reddit_image_saves_file(tmp_path):
    """_download_reddit_image saves image bytes to disk."""
    from channels.horror_narration.harness.reddit_harvest import _download_reddit_image
    from unittest.mock import patch, MagicMock

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.content = b"\xff\xd8\xff" + b"x" * 5000  # fake JPEG bytes

    with patch("requests.get", return_value=fake_resp):
        output = tmp_path / "test_image.jpg"
        result = _download_reddit_image("https://i.redd.it/fake.jpg", output)

    assert result is True
    assert output.exists()
    assert output.stat().st_size > 0
```

- [ ] **Step 2: Run to confirm failure**

```
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation && source venv/bin/activate && python3 -m pytest channels/horror-narration/tests/test_reddit_harvest.py -v -k "extract_media or download_reddit" 2>&1 | tail -15
```

Expected: ImportError — `_detect_media` not found.

- [ ] **Step 3: Add functions to `reddit_harvest.py`**

Append to the bottom of `channels/horror-narration/harness/reddit_harvest.py`:

```python
# ── Media detection and download ─────────────────────────────────────────────

IMAGE_DOMAINS = {"i.redd.it", "i.imgur.com", "preview.redd.it"}
VIDEO_DOMAINS = {"v.redd.it"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
IMAGE_HINTS = {"image"}
VIDEO_HINTS = {"hosted:video", "rich:video"}


def _detect_media(post: dict) -> dict | None:
    """
    Detect whether a Reddit post has attached image or video media.

    Returns a dict with keys:
        type: "image" or "video"
        url: direct URL to the media

    Returns None if the post is text-only or links to an external site
    we don't support.
    """
    url = post.get("url", "")
    domain = post.get("domain", "")
    hint = post.get("post_hint", "")
    is_video = post.get("is_video", False)

    # Reddit-hosted video
    if domain in VIDEO_DOMAINS or is_video and domain in VIDEO_DOMAINS:
        return {"type": "video", "url": url}

    # Hosted video hint (Reddit video player)
    if hint in VIDEO_HINTS and domain in VIDEO_DOMAINS:
        return {"type": "video", "url": url}

    # Direct image from Reddit or Imgur
    if domain in IMAGE_DOMAINS:
        return {"type": "image", "url": url}

    # URL ends in an image extension
    from pathlib import Path as _Path
    if _Path(url.split("?")[0]).suffix.lower() in IMAGE_EXTENSIONS:
        return {"type": "image", "url": url}

    # post_hint says image and domain is image-like
    if hint in IMAGE_HINTS and not domain.startswith("self."):
        return {"type": "image", "url": url}

    return None


def _download_reddit_image(url: str, output_path) -> bool:
    """
    Download a direct image URL to output_path.
    Returns True on success.
    """
    try:
        r = requests.get(url, timeout=20, headers=HEADERS, stream=True)
        r.raise_for_status()
        content = r.content
        if len(content) < 1000:
            return False
        from pathlib import Path as _Path
        _Path(output_path).write_bytes(content)
        return True
    except Exception:
        return False


def _download_reddit_video(url: str, output_path) -> bool:
    """
    Download a Reddit-hosted video (v.redd.it) using yt-dlp.
    These have separate video+audio streams that yt-dlp merges.
    Returns True on success.
    """
    import subprocess
    from pathlib import Path as _Path
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--quiet",
                "--no-warnings",
                "-f", "bestvideo[height<=1920]+bestaudio/best[height<=1920]",
                "--merge-output-format", "mp4",
                "-o", str(output_path),
                url,
            ],
            capture_output=True, text=True, timeout=120,
        )
        return result.returncode == 0 and _Path(output_path).exists()
    except Exception:
        return False


def extract_media(post: dict, save_dir, story_id: str) -> str | None:
    """
    If the Reddit post has attached media, download it into save_dir.

    For images: saves as {story_id}_reddit_media.jpg
    For videos: saves as {story_id}_reddit_media.mp4

    Returns the path to the downloaded file as a string, or None if
    the post has no supported media or the download fails.
    """
    from pathlib import Path as _Path
    media = _detect_media(post)
    if media is None:
        return None

    save_dir = _Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    if media["type"] == "image":
        ext = _Path(media["url"].split("?")[0]).suffix.lower() or ".jpg"
        if ext not in IMAGE_EXTENSIONS:
            ext = ".jpg"
        output_path = save_dir / f"{story_id}_reddit_media{ext}"
        if output_path.exists():
            return str(output_path)
        success = _download_reddit_image(media["url"], output_path)
        return str(output_path) if success else None

    elif media["type"] == "video":
        output_path = save_dir / f"{story_id}_reddit_media.mp4"
        if output_path.exists():
            return str(output_path)
        success = _download_reddit_video(media["url"], output_path)
        return str(output_path) if success else None

    return None
```

- [ ] **Step 4: Run tests — all 6 should pass**

```
python3 -m pytest channels/horror-narration/tests/test_reddit_harvest.py -v -k "extract_media or download_reddit" 2>&1 | tail -15
```

Expected: 6 passed.

- [ ] **Step 5: Run full test suite**

```
python3 -m pytest tests/ channels/horror-narration/tests/ -q 2>&1 | tail -5
```

- [ ] **Step 6: Commit**

```bash
git add channels/horror-narration/harness/reddit_harvest.py channels/horror-narration/tests/test_reddit_harvest.py
git commit -m "feat: reddit_harvest — detect and download post-attached images/videos (i.redd.it, imgur, v.redd.it)"
```

---

### Task 2: Convert Reddit images to looping video clips

**Files:**
- Create: `channels/horror-narration/harness/media_converter.py`
- Create: `channels/horror-narration/tests/test_media_converter.py`

A Reddit image (`.jpg`, `.png`) must be converted to a video clip before `build_video` can use it. We use ffmpeg's `-loop 1` flag to create a static video from the image, duration matched to the audio length. We add a subtle Ken Burns zoom — safe on a single static image (unlike multi-clip where it caused freezes).

- [ ] **Step 1: Write the failing tests**

Create `channels/horror-narration/tests/test_media_converter.py`:

```python
import inspect
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_image_to_video_returns_mp4_path(tmp_path):
    """image_to_video returns a .mp4 path."""
    from channels.horror_narration.harness.media_converter import image_to_video

    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"\xff\xd8\xff" + b"x" * 5000)
    output = tmp_path / "out.mp4"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        # Simulate ffmpeg creating the output file
        output.write_bytes(b"fake_video")
        result = image_to_video(str(fake_img), str(output), duration=25.0)

    assert result == str(output)


def test_image_to_video_uses_loop_flag(tmp_path):
    """image_to_video command must include -loop 1 for static image."""
    from channels.horror_narration.harness.media_converter import image_to_video

    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"\xff\xd8\xff" + b"x" * 5000)
    output = tmp_path / "out.mp4"

    captured_cmd = []
    def fake_run(cmd, **kwargs):
        captured_cmd.extend(cmd)
        output.write_bytes(b"fake")
        return MagicMock(returncode=0)

    with patch("subprocess.run", side_effect=fake_run):
        image_to_video(str(fake_img), str(output), duration=25.0)

    assert "-loop" in captured_cmd
    assert "1" in captured_cmd
    assert "-t" in captured_cmd


def test_image_to_video_returns_none_on_failure(tmp_path):
    """image_to_video returns None if ffmpeg fails."""
    from channels.horror_narration.harness.media_converter import image_to_video

    fake_img = tmp_path / "test.jpg"
    fake_img.write_bytes(b"\xff\xd8\xff" + b"x" * 5000)
    output = tmp_path / "out.mp4"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        result = image_to_video(str(fake_img), str(output), duration=25.0)

    assert result is None


def test_is_image_file_detects_jpg():
    """is_image_file returns True for image extensions."""
    from channels.horror_narration.harness.media_converter import is_image_file
    assert is_image_file("photo.jpg") is True
    assert is_image_file("photo.PNG") is True
    assert is_image_file("video.mp4") is False
    assert is_image_file("file.txt") is False
```

- [ ] **Step 2: Run to confirm failure**

```
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation && source venv/bin/activate && python3 -m pytest channels/horror-narration/tests/test_media_converter.py -v 2>&1 | tail -10
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Create `channels/horror-narration/harness/media_converter.py`**

```python
"""
Convert Reddit media (images/videos) into video clips usable by build_video.

Images: converted to looping video via ffmpeg -loop 1 with slow Ken Burns zoom.
Videos: returned as-is (already MP4 from yt-dlp download).

Ken Burns zoom is safe here because we're working with a single static source,
not mixing variable-fps clips (which was the cause of the earlier freeze bug).
"""
import subprocess
import tempfile
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def is_image_file(path: str) -> bool:
    """Return True if the file has an image extension."""
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def image_to_video(
    image_path: str,
    output_path: str,
    duration: float,
    width: int = 1080,
    height: int = 1920,
) -> str | None:
    """
    Convert a static image to a video clip using ffmpeg.

    Applies a slow Ken Burns zoom (safe on single image — no fps mixing issue).
    Output is constant 30fps h264, duration matches audio.

    Args:
        image_path: Path to source image (.jpg, .png, etc.)
        output_path: Path for output .mp4
        duration: Duration in seconds (should match audio)
        width: Output width (default 1080 for vertical Short)
        height: Output height (default 1920 for vertical Short)

    Returns:
        output_path as string on success, None on failure.
    """
    # d=frames for zoompan: duration * 30fps
    d_frames = int(duration * 30)

    cmd = [
        "ffmpeg",
        "-loop", "1",
        "-i", str(image_path),
        "-t", str(duration),
        "-vf", (
            f"scale={width * 2}:{height * 2},"  # upscale 2x for zoom headroom
            f"zoompan=z='min(zoom+0.0003,1.15)':d={d_frames}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',"
            f"scale={width}:{height},"
            f"eq=brightness=0.02:saturation=1.1:contrast=1.05,"
            f"vignette=PI/4"
        ),
        "-r", "30",
        "-vsync", "cfr",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "slow",
        "-bf", "0",
        "-g", "30",
        "-pix_fmt", "yuv420p",
        "-an",
        "-y", str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and Path(output_path).exists():
            return str(output_path)
        return None
    except Exception:
        return None


def prepare_reddit_media(media_path: str, duration: float, save_dir: str) -> str | None:
    """
    Ensure Reddit media is in a usable video format.

    - If already .mp4: return as-is
    - If image (.jpg etc): convert to video with Ken Burns zoom

    Args:
        media_path: Path to downloaded Reddit media
        duration: Audio duration in seconds (for image-to-video length)
        save_dir: Directory to save converted video

    Returns:
        Path to usable .mp4 clip, or None on failure.
    """
    p = Path(media_path)
    if not p.exists():
        return None

    if p.suffix.lower() == ".mp4":
        return str(p)  # already video

    if is_image_file(str(p)):
        output_path = Path(save_dir) / (p.stem + "_converted.mp4")
        if output_path.exists():
            return str(output_path)
        return image_to_video(str(p), str(output_path), duration=duration)

    return None
```

- [ ] **Step 4: Run tests — all 4 should pass**

```
python3 -m pytest channels/horror-narration/tests/test_media_converter.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add channels/horror-narration/harness/media_converter.py channels/horror-narration/tests/test_media_converter.py
git commit -m "feat: media_converter — convert Reddit images to video with Ken Burns zoom; prepare_reddit_media() handles both image and video"
```

---

### Task 3: Wire media extraction into the horror orchestrator

**Files:**
- Modify: `channels/horror-narration/harness/orchestrator.py`

After the story is selected and rewritten, check if the original Reddit post had media. If yes: download it, convert if needed, use it as `clip_path` (supersedes Pexels fetch). If no: fall back to existing Pexels footage fetch.

- [ ] **Step 1: Read the current orchestrator** to understand the flow around `clip_path` and `fetch_footage_for_topic`.

The relevant section currently (after rewrite):
```python
    # ── Fetch story-matched footage ───────────────────────────────────────────
    topic_cluster = metadata["topic_cluster"]
    clip_path = None
    log(f"🎥 Fetching footage for topic: {topic_cluster}")
    try:
        clip_result = fetch_footage_for_topic(topic_cluster, topic_cluster, fmt=fmt,
                                               save_dir=channel_config.footage_dir)
        ...
```

- [ ] **Step 2: Add the imports to the orchestrator**

Find the import section at the top of `channels/horror-narration/harness/orchestrator.py`. After the existing imports, the `_load` block loads sibling modules. Add two more loads after the existing three:

```python
_converter_mod = _load("media_converter", "media_converter.py")
prepare_reddit_media = _converter_mod.prepare_reddit_media
```

Also import `extract_media` from the harvest module. The `_harvest_mod` is already loaded — add:
```python
extract_media = _harvest_mod.extract_media
```

- [ ] **Step 3: Replace the footage section in `run_horror_pipeline()`**

Find this block:
```python
    # ── Fetch story-matched footage ───────────────────────────────────────────
    topic_cluster = metadata["topic_cluster"]
    clip_path = None
    log(f"🎥 Fetching footage for topic: {topic_cluster}")
    try:
        clip_result = fetch_footage_for_topic(topic_cluster, topic_cluster, fmt=fmt,
                                               save_dir=channel_config.footage_dir)
        if clip_result:
            clip_path = str(clip_result)
            log(f"✅ Footage ready: {clip_result.name}")
        else:
            log("⚠️  No footage downloaded — using existing library")
    except Exception as e:
        log(f"⚠️  Footage fetch failed (non-blocking): {e}", level="warning")
```

Replace it with:

```python
    # ── Fetch footage: Reddit media first, Pexels as fallback ────────────────
    topic_cluster = metadata["topic_cluster"]
    clip_path = None

    # Step A: Try to extract media directly attached to the Reddit post
    try:
        reddit_media_path = extract_media(
            story,  # raw story dict has url, domain, post_hint, is_video
            save_dir=channel_config.footage_dir,
            story_id=story["id"],
        )
        if reddit_media_path:
            log(f"📸 Reddit media found: {reddit_media_path}")
            converted = prepare_reddit_media(
                reddit_media_path,
                duration=audio_duration,
                save_dir=str(channel_config.footage_dir),
            )
            if converted:
                clip_path = converted
                log(f"✅ Using Reddit media as footage: {converted}")
    except Exception as e:
        log(f"⚠️  Reddit media extraction failed (non-blocking): {e}", level="warning")

    # Step B: If no Reddit media, fall back to Pexels/Pixabay topic footage
    if clip_path is None:
        log(f"🎥 No Reddit media — fetching Pexels footage for: {topic_cluster}")
        try:
            clip_result = fetch_footage_for_topic(topic_cluster, topic_cluster, fmt=fmt,
                                                   save_dir=channel_config.footage_dir)
            if clip_result:
                clip_path = str(clip_result)
                log(f"✅ Footage ready: {clip_result.name}")
            else:
                log("⚠️  No footage downloaded — using existing library")
        except Exception as e:
            log(f"⚠️  Footage fetch failed (non-blocking): {e}", level="warning")
```

- [ ] **Step 4: Verify the orchestrator imports load without error**

```
source venv/bin/activate && python3 -c "
import importlib.util, sys
sys.path.insert(0, '.')
spec = importlib.util.spec_from_file_location('horror_orch', 'channels/horror-narration/harness/orchestrator.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print('✅ orchestrator loads OK')
print('extract_media:', hasattr(mod, 'extract_media'))
print('prepare_reddit_media:', hasattr(mod, 'prepare_reddit_media'))
"
```

Expected: both True.

- [ ] **Step 5: Run full test suite**

```
python3 -m pytest tests/ channels/horror-narration/tests/ -q 2>&1 | tail -10
```

- [ ] **Step 6: Commit**

```bash
git add channels/horror-narration/harness/orchestrator.py
git commit -m "feat: orchestrator extracts Reddit post media first, falls back to Pexels if none found"
```

---

### Task 4: Smoke test with a media post

- [ ] **Step 1: Find a Reddit post with actual media for manual verification**

```
source venv/bin/activate && python3 -c "
import sys, importlib.util, requests
sys.path.insert(0,'.')
spec = importlib.util.spec_from_file_location('rh', 'channels/horror-narration/harness/reddit_harvest.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

# Search for posts that tend to have images
r = requests.get('https://api.pullpush.io/reddit/search/submission/?subreddit=Paranormal&sort=score&size=50',
    headers={'User-Agent': 'horror_harness/1.0'}, timeout=20)
posts = r.json().get('data', [])
print(f'Total posts: {len(posts)}')
media_posts = []
for p in posts:
    media = m._detect_media(p)
    if media:
        media_posts.append((p, media))
        print(f'MEDIA: [{media[\"type\"]}] {p[\"title\"][:60]}')
        print(f'       url: {media[\"url\"][:80]}')
        print()
print(f'Posts with media: {len(media_posts)} of {len(posts)}')
"
```

Expected: 1–5 posts with detected media (images from trail cams, screenshots, etc.)

- [ ] **Step 2: Run dry-run pipeline — check if Reddit media is used**

```
source venv/bin/activate && HORROR_DRY_RUN=1 python3 channels/horror-narration/harness/orchestrator.py 2>&1
```

Watch for one of:
- `📸 Reddit media found: ...` + `✅ Using Reddit media as footage: ...` → Reddit media used
- `🎥 No Reddit media — fetching Pexels footage for: ...` → fell back to Pexels (story had no media)

Both are correct — the pipeline handles both cases.

- [ ] **Step 3: Manually test image-to-video conversion**

```
source venv/bin/activate && python3 -c "
import sys, importlib.util, requests, tempfile
from pathlib import Path

sys.path.insert(0,'.')
spec = importlib.util.spec_from_file_location('mc', 'channels/horror-narration/harness/media_converter.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

# Download a test image from i.redd.it
test_url = 'https://i.redd.it/snoovatar/avatars/nftv2_bmZ0X2VpcDE1NToxMzdfY2I3YjQxNzk2MjIyMjIwMjY2MGUwN2MxNzQxMTRlMGQzMWZiMQ_rare_a18bd5fa-d34d-4f81-9d97-4a0a9e0f0001.png'
tmp = Path(tempfile.gettempdir()) / 'test_reddit.jpg'

r = requests.get(test_url, timeout=10)
if r.status_code == 200:
    tmp.write_bytes(r.content)
    print(f'Downloaded test image: {tmp.stat().st_size // 1024} KB')
    out = Path(tempfile.gettempdir()) / 'test_reddit_video.mp4'
    result = m.image_to_video(str(tmp), str(out), duration=10.0)
    if result:
        import subprocess
        probe = subprocess.run(['ffprobe','-v','error','-show_entries','stream=width,height,duration',
            '-of','default=noprint_wrappers=1', result], capture_output=True, text=True)
        print('Video created:')
        print(probe.stdout)
    else:
        print('❌ image_to_video failed')
else:
    print('Could not download test image — skip this test')
"
```

Expected: 10s video, 1080×1920.

- [ ] **Step 4: Run full test suite one last time**

```
python3 -m pytest tests/ channels/horror-narration/tests/ -q 2>&1 | tail -10
```

- [ ] **Step 5: Commit smoke test confirmation**

```bash
git commit -m "chore: Reddit media extraction smoke tested — image-to-video and fallback both verified"
```

---

## Self-Review

**Spec coverage:**
- ✅ Detect image posts (i.redd.it, imgur, post_hint=image, URL extension) — Task 1 `_detect_media()`
- ✅ Detect video posts (v.redd.it, is_video, hosted:video hint) — Task 1 `_detect_media()`
- ✅ Download Reddit images — Task 1 `_download_reddit_image()`
- ✅ Download Reddit videos via yt-dlp — Task 1 `_download_reddit_video()`
- ✅ Convert images to video with Ken Burns zoom — Task 2 `image_to_video()`
- ✅ Ken Burns safe on single image (no fps-mixing freeze) — Task 2 comment explains why
- ✅ Orchestrator uses Reddit media as primary, Pexels as fallback — Task 3
- ✅ Text-only posts fall back gracefully to Pexels — Task 3 Step B
- ✅ Already-downloaded media reused (path exists check) — Task 1 `extract_media()`
- ✅ End-to-end smoke test — Task 4

**Placeholder scan:** None found.

**Type consistency:**
- `extract_media(post, save_dir, story_id)` → `str | None` — consistent with orchestrator usage
- `prepare_reddit_media(media_path, duration, save_dir)` → `str | None` — consistent
- `story["id"]` used as `story_id` — same key used throughout harvest module
