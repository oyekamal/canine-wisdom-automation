# Canine Wisdom Harness — Design Spec
**Date:** 2026-05-17  
**Status:** Draft — awaiting user approval before implementation plan

---

## 1. Problem

The existing pipeline (`main.py`) is a dumb linear runner: generate → audio → video → upload. It posts blindly with no feedback loop, no competitor awareness, no content quality gates, and no way to learn from what works.

---

## 2. Goal

Wrap the existing pipeline in an autonomous harness that:
- Selects topics based on trend data and competitor signals
- Scores every artifact (script, title, thumbnail, audio, video) before it ships
- Reads YouTube Analytics daily and tracks what's working
- Responds to comments autonomously in channel voice
- Detects regressions and self-heals by editing its own code

---

## 3. Architecture Overview

```
harness/
├── orchestrator.py          # Daily entry point — replaces main.py
├── storage.py               # Atomic JSON read/write + file lock for state.json
├── agents/
│   ├── competitor.py        # YouTube Data API: track 5–N competitor channels
│   ├── trend.py             # Rising topics: YouTube suggest + Google Trends
│   ├── comment.py           # Pull, classify, reply to comments via Claude
│   └── healer.py            # Self-healing: diagnose → patch → test → commit
├── evals/
│   ├── hook_eval.py         # LLM judge: first-3-sec hook strength ≥7/10
│   ├── script_eval.py       # LLM judge: accuracy, novelty, pacing ≥7/10
│   ├── title_eval.py        # LLM judge: CTR vs competitor titles ≥7/10
│   ├── thumbnail_eval.py    # LLM judge: contrast, text, emotion — best of N
│   ├── description_eval.py  # LLM judge: SEO coverage, CTA, length ≥7/10
│   ├── audio_eval.py        # Deterministic: loudness, clipping, duration match
│   ├── video_eval.py        # Deterministic: resolution, aspect ratio, no black frames
│   └── channel_eval.py      # Weekly: subscribers, avg views, CTR vs prior week
├── tools/
│   ├── thumbnail.py         # Thumbnail generation (API TBD — harness researches)
│   ├── seo.py               # Title, description, tags, chapters, hashtags builder
│   ├── analytics.py         # Pull YouTube Analytics API, cache 1h
│   └── captions.py          # Auto-caption generation for video (Whisper or alt)
├── tests/
│   ├── test_storage.py      # Atomic write, lock contention, schema validation
│   ├── test_evals.py        # All 8 evals with fixture data
│   └── test_agents.py       # Competitor, trend, comment, healer unit tests
├── data/                    # All persistent state (JSON only, never SQLite)
│   ├── performance/         # {video_id}.json + index.json
│   ├── competitors/         # {channel_id}.json
│   ├── topics/              # {YYYY-MM-DD}.json daily topic queue
│   ├── eval_runs/           # {YYYY-MM-DD}/{video_id}/{eval_name}.json
│   ├── incidents/           # {timestamp}-{id}.json + .md report
│   ├── comments/            # {video_id}.json
│   ├── thumbnails/          # {video_id}.json (variants + A/B results)
│   └── state.json           # Global harness state (last run, KPIs, config)
├── CHANGELOG.md             # Auto-updated by healer on every self-edit
└── README.md                # How to run, extend, and bound the self-healing loop
```

The existing scripts (`generate_script.py`, `build_video.py`, etc.) are **unchanged initially**. The harness wraps them. As evals identify improvement opportunities, the healer is allowed to rewrite them.

---

## 4. JSON Schemas

### `data/state.json`
```json
{
  "last_run": "2026-05-17T09:00:00",
  "last_weekly_eval": "2026-05-11",
  "current_kpis": {
    "avg_views_7d": 1200,
    "avg_ctr_7d": 0.045,
    "subscribers": 3400,
    "watch_time_minutes_7d": 8900
  },
  "competitor_channels": ["UCxxxxxx", "UCyyyyyy"],
  "config": {
    "post_hour_local": 9,
    "max_competitors": 5,
    "eval_pass_threshold": 7,
    "thumbnail_api": null
  }
}
```

### `data/performance/{video_id}.json`
```json
{
  "video_id": "abc123",
  "title": "Dogs can smell cancer...",
  "uploaded_at": "2026-05-17T09:15:00",
  "topic": "dog cancer detection",
  "hook_score": 8.5,
  "title_score": 7.2,
  "thumbnail_variant_winner": "B",
  "analytics": {
    "views": 4200,
    "ctr": 0.062,
    "avg_watch_time_sec": 38,
    "likes": 310,
    "comments": 44,
    "pulled_at": "2026-05-18T09:05:00"
  }
}
```

### `data/topics/{YYYY-MM-DD}.json`
```json
{
  "generated_at": "2026-05-17T08:30:00",
  "topics": [
    {"rank": 1, "topic": "dog cancer detection", "score": 94, "source": "youtube_suggest"},
    {"rank": 2, "topic": "why dogs lick wounds", "score": 88, "source": "competitor_title"},
    {"rank": 3, "topic": "oldest dog breeds", "score": 81, "source": "google_trends"}
  ],
  "used": "dog cancer detection"
}
```

### `data/competitors/{channel_id}.json`
```json
{
  "channel_id": "UCxxxxxx",
  "channel_name": "DogFactsDaily",
  "pulled_at": "2026-05-17T08:00:00",
  "subscriber_count": 120000,
  "recent_videos": [
    {
      "video_id": "xyz",
      "title": "Dogs Can Smell Fear...",
      "views": 85000,
      "likes": 6200,
      "published_at": "2026-05-16T14:00:00",
      "hook": "Dogs can smell fear — and here's what they do about it"
    }
  ],
  "post_cadence_per_day": 1.2,
  "avg_views": 42000
}
```

### `data/eval_runs/{YYYY-MM-DD}/{video_id}/{eval_name}.json`
```json
{
  "eval": "hook_eval",
  "video_id": "abc123",
  "run_at": "2026-05-17T09:03:00",
  "score": 8.5,
  "passed": true,
  "threshold": 7,
  "reasoning": "Strong emotional opener, creates curiosity immediately",
  "input_excerpt": "Did you know dogs can detect cancer before doctors can?"
}
```

### `data/incidents/{timestamp}-{id}.json`
```json
{
  "id": "inc-20260517-001",
  "timestamp": "2026-05-17T09:10:00",
  "trigger": "channel_eval",
  "severity": "high",
  "what_failed": "CTR dropped 30% week-over-week (0.062 → 0.043)",
  "hypothesis": "Titles are too long and front-loading facts instead of questions",
  "code_path": "generate_script.py:prompt",
  "fix_branch": "harness-auto-fix/inc-20260517-001",
  "fix_status": "applied",
  "attempts": 1,
  "resolved_at": "2026-05-17T09:25:00"
}
```

### `data/thumbnails/{video_id}.json`
```json
{
  "video_id": "abc123",
  "generated_at": "2026-05-17T09:05:00",
  "api_used": "pillow",
  "variants": [
    {"id": "A", "path": "outputs/thumbnail_A.jpg", "score": 7.1},
    {"id": "B", "path": "outputs/thumbnail_B.jpg", "score": 8.3}
  ],
  "selected": "B",
  "ab_result": null
}
```

### `data/comments/{video_id}.json`
```json
{
  "video_id": "abc123",
  "pulled_at": "2026-05-17T09:20:00",
  "comments": [
    {
      "comment_id": "Ugxxx",
      "author": "dogmom2023",
      "text": "What breed is that?",
      "classification": "question",
      "reply_sent": true,
      "reply_text": "That's a beautiful Golden Retriever! They're one of the most popular breeds...",
      "replied_at": "2026-05-17T09:21:00"
    }
  ]
}
```

---

## 5. Subsystems

### 5.1 Orchestrator (`harness/orchestrator.py`)
Daily cron entry point. Runs in sequence:
1. Load `state.json`
2. **Trend agent** — build topic queue for today if not already built
3. **Competitor agent** — refresh competitor data if >24h stale
4. **Content generation** — call `generate_script.py` with top topic + hook patterns from competitors
5. **Evals** — run `hook_eval`, `script_eval`, `title_eval` — retry up to 3× if any fail (regenerate)
6. **Thumbnail generation** — call `tools/thumbnail.py`, score with `thumbnail_eval`, pick best
7. **SEO** — call `tools/seo.py`, score with `description_eval` and `title_eval`
8. **Audio + Video** — call existing `generate_audio.py`, `build_video.py`
9. **Hard evals** — `audio_eval`, `video_eval` — halt pipeline if fail
10. **Upload** — call existing `upload_youtube.py` with enriched metadata
11. **Analytics pull** — pull yesterday's video performance, update `performance/index.json`
12. **Comment agent** — pull new comments, classify, reply
13. **Update `state.json`**

Weekly (Sunday): run `channel_eval`, trigger healer if regression.

### 5.2 Competitor Agent (`harness/agents/competitor.py`)
- Seed list of 5 channels in `state.json`
- Pull via YouTube Data API v3: `channels.list` + `search.list` (recent videos)
- Cache in `data/competitors/{channel_id}.json`, 24h TTL
- Extract hook patterns from recent titles (first clause before " — " or "...")
- Feed hook patterns to `generate_script.py` as context

Quota budget: ~100 units/channel × 5 = 500 units/day.

### 5.3 Trend Agent (`harness/agents/trend.py`)
- YouTube search suggest: scrape autocomplete for "dog [letter]" queries (zero quota cost — HTTP only)
- Google Trends: `pytrends` library for rising dog-related queries
- Competitor title keyword extraction (from cached competitor data — no API calls)
- Score topics by: search suggest frequency + trends velocity + competitor coverage
- Write ranked queue to `data/topics/{YYYY-MM-DD}.json`

### 5.4 Thumbnail Generation (`harness/tools/thumbnail.py`)
- **Phase 1 (shipped):** Pillow compositing — dog image frame + bold title text + color overlay. Zero API cost.
- **Phase 2 (harness decides):** When `thumbnail_eval` scores consistently <7, the healer researches image gen APIs (DALL-E, Stability, Flux), proposes one with cost estimate, and prompts the user for a `THUMBNAIL_API_KEY` before enabling it.
- Always generates ≥2 variants; eval picks the winner.

### 5.5 SEO Module (`harness/tools/seo.py`)
- Takes topic + script + competitor titles
- Generates: title variants (3), description, 10 tags, hashtags
- Scores each title against competitor benchmarks using `title_eval`
- Picks the highest-scoring title
- Builds description with CTA, keyword density check, chapter timestamps if >60s

### 5.6 Evals (`harness/evals/`)
All LLM evals use Claude (Haiku for speed/cost, Opus for weekly `channel_eval`).
Every eval writes a result JSON to `data/eval_runs/`.

| Eval | Type | Threshold | Retry? |
|------|------|-----------|--------|
| `hook_eval` | LLM judge | ≥7/10 | Yes — regenerate script |
| `script_eval` | LLM judge | ≥7/10 | Yes — regenerate script |
| `title_eval` | LLM judge | ≥7/10 | Yes — regenerate title |
| `thumbnail_eval` | LLM judge | best of N | No — pick best |
| `description_eval` | LLM judge | ≥7/10 | Yes — rewrite description |
| `audio_eval` | Deterministic | pass/fail | No — halt pipeline |
| `video_eval` | Deterministic | pass/fail | No — halt pipeline |
| `channel_eval` | LLM + data | trending up | Triggers healer |

### 5.7 Analytics (`harness/tools/analytics.py`)
- YouTube Analytics API: pull views, CTR, avg watch time, likes, comments per video
- Cache 1h (channel's own data), 24h (historical)
- Quota budget: ~50 units/day for analytics reads
- Write to `data/performance/{video_id}.json`, update `data/performance/index.json`

### 5.8 Comment Agent (`harness/agents/comment.py`)
- Pull comments via YouTube Data API: `commentThreads.list`
- Classify with Claude: spam / question / praise / criticism / minor / harassment
- Rules:
  - Skip: spam, minor indicators, harassment, DM requests
  - Reply: questions + praise — Claude rewrites each reply in channel-voice persona
  - Never send identical text across comments
- Write state to `data/comments/{video_id}.json`

### 5.9 Self-Healing Loop (`harness/agents/healer.py`)
Triggered by: any eval failure after 3 retries, or weekly `channel_eval` regression.

Sequence:
1. Write `data/incidents/{timestamp}-{id}.md` + `.json`
2. Web search for solutions (YouTube Shorts best practices, library alternatives, etc.)
3. Create branch `harness-auto-fix/{incident-id}`
4. Apply patch to relevant module
5. Run the relevant eval(s) on patched code
6. If pass: commit with clear message, merge to main, update `CHANGELOG.md`
7. If fail after 3 attempts: log and surface to user (print clearly at next run)

**Guardrails:**
- May: install pip packages, add/edit files, modify `requirements.txt`, call web search
- May NOT: rotate or expose API keys, delete `archive/` or `run_logs/`, push to remote without approval, spend money on paid APIs without surfacing the cost estimate first

### 5.10 Storage (`harness/storage.py`)
- Atomic writes: write to `.tmp`, fsync, rename
- `fcntl.flock` on `state.json` (only file with concurrent write risk)
- Pretty-print JSON with 2-space indent, sorted keys where order doesn't matter
- Schema validation via simple `jsonschema` or hand-rolled type checks on read

---

## 6. YouTube Data API Quota Budget

| Operation | Units/call | Calls/day | Units/day |
|-----------|-----------|-----------|-----------|
| Competitor channel pull (5) | 100 | 5 | 500 |
| Video upload | 1600 | 1 | 1600 |
| Comment pull (10 videos) | 1 | 10 | 10 |
| Analytics read | 1 | 5 | 5 |
| Search (topic validation) | 100 | 2 | 200 |
| **Total** | | | **~2315** |

Well under the 10,000 daily limit. Leaves ~7,685 units of headroom for harness growth.

---

## 7. Build Order (Sessions)

### Session 1 — Foundation + Evals
1. `harness/storage.py` + tests
2. `harness/evals/` — all 8 evals + tests
3. `harness/orchestrator.py` — wraps existing pipeline, runs evals, writes incident on failure
4. End state: daily run works end-to-end with eval gating

### Session 2 — Intelligence Layer
5. `harness/agents/competitor.py` + tests
6. `harness/agents/trend.py` + tests
7. Extend `generate_script.py` to accept topic + hook patterns
8. `harness/tools/seo.py` + `title_eval` integration + tests

### Session 3 — Thumbnail + Analytics
9. `harness/tools/thumbnail.py` (Pillow phase 1) + tests
10. `harness/tools/analytics.py` + tests
11. `harness/data/performance/` tracking

### Session 4 — Comment Agent + Self-Healing
12. `harness/agents/comment.py` + tests
13. `harness/agents/healer.py` + tests
14. `harness/CHANGELOG.md` auto-update
15. `harness/README.md`
16. Root `README.md` migration note

---

## 8. New Dependencies

```
pytrends>=4.9.0          # Google Trends
Pillow>=10.0.0           # Thumbnail generation (Phase 1)
jsonschema>=4.0.0        # JSON schema validation in storage.py
openai-whisper           # Captions (research if better alt exists)
```

Thumbnail API key (DALL-E / Stability / other) — TBD, harness surfaces options before enabling.

---

## 9. Constraints & Decisions

- **No SQLite** — all state in JSON under `harness/data/`
- **No web UI** — headless; terminal output is the interface
- **Full autonomy** — healer commits and merges without approval; user sees CHANGELOG
- **Thumbnail API** — harness researches and proposes options before spending money
- **Competitors** — start at 5, harness grows list as quota allows
- **Compliance** — no replies to comments flagged as minors, harassment, or DM requests; all auto-replies unique (no templates)
