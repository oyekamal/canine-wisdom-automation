# Multi-Channel YouTube Automation Pipeline

This repo runs **multiple YouTube channels** from one codebase. Each channel is fully isolated — its own footage, music, OAuth credentials, Claude prompt, and state. Adding a new channel requires zero code changes.

---

## Quick Start — Run a Channel

```bash
source venv/bin/activate

# Canine Wisdom (dog facts → YouTube Shorts)
python3 -m harness.orchestrator --channel canine-wisdom

# Horror Narration — test without uploading
HORROR_DRY_RUN=1 python3 channels/horror-narration/harness/orchestrator.py

# Horror Narration — upload to YouTube (requires OAuth in channels/horror-narration/)
python3 channels/horror-narration/harness/orchestrator.py
```

---

## Channel Directory Structure

```
channels/
  canine-wisdom/
    settings.json          ← niche, voice_id, topic_clusters, affiliate_links,
                              footage_dir="dog_footage", music_dir="assets/music"
    prompt.txt             ← Claude script prompt (dog facts style)
    token.json             ← YouTube OAuth (symlink → root token.json)
    client_secrets.json    ← YouTube OAuth (symlink → root client_secrets.json)
    data/                  ← state.json, learnings.json, evals, analytics, incidents

  horror-narration/
    settings.json          ← voice_id, subreddits, cut_duration_secs=20,
                              footage_dir="horror_footage", music_dir="assets/music/horror"
    prompt.txt             ← Mr. Nightmare style prompt (first-person, no clichés, CTA)
    token.json             ← YouTube OAuth for horror channel (add when ready)
    client_secrets.json    ← YouTube OAuth for horror channel (add when ready)
    data/                  ← per-channel state (used_story_ids, recent_runs)
    harness/
      orchestrator.py      ← entry point
      reddit_harvest.py    ← PullPush API scraper + Reddit media downloader
      story_scorer.py      ← ranks stories by hook words, length, upvotes
      story_rewriter.py    ← Claude rewrite + ElevenLabs voice picker by mood
      media_converter.py   ← converts Reddit images → video (Ken Burns zoom)
```

---

## Footage & Music Libraries (never mixed between channels)

```
dog_footage/               ← Canine Wisdom only — portrait dog clips from Pexels
horror_footage/            ← Horror channel only — dark atmospheric clips
assets/music/              ← Dog channel music (upbeat Kevin MacLeod CC-BY tracks)
assets/music/horror/       ← Horror channel music (dark ambient: Danse Macabre,
                              Lightless Dawn, Unseen Horrors, Dark Times, etc.)
```

### Why the dog channel doesn't auto-download new music

The dog channel uses Kevin MacLeod tracks already in `assets/music/`. These are CC-BY licensed and were placed there manually. The channel doesn't need new music per run — it rotates randomly from the existing library.

If you want to add more dog-channel music: drop any CC-BY `.mp3` into `assets/music/` and it gets picked up automatically on the next run.

### Why the dog channel doesn't always download new footage

It does — on every run it calls `fetch_footage_for_topic()` which downloads one fresh clip from Pexels matching the topic (e.g. "dog facts" → dog portrait clip). But it also reuses existing clips from `dog_footage/` via LRU rotation so the same clip doesn't repeat too often. You'll see `[footage] Already have: ...` when the clip was already downloaded, or `[footage] Downloading ...` when it's fresh.

To force fresh downloads: delete clips from `dog_footage/` and the next run will re-download.

---

## Canine Wisdom — How It Works

1. **Topic Queue** — Builds a list of trending dog topics from Google autocomplete + competitor analysis
2. **Format** — Harness decides Short (1080×1920) or Long-form (1920×1080) based on topic cluster
3. **Script** — Claude generates a viral dog facts script with hook, captions, hashtags
4. **Evals** — Script scored for hook strength, novelty, title quality (retries up to 3×)
5. **Footage** — Downloads one fresh Pexels clip + mixes with existing `dog_footage/` library
6. **Audio** — ElevenLabs TTS with word-level timestamps for captions
7. **Video** — ffmpeg: scale → warm color grade → vignette, libx264 CRF 18
8. **Music** — Random upbeat track from `assets/music/` (Kevin MacLeod CC-BY)
9. **Upload** — YouTube Shorts via OAuth, with affiliate links auto-matched to topic

---

## Horror Channel — How It Works

1. **Harvest** — Fetches top Reddit stories from r/nosleep, r/shortscarystories, r/TwoSentenceHorror, r/LetsNotMeet, r/Paranormal via [PullPush API](https://api.pullpush.io) — no credentials needed
2. **Media check** — If the Reddit post has an attached image (`i.redd.it`, imgur) or video (`v.redd.it`), it's downloaded and used as the primary footage
3. **Score** — Ranks stories by hook words in title + word count fit + upvote signal. Skips already-used stories.
4. **Rewrite** — Claude rewrites in Mr. Nightmare style: first-person confessional, short punchy sentences, concrete details ("3:47 AM", "the third stair"), no clichés (banned: ethereal, malevolent, eldritch, etc.)
5. **CTA** — Every script ends with a natural follow-back line ("Follow if you want to hear more stories like this. I have too many.")
6. **Voice** — Auto-picks ElevenLabs voice by mood: George/dread, Callum/eerie, Harry/intense, Sarah/paranormal
7. **Footage** — Reddit post media first; falls back to Pexels atmospheric clips matched to topic cluster
8. **Image conversion** — Reddit images converted to video with slow Ken Burns zoom (ffmpeg `-loop 1`)
9. **Cut pacing** — `cut_duration_secs: 20` → 2 cuts per Short (slow, atmospheric — not TikTok fast)
10. **Music** — Dark ambient from `assets/music/horror/` (Danse Macabre, Crossing the Chasm, etc.)
11. **Upload** — YouTube via OAuth (`HORROR_DRY_RUN=1` to skip upload for testing)

---

## Adding a New Channel

1. Create `channels/<slug>/settings.json`:
```json
{
  "channel_name": "My Channel",
  "niche": "description of what this channel is about",
  "voice_id": "ElevenLabs_voice_id",
  "youtube_category_id": "22",
  "topic_clusters": ["topic a", "topic b"],
  "description_template": "{video_title}\n\n{video_script}\n\n{hashtags}",
  "affiliate_links": {"default": {"product": "...", "url": "https://amzn.to/..."}},
  "footage_dir": "my_channel_footage",
  "music_dir": "assets/music/my_channel",
  "cut_duration_secs": 5
}
```
2. Create `channels/<slug>/prompt.txt` with the Claude prompt
3. Place `client_secrets.json` + `token.json` (YouTube OAuth) in the channel dir
4. Run: `python3 -m harness.orchestrator --channel <slug>`

No code changes needed.

---

## Maintenance & Utilities

```bash
# Download fresh horror footage (run once or when library is low)
python3 -m harness.tools.horror_footage_downloader

# Download horror ambient music
python3 -m harness.tools.horror_music_downloader

# Rebuild footage index after manual additions
python3 -c "from footage_db import build_footage_index; from pathlib import Path; \
  build_footage_index(Path('horror_footage'), Path('horror_footage/footage_index.json'))"
```

---

## Key Settings per Channel

| Setting | Canine Wisdom | Horror |
|---|---|---|
| `footage_dir` | `dog_footage` | `horror_footage` |
| `music_dir` | `assets/music` | `assets/music/horror` |
| `cut_duration_secs` | not set (1.5s default — fast cuts) | `20` (slow, 2 cuts) |
| `voice_id` | `pNInz6obpgDQGcFmaJgB` | auto-picked by mood |
| YouTube category | `15` (Pets & Animals) | `24` (Entertainment) |

---

## Environment Variables

```
ANTHROPIC_API_KEY=       Claude API key
ELEVENLABS_API_KEY=      ElevenLabs TTS key
ELEVENLABS_VOICE_ID=     Default voice (overridden per channel)
PEXELS_API_KEY=          Pexels footage API
PIXABAY_API_KEY=         Pixabay footage fallback
HORROR_DRY_RUN=1         Skip YouTube upload for horror channel testing
```

---

## Server Deployment (Hetzner / Ubuntu VPS)

### One-time setup

```bash
# 1. Clone repo
git clone <repo_url> canine-wisdom-automation
cd canine-wisdom-automation

# 2. Install system dependencies
sudo apt update
sudo apt install -y python3.11 python3.11-venv ffmpeg yt-dlp

# 3. Create virtual environment and install all packages
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Add credentials
cp .env.example .env          # fill in your API keys
# Copy OAuth files for each channel:
cp /your/local/token.json channels/canine-wisdom/token.json
cp /your/local/client_secrets.json channels/canine-wisdom/client_secrets.json

# 5. Pre-download Supertonic model (~50MB, cached at ~/.cache/supertonic-mnn/)
python3 -c "from supertonic_mnn import SupertonicTTS; SupertonicTTS()"
```

### Cron setup (daily runs)

```bash
crontab -e

# Canine Wisdom — 9 AM daily
0 9 * * * cd /path/to/canine-wisdom-automation && source venv/bin/activate && python3 -m harness.orchestrator --channel canine-wisdom >> run_logs/cron_dog.log 2>&1

# Horror channel — 8 PM daily
0 20 * * * cd /path/to/canine-wisdom-automation && source venv/bin/activate && python3 channels/horror-narration/harness/orchestrator.py >> run_logs/cron_horror.log 2>&1
```

### TTS Fallback

ElevenLabs is the primary TTS. If it fails (API down, key expired, rate limited), the pipeline **automatically falls back to Supertonic** — free, runs on CPU, no API key needed.

| | ElevenLabs | Supertonic (fallback) |
|---|---|---|
| Cost | ~$0.30/30s | Free |
| Quality | High | Good |
| Word timestamps | Exact | Approximate (evenly spaced) |
| Requires internet | Yes | No (after first download) |
| Voices | 10+ | M1, M2, F1, F2 |
