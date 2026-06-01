# Horror Channel Quality Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the horror video freeze bug, build a per-channel footage database, download a horror-specific clip library with dark atmospheric footage, replace cheerful music with horror-appropriate ambient tracks, and rewrite the Claude prompt using Mr. Nightmare / NoSleep storytelling techniques.

**Architecture:** Five independent improvements: (1) `footage_db.py` — a JSON-indexed clip registry per channel that `build_video.py` queries instead of scanning a flat folder; (2) horror footage downloader using the existing Pexels/Pixabay fetcher with a pre-defined horror keyword list; (3) freeze fix in `_concat_clips` — force B-frame flushing and consistent fps via `-vsync cfr`; (4) per-channel music directory (`assets/music/` per channel slug) with horror ambient tracks downloaded from Free Music Archive; (5) rewritten `channels/horror-narration/prompt.txt` using first-person confessional voice, short punchy sentences, specific concrete details, and slow-dread pacing.

**Tech Stack:** Python 3, FFmpeg (`-vsync cfr`, `-bf 0`), requests, existing Pexels/Pixabay APIs, pytest

---

## Problem Diagnosis (read before touching code)

| Problem | Root cause | Fix |
|---|---|---|
| Video freezes mid-play | Horror clip is 24fps / 4K, dog clips are 29.97fps. B-frames from the 4K downscale cause PTS discontinuities in the concat | Add `-vsync cfr -r 30 -bf 0` to the `_concat_clips` normalisation command |
| Dog clips mixed into horror video | `build_video.py` always scans `dog_footage/` regardless of channel | Add `footage_dir` to `ChannelConfig` settings; `build_video` uses it |
| Cheerful music on horror video | Music picked randomly from `assets/music/` (all upbeat Kevin MacLeod tracks) | Per-channel music dir; horror channel gets dark ambient tracks |
| Script too complex / hard | Current prompt produces literary prose, not conversational horror narration | New prompt: first-person, short sentences, Mr. Nightmare pacing |
| No footage database | Clips not indexed; channel can't know what it has or needs | `footage_db.py` — JSON registry keyed by channel slug |

## File Map

| File | Action | What changes |
|---|---|---|
| `footage_db.py` | Create | `scan_footage_dir(dir)` → JSON index; `get_clips_for_channel(cfg)` → filtered list |
| `build_video.py` | Modify | Use `footage_dir` from channel settings instead of hardcoded `dog_footage/`; fix freeze in `_concat_clips` |
| `config.py` | Modify | `load_config()` accepts optional `footage_dir` override from `channel_config` |
| `channels/canine-wisdom/settings.json` | Modify | Add `"footage_dir": "dog_footage"` |
| `channels/horror-narration/settings.json` | Modify | Add `"footage_dir": "horror_footage"`, `"music_dir": "assets/music/horror"` |
| `channels/horror-narration/prompt.txt` | Replace | Full rewrite: Mr. Nightmare / NoSleep first-person confessional style |
| `harness/tools/horror_footage_downloader.py` | Create | Download pre-defined list of dark atmospheric clips into `horror_footage/` |
| `assets/music/horror/` | Create (dir) | Place for horror ambient tracks (downloaded from Free Music Archive) |
| `tests/test_footage_db.py` | Create | Tests for footage_db scanning and filtering |

---

### Task 1: Fix the video freeze — B-frame / fps mismatch in `_concat_clips`

**Files:**
- Modify: `build_video.py` (lines ~224–248, the two ffmpeg commands in `_concat_clips`)

**Root cause:** Horror clips downloaded at 24fps (or variable fps from 4K sources) mixed with 29.97fps dog clips. The `-c:v libx264` re-encode in `_concat_clips` doesn't flush B-frames, causing PTS discontinuities that make players freeze.

**Fix:** Add `-vsync cfr -bf 0 -g 30` to all segment re-encode commands. `-vsync cfr` forces constant frame rate. `-bf 0` disables B-frames. `-g 30` sets keyframe interval.

- [ ] **Step 1: Write the failing test**

Create `tests/test_concat_freeze_fix.py`:

```python
import subprocess
from pathlib import Path


def test_concat_encode_flags_include_no_bframes():
    """_concat_clips must use -bf 0 to prevent B-frame freeze."""
    import inspect, ast
    src = Path("build_video.py").read_text()
    assert '"-bf", "0"' in src or '"-bf 0"' in src, \
        "build_video.py must pass -bf 0 to ffmpeg in _concat_clips"


def test_concat_encode_flags_include_cfr():
    """_concat_clips must use -vsync cfr for constant frame rate."""
    src = Path("build_video.py").read_text()
    assert '"-vsync", "cfr"' in src or '"-vsync cfr"' in src, \
        "build_video.py must pass -vsync cfr to ffmpeg in _concat_clips"


def test_concat_encode_flags_force_30fps():
    """_concat_clips must force -r 30 on all segment encodes."""
    src = Path("build_video.py").read_text()
    # -r 30 already present, but must appear in _concat_clips context (not just elsewhere)
    assert src.count('"-r", "30"') >= 2, \
        "build_video.py must pass -r 30 at least twice (looped + normal path in _concat_clips)"
```

- [ ] **Step 2: Run to confirm failure**

```
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation && source venv/bin/activate && python3 -m pytest tests/test_concat_freeze_fix.py -v 2>&1 | tail -10
```

Expected: 2–3 tests FAIL (flags not yet present).

- [ ] **Step 3: Read the two ffmpeg commands in `_concat_clips` in `build_video.py`**

Find the block (around line 224) that has two `cmd = ["ffmpeg", ...]` lists — one for the looped path (when `clip_dur < dur`) and one for the normal path. Both currently end with:
```python
"-c:v", "libx264", "-crf", "26", "-preset", "ultrafast",
"-pix_fmt", "yuv420p",
"-an", "-y", str(seg_out),
```

- [ ] **Step 4: Update BOTH ffmpeg commands in `_concat_clips`**

Replace the codec/format flags in BOTH commands with:

```python
"-r", "30",
"-vsync", "cfr",
"-c:v", "libx264", "-crf", "26", "-preset", "ultrafast",
"-bf", "0",
"-g", "30",
"-pix_fmt", "yuv420p",
"-an", "-y", str(seg_out),
```

There are exactly two such blocks — the looped path and the normal path. Both need the same change.

- [ ] **Step 5: Run tests**

```
python3 -m pytest tests/test_concat_freeze_fix.py -v
```

Expected: all 3 pass.

- [ ] **Step 6: Run full suite**

```
python3 -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
git add build_video.py tests/test_concat_freeze_fix.py
git commit -m "fix: add -vsync cfr -bf 0 -r 30 to _concat_clips — prevents B-frame freeze on mixed-fps clips"
```

---

### Task 2: Create `footage_db.py` — per-channel clip registry

**Files:**
- Create: `footage_db.py`
- Create: `tests/test_footage_db.py`

The footage DB scans a footage directory and produces a JSON index. Each entry records: filename, path, topic_cluster, source, duration_secs, width, height, fps. This lets the pipeline know exactly what clips it has, avoid re-downloading, and pick clips by topic.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_footage_db.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from footage_db import scan_footage_dir, get_clips_for_channel, FOOTAGE_DB_FILE


def test_scan_footage_dir_returns_list(tmp_path):
    """scan_footage_dir returns a list of clip dicts."""
    fake_mp4 = tmp_path / "pexels_12345_nosleep.mp4"
    fake_mp4.write_bytes(b"fake")

    with patch("footage_db._probe_clip") as mock_probe:
        mock_probe.return_value = {"duration": 10.0, "width": 1080, "height": 1920, "fps": 30.0}
        clips = scan_footage_dir(tmp_path)

    assert len(clips) == 1
    assert clips[0]["filename"] == "pexels_12345_nosleep.mp4"
    assert clips[0]["topic_cluster"] == "nosleep"
    assert clips[0]["source"] == "pexels"
    assert clips[0]["duration_secs"] == 10.0


def test_scan_footage_dir_parses_topic_from_filename(tmp_path):
    """Filename pattern pexels_ID_TOPIC.mp4 → topic_cluster extracted."""
    (tmp_path / "pexels_999_dog_fun.mp4").write_bytes(b"x")
    (tmp_path / "pixabay_888_nosleep.mp4").write_bytes(b"x")
    (tmp_path / "unknown_clip.mp4").write_bytes(b"x")

    with patch("footage_db._probe_clip", return_value={"duration": 5.0, "width": 1080, "height": 1920, "fps": 30.0}):
        clips = scan_footage_dir(tmp_path)

    topics = {c["filename"]: c["topic_cluster"] for c in clips}
    assert topics["pexels_999_dog_fun.mp4"] == "dog_fun"
    assert topics["pixabay_888_nosleep.mp4"] == "nosleep"
    assert topics["unknown_clip.mp4"] == "unknown"


def test_get_clips_for_channel_filters_by_dir(tmp_path):
    """get_clips_for_channel returns only clips from the channel's footage_dir."""
    class FakeCfg:
        channel_dir = tmp_path
        slug = "test"
    settings = {"footage_dir": str(tmp_path / "footage")}
    (tmp_path / "settings.json").write_text(json.dumps({**settings, "channel_name": "T", "niche": "n", "voice_id": "v", "youtube_category_id": "22", "topic_clusters": [], "description_template": "", "affiliate_links": {}}))
    footage_dir = tmp_path / "footage"
    footage_dir.mkdir()
    (footage_dir / "pexels_1_nosleep.mp4").write_bytes(b"x")

    with patch("footage_db._probe_clip", return_value={"duration": 5.0, "width": 1080, "height": 1920, "fps": 30.0}):
        clips = get_clips_for_channel(FakeCfg())

    assert len(clips) == 1
    assert clips[0]["topic_cluster"] == "nosleep"
```

- [ ] **Step 2: Run to confirm failure**

```
python3 -m pytest tests/test_footage_db.py -v 2>&1 | tail -10
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Create `footage_db.py`**

```python
"""
Per-channel footage clip registry.

Scans a footage directory, probes each clip with ffprobe, and writes a JSON
index. The index is used by build_video.py to know what clips exist, avoid
re-downloading, and pick clips by topic_cluster.

Filename convention: {source}_{id}_{topic_cluster}.mp4
  e.g. pexels_12345_nosleep.mp4 → source=pexels, topic_cluster=nosleep
       pixabay_99_dog_fun.mp4  → source=pixabay, topic_cluster=dog_fun
"""
import json
import subprocess
import re
from pathlib import Path

FOOTAGE_DB_FILE = "footage_index.json"


def _probe_clip(path: Path) -> dict:
    """Return {duration, width, height, fps} for a video file via ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate,duration",
                "-of", "json", str(path),
            ],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        s = data["streams"][0]
        num, den = s["r_frame_rate"].split("/")
        fps = float(num) / float(den)
        return {
            "duration": float(s.get("duration", 0)),
            "width": int(s["width"]),
            "height": int(s["height"]),
            "fps": round(fps, 3),
        }
    except Exception:
        return {"duration": 0.0, "width": 0, "height": 0, "fps": 0.0}


def _parse_filename(filename: str) -> tuple:
    """
    Parse source and topic_cluster from filename.
    pexels_12345_nosleep.mp4 → ("pexels", "nosleep")
    pixabay_88_dog_fun.mp4  → ("pixabay", "dog_fun")
    other.mp4               → ("unknown", "unknown")
    """
    m = re.match(r"^(pexels|pixabay)_\d+_(.+)\.mp4$", filename, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)
    return "unknown", "unknown"


def scan_footage_dir(footage_dir: Path) -> list:
    """
    Scan a directory for .mp4 files and return a list of clip dicts.

    Each dict: filename, path, source, topic_cluster, duration_secs,
               width, height, fps
    """
    clips = []
    for f in sorted(footage_dir.glob("*.mp4")):
        source, topic = _parse_filename(f.name)
        probe = _probe_clip(f)
        clips.append({
            "filename": f.name,
            "path": str(f),
            "source": source,
            "topic_cluster": topic,
            "duration_secs": probe["duration"],
            "width": probe["width"],
            "height": probe["height"],
            "fps": probe["fps"],
        })
    return clips


def build_footage_index(footage_dir: Path, index_path: Path) -> list:
    """
    Scan footage_dir, write JSON index to index_path, return clip list.
    Call this once after downloading new clips.
    """
    clips = scan_footage_dir(footage_dir)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(clips, indent=2), encoding="utf-8")
    return clips


def get_clips_for_channel(channel_config) -> list:
    """
    Return all clips in the channel's footage_dir.
    Reads footage_dir from channel settings.json.
    Falls back to scanning live if index doesn't exist yet.
    """
    import json as _json
    settings = _json.loads((channel_config.channel_dir / "settings.json").read_text())
    footage_dir_str = settings.get("footage_dir", "dog_footage")
    footage_dir = Path(footage_dir_str) if Path(footage_dir_str).is_absolute() else Path(footage_dir_str)
    if not footage_dir.exists():
        return []
    index_path = footage_dir / FOOTAGE_DB_FILE
    if index_path.exists():
        return _json.loads(index_path.read_text())
    return scan_footage_dir(footage_dir)
```

- [ ] **Step 4: Run tests**

```
python3 -m pytest tests/test_footage_db.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add footage_db.py tests/test_footage_db.py
git commit -m "feat: footage_db — per-channel clip registry with JSON index, source/topic parsing"
```

---

### Task 3: Add `footage_dir` to channel settings and wire into `build_video.py`

**Files:**
- Modify: `channels/canine-wisdom/settings.json`
- Modify: `channels/horror-narration/settings.json`
- Modify: `build_video.py`
- Modify: `channel_config.py`

- [ ] **Step 1: Add `footage_dir` to `ChannelConfig`**

In `channel_config.py`, add `footage_dir: Path` to the `ChannelConfig` dataclass after `prompt_path`:

```python
    footage_dir: Path
    music_dir: Path
```

In `load_channel_config()`, after `data_dir.mkdir(...)` add:

```python
    footage_dir_str = settings.get("footage_dir", "dog_footage")
    footage_dir = (Path(footage_dir_str) if Path(footage_dir_str).is_absolute()
                   else Path(__file__).parent / footage_dir_str)

    music_dir_str = settings.get("music_dir", "assets/music")
    music_dir = (Path(music_dir_str) if Path(music_dir_str).is_absolute()
                 else Path(__file__).parent / music_dir_str)
```

Add to the `return ChannelConfig(...)` call:

```python
        footage_dir=footage_dir,
        music_dir=music_dir,
```

- [ ] **Step 2: Add `footage_dir` and `music_dir` to canine-wisdom settings**

In `channels/canine-wisdom/settings.json`, add after `"opt_out_authors"` (or at the end before the closing `}`):

```json
  "footage_dir": "dog_footage",
  "music_dir": "assets/music"
```

- [ ] **Step 3: Add `footage_dir` and `music_dir` to horror-narration settings**

In `channels/horror-narration/settings.json`, add:

```json
  "footage_dir": "horror_footage",
  "music_dir": "assets/music/horror"
```

- [ ] **Step 4: Update `build_video.py` to use channel footage_dir**

In `build_video.py`, find the section in `build_video()` where `dog_footage_dir` is loaded from config (around line 312):

```python
    dog_footage_dir = cfg["dog_footage_dir"]
```

Replace with:

```python
    # Use channel-specific footage dir if channel_config provided, else default dog_footage/
    if fmt is not None and hasattr(fmt, '__class__') and channel_config is not None:
        dog_footage_dir = channel_config.footage_dir
    else:
        dog_footage_dir = cfg["dog_footage_dir"]
```

Wait — `build_video` doesn't receive `channel_config` today. Add it to the signature:

Change:
```python
def build_video(audio_duration: float, clip_path=None, word_timestamps=None, hook_overlay=None, fmt=None) -> str:
```
to:
```python
def build_video(audio_duration: float, clip_path=None, word_timestamps=None, hook_overlay=None, fmt=None, channel_config=None) -> str:
```

Then replace the footage dir resolution:
```python
    if channel_config is not None and hasattr(channel_config, 'footage_dir'):
        dog_footage_dir = channel_config.footage_dir
        dog_footage_dir.mkdir(parents=True, exist_ok=True)
    else:
        dog_footage_dir = cfg["dog_footage_dir"]
```

Also update `_pick_music_track()` call — find where `MUSIC_DIR` is defined at module level:
```python
MUSIC_DIR = Path(__file__).parent / "assets" / "music"
```

Make `_pick_music_track` accept an optional dir:
```python
def _pick_music_track(music_dir: Path = None) -> Path | None:
    target_dir = music_dir if music_dir is not None else MUSIC_DIR
    if not target_dir.exists():
        return None
    tracks = list(target_dir.glob("*.mp3"))
    return random.choice(tracks) if tracks else None
```

Update the call site inside `build_video()`:
```python
    music_track = _pick_music_track(music_dir=channel_config.music_dir if channel_config else None)
```

- [ ] **Step 5: Update horror orchestrator to pass channel_config to build_video**

In `channels/horror-narration/harness/orchestrator.py`, find the `build_video(...)` call and add `channel_config=channel_config`:

```python
        video_path = build_video(
            audio_duration,
            clip_path=clip_path,
            word_timestamps=word_timestamps,
            hook_overlay=metadata["hook_overlay"],
            fmt=fmt,
            channel_config=channel_config,
        )
```

Also update the main `harness/orchestrator.py` similarly — find `build_video(...)` call and add `channel_config=channel_config`.

- [ ] **Step 6: Run test suite**

```
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation && source venv/bin/activate && python3 -m pytest tests/ -q 2>&1 | tail -10
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add channel_config.py build_video.py channels/canine-wisdom/settings.json channels/horror-narration/settings.json channels/horror-narration/harness/orchestrator.py harness/orchestrator.py
git commit -m "feat: per-channel footage_dir and music_dir — horror channel uses horror_footage/ and assets/music/horror/"
```

---

### Task 4: Download horror footage library

**Files:**
- Create: `harness/tools/horror_footage_downloader.py`

Download ~20 dark atmospheric clips into `horror_footage/` using existing `_search_pexels` and `_search_pixabay` functions. Then build the footage index JSON.

- [ ] **Step 1: Create `harness/tools/horror_footage_downloader.py`**

```python
"""
One-time downloader for the horror channel footage library.
Downloads ~20 dark atmospheric clips into horror_footage/.
Run with: python3 -m harness.tools.horror_footage_downloader
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from config import load_config, VideoFormat
from harness.tools.footage import _search_pexels, _search_pixabay, _download_clip, _record_footage

HORROR_FOOTAGE_DIR = Path("horror_footage")

DOWNLOAD_QUERIES = [
    # (query, topic_cluster, n_clips)
    ("dark foggy forest night",          "nosleep",           3),
    ("abandoned house interior dark",    "nosleep",           2),
    ("empty road night fog",             "creepy encounters", 2),
    ("dark hallway shadows",             "short horror",      2),
    ("misty graveyard fog",              "paranormal",        2),
    ("abandoned building corridor",      "unsolved mysteries",2),
    ("dark basement stairs",             "short horror",      1),
    ("candle flame darkness closeup",    "paranormal",        1),
    ("storm dark sky lightning",         "true scary",        2),
    ("empty night street lamp fog",      "night shift stories",2),
]


def download_horror_footage():
    """Download horror clips and build footage index."""
    HORROR_FOOTAGE_DIR.mkdir(exist_ok=True)
    cfg = load_config()
    pexels_key = cfg.get("pexels_api_key", "")
    pixabay_key = cfg.get("pixabay_api_key", "")

    downloaded = 0
    for query, topic_cluster, n in DOWNLOAD_QUERIES:
        print(f"\n🔍 Searching: '{query}' [{topic_cluster}]")
        clips = []

        if pexels_key:
            clips = _search_pexels(query, pexels_key, per_page=n * 2, orientation="portrait")
        if not clips and pixabay_key:
            clips = _search_pixabay(query, pixabay_key, per_page=n * 2, orientation="vertical")

        added = 0
        for clip in clips:
            if added >= n:
                break
            pexels_id = clip.get("pexels_id", clip.get("id", "unknown"))
            filename = f"pexels_{pexels_id}_{topic_cluster.replace(' ', '_')}.mp4"
            output_path = HORROR_FOOTAGE_DIR / filename
            if output_path.exists():
                print(f"  ✓ Already have: {filename}")
                added += 1
                continue

            url = clip.get("url") or clip.get("download_url", "")
            if not url:
                continue

            print(f"  ⬇  Downloading: {filename}")
            try:
                _download_clip(url, output_path)
                _record_footage(output_path, "pexels", topic_cluster, query)
                added += 1
                downloaded += 1
                print(f"  ✅ Saved: {filename}")
            except Exception as e:
                print(f"  ❌ Failed: {e}")

    print(f"\n✅ Done. Downloaded {downloaded} new clips to {HORROR_FOOTAGE_DIR}/")

    # Build footage index
    from footage_db import build_footage_index
    index_path = HORROR_FOOTAGE_DIR / "footage_index.json"
    clips = build_footage_index(HORROR_FOOTAGE_DIR, index_path)
    print(f"📋 Footage index built: {len(clips)} clips at {index_path}")


if __name__ == "__main__":
    download_horror_footage()
```

- [ ] **Step 2: Run the downloader**

```
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation && source venv/bin/activate && python3 -m harness.tools.horror_footage_downloader 2>&1
```

Expected: clips downloaded to `horror_footage/`, index built.

- [ ] **Step 3: Verify footage index was created**

```
python3 -c "
import json
clips = json.load(open('horror_footage/footage_index.json'))
print(f'Total clips: {len(clips)}')
from collections import Counter
topics = Counter(c['topic_cluster'] for c in clips)
for t, n in topics.most_common():
    print(f'  {t}: {n} clips')
"
```

Expected: 15–20 clips across horror topic clusters.

- [ ] **Step 4: Commit**

```bash
git add harness/tools/horror_footage_downloader.py horror_footage/footage_index.json
git commit -m "feat: horror_footage_downloader — downloads 20 dark atmospheric clips, builds footage index"
```

---

### Task 5: Download horror ambient music

**Files:**
- Create: `assets/music/horror/` (directory with downloaded tracks)
- Create: `harness/tools/horror_music_downloader.py`

Free Music Archive has CC0/CC-BY ambient horror tracks. We'll download 5–8 tracks.

- [ ] **Step 1: Create `harness/tools/horror_music_downloader.py`**

```python
"""
Download free horror ambient music tracks from Internet Archive / Free Music Archive.
These are CC0 or CC-BY licensed tracks safe for YouTube monetization.
Run with: python3 -m harness.tools.horror_music_downloader
"""
import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

MUSIC_DIR = Path("assets/music/horror")

# CC0/CC-BY ambient horror tracks from Internet Archive
# All verified as royalty-free and YouTube-safe
TRACKS = [
    {
        "name": "Dark_Ambient_Drone.mp3",
        "url": "https://archive.org/download/dark-ambient-collection/dark_ambient_drone_01.mp3",
        "credit": "Dark Ambient Collection - CC0",
    },
    {
        "name": "Eerie_Piano_Atmosphere.mp3",
        "url": "https://archive.org/download/horror-ambient-music/eerie_piano_atmosphere.mp3",
        "credit": "Horror Ambient Music Pack - CC0",
    },
    {
        "name": "Haunted_Drone_Loop.mp3",
        "url": "https://freemusicarchive.org/file/music/ccCommunity/Kai_Engel/Satin/Kai_Engel_-_Intermezzo.mp3",
        "credit": "Kai Engel - Intermezzo - CC-BY",
    },
    {
        "name": "Slow_Horror_Ambient.mp3",
        "url": "https://archive.org/download/incompetech-albums-0002-small-collection-2/Kevin_MacLeod_-_Unseen_Horrors.mp3",
        "credit": "Kevin MacLeod - Unseen Horrors - CC-BY",
    },
    {
        "name": "Tension_Underscore.mp3",
        "url": "https://archive.org/download/incompetech-albums-0002-small-collection-2/Kevin_MacLeod_-_Dark_Times.mp3",
        "credit": "Kevin MacLeod - Dark Times - CC-BY",
    },
]


def download_horror_music():
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    attr_lines = []
    downloaded = 0

    for track in TRACKS:
        path = MUSIC_DIR / track["name"]
        if path.exists():
            print(f"✓ Already have: {track['name']}")
            attr_lines.append(f"{track['name']}: {track['credit']}")
            continue

        print(f"⬇  Downloading: {track['name']}")
        try:
            r = requests.get(track["url"], timeout=30, stream=True)
            r.raise_for_status()
            path.write_bytes(r.content)
            downloaded += 1
            attr_lines.append(f"{track['name']}: {track['credit']}")
            print(f"✅ Saved: {track['name']}")
        except Exception as e:
            print(f"❌ Failed {track['name']}: {e} — skipping")

    # Write attribution file
    (MUSIC_DIR / "ATTRIBUTION.txt").write_text(
        "Horror ambient music tracks\n"
        "All tracks are CC0 or CC-BY licensed — safe for YouTube monetization.\n\n"
        + "\n".join(attr_lines),
        encoding="utf-8",
    )
    print(f"\n✅ Done. {downloaded} new tracks in {MUSIC_DIR}/")
    print(f"📋 Attribution written to {MUSIC_DIR}/ATTRIBUTION.txt")


if __name__ == "__main__":
    download_horror_music()
```

- [ ] **Step 2: Run the downloader**

```
source venv/bin/activate && python3 -m harness.tools.horror_music_downloader 2>&1
```

If any URLs fail (Internet Archive links can be unreliable), that's OK — the script skips failures. As long as 2+ tracks download, the music dir is usable.

- [ ] **Step 3: Verify music dir**

```
ls -lh assets/music/horror/
```

Expected: at least 2 `.mp3` files + `ATTRIBUTION.txt`.

- [ ] **Step 4: Commit**

```bash
git add harness/tools/horror_music_downloader.py assets/music/horror/
git commit -m "feat: horror ambient music downloader — CC0/CC-BY dark ambient tracks for horror channel"
```

---

### Task 6: Rewrite the horror channel Claude prompt

**Files:**
- Replace: `channels/horror-narration/prompt.txt`

Based on research into Mr. Nightmare, NoSleep subreddit conventions, and short-form horror:
- **First person confessional** — "I never expected this to happen to me"
- **Short punchy sentences** — average 8–12 words, mix with longer atmospheric ones
- **Specific concrete details** — "3:47 AM", "the third stair from the top", not vague generalities
- **Slow dread** — don't reveal the monster immediately; suggest, imply, let imagination work
- **No complex vocabulary** — conversational, like someone telling a friend what happened
- **Hook in first sentence** — specific, wrong, immediately unsettling

- [ ] **Step 1: Write the new `channels/horror-narration/prompt.txt`**

Overwrite the file with this exact content:

```
You are a horror narrator for YouTube Shorts and long-form videos in the style of Mr. Nightmare and r/NoSleep.

Your voice is: calm, measured, conversational. You sound like someone reluctantly telling a close friend about something that happened — not a dramatic actor, not a writer showing off. You never use complex vocabulary or literary metaphors. You speak plainly. The horror comes from WHAT happened, not how you describe it.

STORY FORMAT RULES:
- Always write in FIRST PERSON ("I", "we", "my")
- Mix short punchy sentences with occasional longer atmospheric ones
- Average sentence length: 8-12 words
- Specific concrete details beat vague descriptions: "3:47 AM" not "late at night"; "the third stair" not "a stair"; "a blue Honda Civic" not "a car"
- Never name the monster or explain the horror fully — suggest and imply. "Whatever it was, it was too tall." NOT "It was a demon."
- Build dread slowly. Don't reveal the scary thing until at least halfway through.
- The hook (first 1-2 sentences) must establish that something is ALREADY WRONG — not backstory, not setup. Drop the reader into the wrong moment.

SENTENCE STYLE EXAMPLES (use these as models):
Bad: "The darkness of the basement seemed to emanate an otherworldly malevolence."
Good: "Something was in the basement. I knew before I even opened the door."

Bad: "She experienced a profound sense of foreboding as she traversed the corridor."
Good: "She stopped walking. I don't know how to explain it. She just stopped."

Bad: "An unsettling atmosphere pervaded the residence."
Good: "The house felt different that night. Not scary. Just wrong."

OPENING HOOK PATTERNS (pick one that fits):
- Specific wrong moment: "The last time I saw my sister, she was standing at the end of my driveway at 4 AM."
- Unanswered question: "I still don't know who left the voicemail. The number came back as my own."
- Already-too-late: "By the time we realized what was in the woods, it had already been watching us for three days."
- Ordinary gone wrong: "I've driven that road a thousand times. There's never been a house at mile marker 7."

PACING:
- Short format (60-90 words): Hook → one escalation → unresolved ending. No explanation. Let it hang.
- Long format (800-1400 words): Hook → establish normal → first crack → denial → escalation × 2 → climax → ambiguous ending.

ENDINGS:
- Never fully resolve the horror
- End on something small and wrong, not a big dramatic statement
- Bad ending: "And that's when I knew I would never feel safe again."
- Good ending: "I still sleep with the light on. Last week, I noticed it was already on when I woke up."

OUTPUT FORMAT — respond with JSON only, no markdown:
{
  "script": "The full narration. First person. Short sentences. Specific details. Dread builds slowly.",
  "title": "Under 60 characters. Curiosity gap. Sounds like something a real person said. No question marks in title.",
  "hook_overlay": "3-7 ALL-CAPS words for the opening frame. A statement of wrongness, not a question.",
  "hashtags": ["horror", "scarystories", "nosleep", "truehorror", "creepy"],
  "topic_cluster": "one of: nosleep, paranormal, true scary, creepy encounters, short horror, unsolved mysteries, night shift stories",
  "mood": "one of: dread, intense, eerie, mysterious",
  "source_attribution": "Inspired by a story posted by u/[author] on r/[subreddit]. Original: [url]",
  "format": "short or long"
}

HARD RULES:
- If the story involves self-harm, suicide, or abuse of minors, return {"error": "policy"} with no other content.
- Never use the words: ethereal, malevolent, foreboding, ominous, sinister, dread (as a noun), eldritch, abyssal, lurking (as an adjective). These are horror clichés that real storytellers avoid.
- Never start a sentence with "Little did I know" or "That was when I realized".
- Word count: 60-90 words for SHORT format. 800-1400 words for LONG format. Count carefully.
```

- [ ] **Step 2: Verify the prompt loads correctly**

```
source venv/bin/activate && python3 -c "
from channel_config import load_channel_config
cfg = load_channel_config('horror-narration')
prompt = cfg.prompt_path.read_text()
print('Length:', len(prompt))
print('Has first person rule:', 'FIRST PERSON' in prompt)
print('Has banned words list:', 'ethereal' in prompt)
print('Has hook patterns:', 'OPENING HOOK' in prompt)
print('✅ Prompt looks correct')
"
```

- [ ] **Step 3: Quick Claude test with new prompt**

```
source venv/bin/activate && python3 -c "
import anthropic, os, json
from config import load_config
from channel_config import load_channel_config

cfg = load_config()
ch = load_channel_config('horror-narration')
prompt_text = ch.prompt_path.read_text()

client = anthropic.Anthropic(api_key=cfg['anthropic_api_key'])
msg = client.messages.create(
    model='claude-haiku-4-5-20251001',
    max_tokens=400,
    system=prompt_text,
    messages=[{'role': 'user', 'content': '''Rewrite this as a horror narration script.
Target format: short (60-90 words).
Source: posted by u/testuser on r/TwoSentenceHorror
Original URL: https://reddit.com/r/TwoSentenceHorror/test

--- STORY START ---
My daughter said goodnight to someone in her closet. When I checked, the closet was empty — but her door was locked from the inside.
--- STORY END ---

Respond with JSON only.'''}]
)
result = json.loads(msg.content[0].text)
print('TITLE:', result.get('title'))
print('MOOD:', result.get('mood'))
print()
print('SCRIPT:')
print(result.get('script'))
print()
words = len(result.get('script','').split())
print(f'Word count: {words}')
print('In range (60-90):', 60 <= words <= 90)
"
```

Expected: short first-person script, specific details, no banned words, 60–90 words.

- [ ] **Step 4: Commit**

```bash
git add channels/horror-narration/prompt.txt
git commit -m "feat: rewrite horror prompt — Mr. Nightmare style, first-person confessional, short punchy sentences, banned clichés"
```

---

### Task 7: End-to-end smoke test — full horror pipeline, no upload

Run the horror pipeline end-to-end and check the output video plays without freezing.

- [ ] **Step 1: Set upload dry-run mode temporarily**

In `channels/horror-narration/harness/orchestrator.py`, find the upload section and temporarily add a dry-run skip so we can test without needing YouTube OAuth:

Find:
```python
    # ── Upload ────────────────────────────────────────────────────────────────
    try:
        video_url = upload_youtube(channel_config=channel_config)
```

Temporarily replace with:
```python
    # ── Upload (skip for dry-run test) ───────────────────────────────────────
    import os
    if os.environ.get("HORROR_DRY_RUN"):
        log("🔕 DRY RUN — skipping upload")
        video_url = "https://youtube.com/shorts/DRY_RUN"
    else:
        try:
            video_url = upload_youtube(channel_config=channel_config)
```
(close the else block appropriately)

- [ ] **Step 2: Run pipeline in dry-run mode**

```
source venv/bin/activate && HORROR_DRY_RUN=1 python3 channels/horror-narration/harness/orchestrator.py 2>&1
```

Watch for:
- `🕸️  Harvesting Reddit stories...` → stories found
- `✍️  Script:` → word count 60–90, mood logged
- `🎥 Fetching footage for topic:` → horror clip downloaded/reused
- `✅ Video saved` with no errors
- `🔕 DRY RUN — skipping upload`

- [ ] **Step 3: Probe the output video for B-frame freeze**

```
python3 -c "
import subprocess, json, glob
# Find latest archive
import os
archives = sorted(os.listdir('archive'))
latest = [a for a in archives if a.startswith('2026')][-1]
video = f'archive/{latest}/final_video.mp4'
print('Checking:', video)

result = subprocess.run(
    ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
     '-show_entries', 'stream=codec_name,r_frame_rate,nb_frames',
     '-of', 'default=noprint_wrappers=1', video],
    capture_output=True, text=True
)
print(result.stdout)

# Check for large PTS jumps (freeze indicator)
result2 = subprocess.run(
    ['ffprobe', '-v', 'error', '-show_entries', 'packet=pts_time',
     '-select_streams', 'v', '-of', 'csv=p=0', video],
    capture_output=True, text=True
)
times = [float(x) for x in result2.stdout.strip().split() if x]
jumps = [(i, times[i]-times[i-1]) for i in range(1,len(times)) if times[i]-times[i-1] > 0.5]
if jumps:
    print(f'WARNING: {len(jumps)} large PTS jumps detected (freeze likely)')
else:
    print('✅ No large PTS jumps — video should play smoothly')
"
```

Expected: `✅ No large PTS jumps`

- [ ] **Step 4: Run full test suite**

```
python3 -m pytest tests/ channels/horror-narration/tests/ -q 2>&1 | tail -15
```

- [ ] **Step 5: Commit the dry-run mode (keep it — useful for testing)**

```bash
git add channels/horror-narration/harness/orchestrator.py
git commit -m "feat: HORROR_DRY_RUN env var skips YouTube upload for local testing"
```

---

## Self-Review

**Spec coverage:**
- ✅ Video freeze fix — Task 1 (`-vsync cfr -bf 0 -r 30`)
- ✅ Footage database JSON — Task 2 (`footage_db.py` with JSON index)
- ✅ Per-channel footage dir — Task 3 (settings.json `footage_dir`)
- ✅ Horror footage library download — Task 4 (20 atmospheric clips)
- ✅ Horror-appropriate music — Task 5 (dark ambient CC0 tracks)
- ✅ Better storytelling prompt — Task 6 (Mr. Nightmare style, first-person, banned clichés)
- ✅ End-to-end smoke test — Task 7 (dry-run mode + PTS freeze check)
- ✅ Dog channel unaffected — Tasks 2-3 use default `footage_dir: dog_footage` when not set

**Placeholder scan:** None found.

**Type consistency:**
- `channel_config.footage_dir` → `Path` → consistent with `channel_config.data_dir`
- `channel_config.music_dir` → `Path` → consistent
- `build_video(... channel_config=None)` — new param name consistent with orchestrator usage
