# Intelligence Loop Design — S2 + S3 + S9
**Date:** 2026-05-17  
**Status:** Approved — ready for implementation planning

---

## Overview

Three subsystems that form a single self-improving data flywheel:

```
Competitor Intel (S3) ──→ learnings.json (S2) ←── Analytics (S9)
        ↓                         ↓
  seeds hook patterns,      evals read it,
  title formulas,           orchestrator reads it,
  thumbnail features        weekly rebuild updates it
```

S2 (`learnings.json`) is the brain — it has no value without data. S3 and S9 are the two data sources that fill it. They must be designed and built together so the schemas lock correctly.

---

## Existing foundation (Session 1)

- `harness/storage.py` — `atomic_write`, `atomic_read`, `lock_state()` (fcntl-based)
- `harness/orchestrator.py` — eval-gated daily pipeline
- `harness/evals/` — 8 evals: hook, script, title, description (LLM judges), audio, video (deterministic), thumbnail + channel (placeholders)
- `harness/data/state.json` — global state, file-locked
- `harness/data/eval_runs/` — per-run eval scores

Nothing in the current evals reads external data. All LLM judges score against abstract criteria. This design fixes that.

---

## New files

| File | Responsibility |
|------|----------------|
| `harness/tools/learnings.py` | Single read/write interface for `learnings.json` |
| `harness/agents/competitor.py` | Channel discovery, daily refresh, weekly deep scan |
| `harness/agents/analytics.py` | Daily YouTube Analytics pull, weekly learnings rebuild |
| `harness/data/learnings.json` | The brain — bootstrapped from competitor data |
| `harness/data/competitors/{channel_id}/channel.json` | Channel-level metadata |
| `harness/data/competitors/{channel_id}/videos/{video_id}.json` | Per-video metadata + engagement |
| `harness/data/competitors/{channel_id}/thumbnails/{video_id}.jpg` | Downloaded thumbnails |
| `harness/data/competitors/{channel_id}/transcripts/{video_id}.txt` | Full transcripts (weekly) |
| `harness/data/performance/index.json` | Rolled-up channel state |
| `harness/data/performance/{video_id}.json` | Per-video analytics with daily snapshots |

**Modified files:**

| File | Change |
|------|--------|
| `harness/evals/hook_eval.py` | Reads top hook patterns from learnings |
| `harness/evals/script_eval.py` | Reads covered_topics for novelty check |
| `harness/evals/title_eval.py` | Reads title formulas + CTR from learnings |
| `harness/orchestrator.py` | Calls competitor refresh + analytics pull in daily run |
| `upload_youtube.py` | Adds analytics OAuth scope |
| `requirements.txt` | Adds youtube-transcript-api, pytrends, openai-whisper |

---

## Section 1: `learnings.json` — The Brain

### Location
`harness/data/learnings.json` — file-locked via `harness/tools/learnings.py` using the same fcntl pattern as `lock_state()`.

### Schema

```json
{
  "updated_at": "2026-05-17T12:00:00",
  "schema_version": 1,
  "hook_patterns": [
    {
      "pattern": "Did you know dogs can [surprising fact]?",
      "avg_3sec_retention_proxy": 0.78,
      "sample_size": 14,
      "confidence": "medium",
      "source": "competitor",
      "last_seen": "2026-05-15"
    }
  ],
  "title_formulas": [
    {
      "formula": "[Number] [Surprising] Things About [Breed]",
      "avg_ctr": 0.092,
      "sample_size": 8,
      "confidence": "high",
      "source": "own_analytics"
    }
  ],
  "thumbnail_features": [
    {
      "feature": "close-up dog face + text overlay under 4 words",
      "avg_ctr": 0.11,
      "sample_size": 22,
      "confidence": "high",
      "source": "competitor"
    }
  ],
  "posting_times": {
    "shorts": {
      "best_hour_utc": 14,
      "best_dow": "Tue",
      "confidence": "low",
      "sample_size": 3
    },
    "long_form": {
      "best_hour_utc": 17,
      "best_dow": "Sat",
      "confidence": "low",
      "sample_size": 0
    }
  },
  "topic_performance": [
    {
      "topic_cluster": "breed comparisons",
      "format": "short",
      "avg_views": 4200,
      "trend": "up",
      "last_updated": "2026-05-17"
    }
  ],
  "pacing_rules": {
    "shorts": {
      "hook_max_sec": 3,
      "words_per_min": 140
    },
    "long_form": {
      "b_roll_cut_every_sec": 7,
      "chapter_count_target": 6
    }
  },
  "anti_patterns": [
    {
      "pattern": "Title starts with 'How to'",
      "reason": "underperformed in 12 of 14 cases",
      "source": "own_analytics",
      "added": "2026-05-17"
    }
  ],
  "format_mix": {
    "shorts_per_week": 7,
    "long_form_per_week": 0,
    "rationale": "insufficient long-form data — will re-evaluate after 4 weeks",
    "next_review": "2026-06-14"
  },
  "covered_topics": [
    {
      "topic": "dogs detecting cancer",
      "posted": "2026-05-17",
      "video_id": "abc123"
    }
  ]
}
```

### Confidence levels

| Level | Sample size | Effect on evals |
|-------|-------------|----------------|
| `"low"` | < 5 | Included in prompt but flagged as low confidence |
| `"medium"` | 5–19 | Standard weight |
| `"high"` | ≥ 20 | Highlighted as proven pattern |

### Source priority
`"own_analytics"` always overwrites `"competitor"` values when both exist for the same pattern. Competitor data is the bootstrap; own data is the truth.

### Cold start
On first run, `learnings.json` is bootstrapped from competitor data only (no own analytics yet). `harness/tools/learnings.py` exposes `bootstrap_from_competitors(competitor_data)` which extracts hook patterns, title formulas, thumbnail features, and posting times from the top-performing competitor videos. This runs once after the first competitor deep scan, before the first harness-posted video.

### `harness/tools/learnings.py` interface

```python
def read_learnings() -> dict
    # Returns parsed learnings.json. Cached in memory for 1 hour.
    # Re-reads from disk if cache is stale.

def get_top_hook_patterns(min_confidence: str = "low", n: int = 3) -> list[dict]
    # Returns top n hook patterns sorted by avg_3sec_retention_proxy.

def get_top_title_formulas(min_confidence: str = "low", n: int = 3) -> list[dict]
    # Returns top n title formulas sorted by avg_ctr.

def get_covered_topics(days: int = 30) -> list[str]
    # Returns topic strings posted in the last N days.

def add_covered_topic(topic: str, video_id: str) -> None
    # Appends to covered_topics. Called by orchestrator after upload.

def update_from_competitor(channel_id: str, videos: list[dict]) -> None
    # Extracts patterns from competitor video list, merges into learnings.
    # Only updates fields with source="competitor" if own_analytics data exists for the same pattern.

def update_from_analytics(video_id: str, performance: dict) -> None
    # Updates hook_patterns, title_formulas, topic_performance based on one video's analytics.
    # Called daily after analytics pull.

def rebuild_from_week(all_performance: list[dict]) -> None
    # Full weekly rebuild: groups all week's videos by hook_pattern_used and
    # title_formula_used, recomputes averages, updates posting_times, appends anti_patterns.
    # Atomically writes new learnings.json.

def bootstrap_from_competitors(competitor_data: list[dict]) -> None
    # One-time call after first competitor deep scan.
    # Populates hook_patterns, title_formulas, thumbnail_features, posting_times
    # from competitor video performance data. Only runs if learnings.json is empty.
```

---

## Section 2: Competitor Intel Agent (S3)

### `harness/agents/competitor.py`

#### Channel discovery (monthly)

Search YouTube Data API with seed keywords: `["dog facts", "dog training tips", "dog breed comparison", "cute dog videos"]`. For each candidate channel returned:

1. Pull channel statistics: `subscriber_count`, `video_count`, `view_count`
2. Pull last 10 uploads: compute `avg_views_last_10`
3. Compute `upload_velocity` = uploads in last 30 days
4. Score niche match with Claude (Haiku): given channel title + description, rate 0–1 how closely it matches the dog-facts Short niche
5. Compute ranking score: `(subscriber_count × 0.3) + (avg_views_last_10 × 0.4) + (upload_velocity × 0.2) + (niche_match_score × 0.1)`
6. Top 5 by ranking score are written to `state.json["competitor_channels"]`

Re-evaluated monthly. A channel is only displaced if a new entrant beats it on ranking score.

**Quota:** ~200 units for discovery run (run once monthly, negligible daily cost).

#### Daily refresh (24h TTL)

For each of the 5 tracked channels:

1. Check `channel.json["last_scanned"]` — skip if < 24h ago
2. Pull top 20 videos from last 7 days: `search.list(channelId, type=video, order=viewCount, publishedAfter=7d_ago)`
3. For each video:
   - Pull full metadata: `videos.list(id, part=snippet,statistics,contentDetails)`
   - Download thumbnail to `thumbnails/{video_id}.jpg` (skip if already exists)
   - Fetch transcript via `youtube-transcript-api`: if available, extract first 15 words as hook, store full transcript in `transcripts/{video_id}.txt`
   - If transcript unavailable: set `transcript_status: "unavailable"` — Whisper runs on weekly scan
   - Compute engagement ratios: `views_per_sub = views / subscriber_count`, `like_rate = likes / views`, `comment_rate = comments / views`
   - Write to `videos/{video_id}.json`
4. Update `channel.json["last_scanned"]`

**Quota:** 5 channels × ~3 API calls per video × 20 videos = ~300 units/day.

#### Weekly deep scan (Sundays)

Same as daily but additionally:
- Pull top 20 comments per video (`commentThreads.list`, 1 unit per video × 20 = 20 units)
- Run Whisper on any video where `transcript_status: "unavailable"` (requires yt-dlp download — audio only, delete after)
- After all channels scanned: call `learnings.update_from_competitor()` to rebuild hook patterns and title formulas from the week's data

**Quota:** ~600 units for weekly deep scan (well within 10k daily limit on Sunday).

### Storage schemas

**`harness/data/competitors/{channel_id}/channel.json`**
```json
{
  "channel_id": "UCxxxxxx",
  "channel_name": "DogFactsDaily",
  "subscriber_count": 120000,
  "ranking_score": 84.2,
  "niche_match_score": 0.91,
  "upload_velocity_30d": 28,
  "last_scanned": "2026-05-17T08:00:00",
  "last_deep_scan": "2026-05-11T03:00:00",
  "discovered_at": "2026-05-01"
}
```

**`harness/data/competitors/{channel_id}/videos/{video_id}.json`**
```json
{
  "video_id": "xyz123",
  "channel_id": "UCxxxxxx",
  "title": "Dogs Can Smell Fear — Here's What They Do About It",
  "description": "...",
  "tags": ["dog facts", "dogs", "animal facts"],
  "duration_sec": 58,
  "published_at": "2026-05-16T14:00:00",
  "publish_hour_utc": 14,
  "publish_dow": "Fri",
  "thumbnail_path": "competitors/UCxxxxxx/thumbnails/xyz123.jpg",
  "transcript_path": "competitors/UCxxxxxx/transcripts/xyz123.txt",
  "transcript_status": "available",
  "hook": "Dogs can smell fear — and here's what they actually do about it",
  "view_count": 85000,
  "like_count": 6200,
  "comment_count": 440,
  "views_per_sub": 0.71,
  "like_rate": 0.073,
  "comment_rate": 0.005,
  "top_comments": [
    {"text": "My dog does this every time!", "like_count": 312}
  ],
  "scraped_at": "2026-05-17T08:15:00"
}
```

---

## Section 3: Analytics + Performance Tracking (S9)

### `harness/agents/analytics.py`

#### OAuth scope

Adds `https://www.googleapis.com/auth/yt-analytics.readonly` to `YOUTUBE_API_SCOPES` in `config.py`. The existing `get_youtube_service()` in `upload_youtube.py` is extended to build both the Data API v3 and Analytics API v2 clients from the same credentials.

#### Daily pull

After each upload, the orchestrator calls `analytics.track_video(video_id, metadata)` which:
1. Creates `harness/data/performance/{video_id}.json` with the video's metadata and an empty `snapshots: []`
2. Registers the video_id in `harness/data/performance/index.json`

Each day, `analytics.pull_daily_snapshots()`:
1. Reads all video_ids from `index.json`
2. For each: calls `youtubeAnalytics.v2.reports.query` with metrics: `views,watchTimeMinutes,averageViewDuration,estimatedMinutesWatched,subscribersGained,likes,comments,impressions,impressionClickThroughRate`
3. Appends a daily snapshot to `snapshots[]` in that video's JSON

**Quota:** Analytics API has a separate quota from Data API. Standard quota is 200 units/day for Analytics — each report query is 1 unit. With <50 videos tracked, well within limits.

#### Performance storage schemas

**`harness/data/performance/{video_id}.json`**
```json
{
  "video_id": "abc123",
  "title": "Dogs Detect Cancer Before Doctors",
  "format": "short",
  "topic": "dogs detecting cancer",
  "topic_cluster": "dog health",
  "uploaded_at": "2026-05-17T09:47:21",
  "hook_pattern_used": "Did you know dogs can [surprising fact]?",
  "title_formula_used": "[Surprising claim] Before [Authority]",
  "eval_scores": {
    "hook_eval": 8.5,
    "script_eval": 7.8,
    "title_eval": 7.2
  },
  "snapshots": [
    {
      "date": "2026-05-18",
      "views": 1240,
      "watch_time_minutes": 620,
      "avg_view_duration_sec": 30,
      "ctr": 0.062,
      "likes": 88,
      "comments": 12,
      "subscribers_gained": 4,
      "impressions": 20000
    }
  ]
}
```

**`harness/data/performance/index.json`**
```json
{
  "updated_at": "2026-05-18T09:00:00",
  "total_videos_tracked": 3,
  "channel_stats": {
    "subscriber_count": 3450,
    "total_views_all_time": 28400
  },
  "kpis_7d": {
    "avg_views_per_video": 1240,
    "avg_ctr": 0.062,
    "avg_watch_time_min": 620,
    "subscribers_gained": 12
  },
  "videos": [
    {"video_id": "abc123", "format": "short", "uploaded_at": "2026-05-17"}
  ]
}
```

#### Weekly learnings rebuild

Every Sunday, `analytics.rebuild_learnings_from_week()`:

1. Loads all `performance/{video_id}.json` files with `uploaded_at` in last 7 days
2. Groups by `hook_pattern_used` → averages `ctr` and `avg_view_duration_sec` across the group → updates `learnings.hook_patterns`
3. Groups by `title_formula_used` → averages `ctr` → updates `learnings.title_formulas`
4. Finds the `publish_hour_utc` + `publish_dow` of the top 3 videos by views → updates `learnings.posting_times.shorts`
5. Any hook/title with < 0.04 CTR and ≥ 5 samples → appended to `learnings.anti_patterns`
6. Calls `learnings.rebuild_from_week()` to atomically write the updated file

---

## Section 4: Eval Upgrades

### `hook_eval.py`

New prompt includes learnings context:

```
Top-performing hook patterns for this channel (sorted by retention):
1. "Did you know dogs can [fact]?" — avg 78% 3-sec retention (14 samples, medium confidence)
2. "The reason dogs [behaviour] will shock you" — avg 71% (8 samples, medium confidence)

Compare the generated hook against these patterns. Does it use a similar structure?
Does it create equivalent or stronger curiosity?
```

### `script_eval.py`

Novelty check now uses real data:

```
Topics covered in the last 30 days (do NOT repeat these):
- dogs detecting cancer (2026-05-17)
- why dogs lick wounds (2026-05-14)
```

### `title_eval.py`

Now benchmarks against real CTR:

```
Top title formulas for this channel:
1. "[Surprising claim] Before [Authority]" — avg CTR 6.2% (3 samples, low confidence)

Competitor top titles this week:
- "Dogs Can Smell Fear — Here's What They Do" — 85k views
- "Your Dog is Doing THIS for a Reason 🐕" — 62k views
```

### `learnings_freshness_eval.py` (new)

Deterministic check run weekly:
- Any `hook_patterns` or `title_formulas` entry with `last_seen` > 14 days: downgrade confidence one level
- Any entry with `sample_size` = 0 and `last_seen` > 30 days: remove
- Writes updated learnings.json, emits EvalResult (pass/fail based on whether learnings has ≥ 3 medium/high confidence entries)

---

## Orchestrator changes

### Daily run additions

```python
# After init:
competitor.refresh_if_stale()       # skips if all channels < 24h old

# After upload:
analytics.track_video(video_id, metadata)
learnings.add_covered_topic(topic, video_id)

# After analytics pull:
analytics.pull_daily_snapshots()
```

### Weekly run (Sundays)

```python
competitor.deep_scan()              # full scan + Whisper fallback
analytics.rebuild_learnings_from_week()
learnings_freshness_eval.run()
channel_eval.run()                  # now has real data
```

---

## New dependencies

```
youtube-transcript-api>=0.6.0    # competitor transcripts (no download needed)
yt-dlp>=2024.1.1                 # audio-only download for Whisper fallback
openai-whisper>=20231117         # local transcription fallback
pytrends>=4.9.0                  # Google Trends (Session 5 — topic agent)
```

Note: `pytrends` is listed here for completeness but not used until Session 5 (trend + topic agent).

---

## Build order for this session

1. `harness/data/learnings.json` — initial schema + bootstrap structure
2. `harness/tools/learnings.py` — read/write interface + cache
3. `harness/agents/competitor.py` — channel discovery + daily refresh + weekly deep scan
4. `harness/agents/analytics.py` — daily pull + weekly rebuild
5. Eval upgrades — hook_eval, script_eval, title_eval read from learnings
6. `harness/evals/learnings_freshness_eval.py` — new deterministic eval
7. Orchestrator wiring — daily + weekly cadence
8. Tests for all of the above

---

## Quota summary

| Operation | Units/call | Calls/day | Units/day |
|-----------|-----------|-----------|-----------|
| Competitor daily refresh (5 channels × 20 vids × 3 calls) | 1 | 300 | 300 |
| Video upload | 1600 | 1 | 1600 |
| Analytics pull (per video) | 1 | ~10 | 10 |
| Channel stats | 1 | 5 | 5 |
| **Total daily** | | | **~1915** |
| Weekly deep scan additions (comments + channel discovery) | 1 | ~220 | 220 (Sunday only) |

All well within the 10,000 unit daily quota.

---

## Not in scope for this session

- Long-form pipeline (S7)
- Footage sourcing / yt-dlp clip library (S4)
- Thumbnail generation (S8)
- Comment agent (S10)
- Self-healing loop (S11)
- Topic/trend agent (S5) — `pytrends` dependency listed but not wired
