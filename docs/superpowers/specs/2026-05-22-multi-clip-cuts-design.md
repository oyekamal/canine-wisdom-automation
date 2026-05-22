# Multi-Clip Fast Cuts — Design Spec

**Date:** 2026-05-22  
**Status:** Approved

---

## Goal

Replace the current single-clip video assembly with multi-clip concatenation producing 2–3 second cuts throughout each Short. Clips are selected globally across runs using least-recently-used rotation tracked in harness state.

---

## Architecture

Two components change:

1. **`clip_scheduler.py`** (new) — owns all clip selection and usage tracking
2. **`build_video.py`** (modified) — uses clip_scheduler, concatenates clips before encoding

Everything else (caption engine, audio generation, script generation, upload) is unchanged.

---

## Component: clip_scheduler.py

**Location:** `clip_scheduler.py` (repo root, alongside `build_video.py`)

**Public interface:**

```python
def get_clips_for_video(footage_dir: Path, audio_duration: float) -> list[Path]:
    ...
```

**Behaviour:**

- Computes `n_clips = ceil(audio_duration / 2.5)` — minimum clips needed at 2.5s average cut length.
- Reads `state["clip_usage"]` from `harness/storage.py`'s `lock_state()`. Shape: `{"filename.mp4": "2026-05-22T09:41:41"}`.
- Clips not yet in state are treated as never used (sorted before any used clip).
- Sorts available clips by `last_used` ascending (oldest first), picks top `n_clips`.
- If `n_clips > len(available_clips)`, cycles through all clips repeatedly (wraps) until `n_clips` are filled — earlier picks get lower priority on the wrap.
- Writes updated timestamps back to state before returning.
- Returns list of `Path` objects in selection order (oldest-first = first on screen).

**State key:** `"clip_usage"` inside the shared `harness/data/state.json`.

---

## Component: build_video.py changes

**Remove:** `get_random_dog_clip()` call and single `VideoOptimizer` usage.

**Add:** `_concat_clips(clip_paths, audio_duration) -> str`

- Assigns each clip a random duration between 2.0–3.0s (uniform), scaled so the sum equals `audio_duration` exactly (proportional rescaling of the random durations).
- For each clip: extracts a random segment of the assigned duration using ffmpeg `-ss` + `-t` + `-c copy` into a temp file.
- Writes an ffmpeg concat list file (`concat_list.txt` in tempdir): one `file /path/to/clip` + `duration X` entry per clip.
- Runs `ffmpeg -f concat -safe 0 -i concat_list.txt -c copy` to produce a single temp concatenated video.
- Returns path to the concatenated temp file.

**Modified flow in `build_video()`:**

```
clips = get_clips_for_video(footage_dir, audio_duration)   # clip_scheduler
concat_video = _concat_clips(clips, audio_duration)         # new helper
# existing encode: scale + ASS subtitles applied to concat_video
```

---

## Cut Duration Assignment

Given `n` clips and total `audio_duration`:

1. Draw `n` uniform random values in [2.0, 3.0].
2. Scale each by `audio_duration / sum(raw_values)` so they sum exactly to `audio_duration`.
3. Each clip is trimmed to its assigned duration from a random start point within the source clip.
4. If a source clip is shorter than its assigned duration, loop it (`-stream_loop -1`) before trimming.

---

## Testing

**`tests/test_clip_scheduler.py`:**

- `test_new_clips_picked_before_used` — clips with no usage entry are selected first.
- `test_state_updated_after_selection` — after call, selected clips have updated timestamps in state.
- `test_wraps_when_fewer_clips_than_needed` — with 3 clips and n_clips=5, returns 5 paths (some repeated).
- `test_oldest_picked_first` — clip with older timestamp is picked before newer one.

**`tests/test_build_video_concat.py`:**

- `test_cut_durations_sum_to_audio_duration` — given 5 clips and 28s audio, assigned durations sum to 28.0.
- `test_cut_durations_in_range_before_scaling` — raw random values are between 2.0 and 3.0.

---

## Files Changed

| File | Change |
|---|---|
| `clip_scheduler.py` | **New** — clip selection + LRU rotation |
| `build_video.py` | Modify — replace single clip with `_concat_clips()` |
| `utils.py` | Remove `get_random_dog_clip()` or leave (no longer called from build_video) |
| `tests/test_clip_scheduler.py` | **New** |
| `tests/test_build_video_concat.py` | **New** |

---

## Out of Scope

- Sourcing new footage (manual task, no code change)
- Per-topic clip matching (already exists via `clip_path` param, unchanged)
- Cut transitions/effects (plain hard cuts only)
