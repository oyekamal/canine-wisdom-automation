# Canine Wisdom by King — YouTube Shorts Automation Pipeline

**Automatically generate viral dog fact YouTube Shorts and publish them with a single command.**

Turn your dog footage into engaging, AI-narrated YouTube Shorts that educate and entertain. No editing skills required. One command: `python main.py` → Your Short goes live in minutes.

---

## How It Works

The pipeline automates four steps—from dog footage to a published YouTube Short:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│  1. SCRIPT GENERATION        2. AUDIO CREATION       3. VIDEO BUILD      │
│  (Claude AI)                 (ElevenLabs TTS)        (ffmpeg editing)    │
│       │                            │                         │           │
│       ├─ Random dog fact      ├─ Natural voice       ├─ Dog footage     │
│       ├─ Catchy hook          ├─ 10-15 sec narration ├─ Audio sync      │
│       └─ YouTube captions     └─ MP3 file            └─ 1080x1920 format│
│            │                        │                         │           │
│            └────────────────────────┴─────────────────────────┘           │
│                                     │                                     │
│  4. UPLOAD TO YOUTUBE                                                    │
│  (Google OAuth)                                                          │
│       │                                                                  │
│       ├─ Auto-title                                                      │
│       ├─ Auto-description                                               │
│       ├─ Auto-tags                                                       │
│       └─ Publish (LIVE!)                                                │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

**Each run:** ~2-5 minutes, fully automated, no manual editing.

---

## What You Get

✅ **Original scripts** — New dog fact every time (powered by Claude AI)  
✅ **Professional audio** — Natural voice narration (ElevenLabs)  
✅ **Engaging visuals** — Your dog footage synced with captions  
✅ **Optimal format** — 1080x1920 vertical (YouTube Shorts standard)  
✅ **Instant publishing** — Auto-upload to your YouTube channel  
✅ **No editing** — Hands-off automation  

---

## Quick Start

**3 steps to your first Short:**

### 1. Install & Configure
```bash
# Clone or navigate to project
cd canine-wisdom-automation

# Install dependencies
pip install -r requirements.txt

# Install ffmpeg (if not already installed)
# Mac: brew install ffmpeg
# Linux: sudo apt install ffmpeg
# Windows: Download from ffmpeg.org

# Copy and edit .env
cp .env.example .env
# → Add your API keys (see SETUP.md for details)
```

### 2. Add Dog Footage
```bash
# Create folder (if not exists) and add videos
mkdir -p dog_footage
# Copy your .mp4 or .mov files here
```

### 3. Run
```bash
python main.py
```

**That's it.** Your Short publishes in 2-5 minutes.

---

## Setup & Configuration

**New to this?** Follow the [SETUP.md](./SETUP.md) guide (takes ~15 minutes).

**Already set up?** Here's the quick reference:

### Required API Keys

You need three API keys in your `.env` file:

| Key | Where to Get | What It Does |
|-----|--------------|--------------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/keys) | Generates dog facts (Claude AI) |
| `ELEVENLABS_API_KEY` | [elevenlabs.io/settings](https://elevenlabs.io/settings/api-keys) | Creates voice narration |
| `ELEVENLABS_VOICE_ID` | [elevenlabs.io/voices](https://elevenlabs.io/voices) (optional, has default) | Which voice reads the facts |

### Google OAuth Credentials

YouTube uploads require `client_secrets.json`:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Enable **YouTube Data API v3**
3. Create **OAuth 2.0 Desktop Application** credentials
4. Download JSON file → save as `client_secrets.json` in project root

**First run:** You'll be prompted to authorize in your browser. Grant access, and `token.pickle` is saved for future runs.

### Environment Variables

```bash
# .env file (copy from .env.example)

# Anthropic Claude API
ANTHROPIC_API_KEY=sk-ant-your-key-here

# ElevenLabs Text-to-Speech
ELEVENLABS_API_KEY=sk_your-key-here
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB  # Default: Joshua (male voice)
```

---

## How to Change Settings

### Change Voice

Each dog fact is narrated by an AI voice. To pick a different voice:

1. Visit [elevenlabs.io/voices](https://elevenlabs.io/voices)
2. Click a voice to preview
3. Copy its **Voice ID** (shown in the preview panel)
4. Edit `.env` and update `ELEVENLABS_VOICE_ID`

**Popular voices:**
- `pNInz6obpgDQGcFmaJgB` — Joshua (warm male)
- `9BWtsMINqrJLrRacOk9x` — Ava (clear female)
- `EXAVITQu4vr4xnSDxMaL` — Bella (expressive female)

### Add or Change Dog Footage

1. Add new `.mp4` or `.mov` files to `dog_footage/`
2. The pipeline picks a random clip each run
3. Recommended: 60+ seconds per clip (pipeline auto-clips to 59-60 sec)

### Adjust Video Quality

Edit `config.py` if needed:

```python
VIDEO_WIDTH = 1080      # 1080 is YouTube Shorts standard
VIDEO_HEIGHT = 1920     # Vertical format
VIDEO_CRF = 20          # Quality (0=highest, 51=lowest; 20 is good)
VIDEO_PRESET = "fast"   # Speed (ultrafast, superfast, fast, medium, slow)

AUDIO_BITRATE = "192k"  # 192k is high quality
```

### Schedule Daily Posts

Run the pipeline daily without manual interaction:

**Mac/Linux (Cron):**
```bash
crontab -e
# Add line:
0 9 * * * cd /path/to/canine-wisdom-automation && python main.py >> run_logs/cron.log 2>&1
```

**Windows (Task Scheduler):**
1. Open Task Scheduler
2. Create Basic Task → Daily at 9:00 AM
3. Action: Run `python main.py` in project folder

---

## Project Structure

```
canine-wisdom-automation/
├── main.py                  # Master runner — execute this
├── config.py                # Load API keys & validate setup
├── generate_script.py       # Step 1: Claude generates dog fact
├── generate_audio.py        # Step 2: ElevenLabs creates narration
├── build_video.py           # Step 3: ffmpeg edits video + audio
├── upload_youtube.py        # Step 4: Google OAuth uploads to YouTube
├── utils.py                 # Helpers (logging, file ops)
│
├── .env.example             # Template for API keys
├── .env                     # Your actual API keys (DO NOT commit)
├── client_secrets.json      # Google OAuth (DO NOT commit)
├── token.pickle             # YouTube auth token (DO NOT commit)
│
├── dog_footage/             # Your dog video clips (.mp4/.mov)
├── outputs/                 # Temp files during current run
├── archive/                 # Completed videos (timestamped folders)
├── run_logs/                # Detailed logs for each execution
│
├── requirements.txt         # Python dependencies
├── SETUP.md                 # Detailed setup guide (~15 min)
├── README.md                # This file
└── .git/                    # Version control
```

---

## Logs & Debugging

### Where Logs Live

- **Run logs:** `run_logs/` folder contains detailed logs for each execution
- **Archive:** `archive/` contains completed videos with metadata (timestamped folders)
- **Output temp files:** `outputs/` (cleared at start of each run)

### Typical Log Format

Each run creates a log file: `run_logs/2026-04-24_14-30-15.log`

```
2026-04-24 14:30:15 — 🚀 Canine Wisdom — VIRAL SHORTS Pipeline
2026-04-24 14:30:15 — Validating configuration...
2026-04-24 14:30:16 — ✅ Configuration valid
2026-04-24 14:30:16 — ✅ Outputs directory cleared
2026-04-24 14:30:17 — [Step 1/4] Generating script...
2026-04-24 14:30:22 — ✅ Script generated (145 chars, ~12 sec narration)
2026-04-24 14:30:23 — [Step 2/4] Generating audio...
2026-04-24 14:30:29 — ✅ Audio created: outputs/narration.mp3 (12.3 sec)
2026-04-24 14:30:30 — [Step 3/4] Building video...
2026-04-24 14:31:08 — ✅ Video built: outputs/short.mp4
2026-04-24 14:31:09 — [Step 4/4] Uploading to YouTube...
2026-04-24 14:31:45 — ✅ Video uploaded successfully
2026-04-24 14:31:45 — 🎉 Your Short is LIVE! Go check your channel!
2026-04-24 14:31:45 — 📺 Watch here: https://www.youtube.com/shorts/dQw4w9WgXcQ
```

### Debug: Check a Specific Step

If something fails, look at the log to see which step:

1. **Script generation failed?** → Check `ANTHROPIC_API_KEY` and API credits
2. **Audio creation failed?** → Check `ELEVENLABS_API_KEY` and credits
3. **Video build failed?** → Check `ffmpeg` installation and dog footage format
4. **YouTube upload failed?** → Check `client_secrets.json` and YouTube auth

---

## FAQ

### Q: Can I change the voice?
**A:** Yes! See "How to Change Settings" → Voice. You can use any of 100+ voices from ElevenLabs.

### Q: How long is each Short?
**A:** 45-60 seconds. The pipeline generates a 10-15 second script and fills the rest with dog footage and captions. You can edit the script length in `generate_script.py`.

### Q: What does this cost?
**A:** Depends on your usage:
- **Anthropic** — ~$0.003 per Short (Claude API)
- **ElevenLabs** — ~$0.05 per Short (voice synthesis)
- **YouTube** — Free (you own the channel)
- **Total:** ~$0.053 per Short (less than $2 per month at 1 daily)

### Q: Can I run it daily automatically?
**A:** Yes! See "How to Change Settings" → Schedule Daily Posts (cron or Task Scheduler).

### Q: Do I need my own YouTube channel?
**A:** Yes. Set up a free channel at [youtube.com](https://youtube.com). This pipeline uploads to **your** channel only.

### Q: What if I don't have dog footage?
**A:** Search YouTube for free dog clips (Creative Commons) or record your own. Any dog video works. Minimum 60 seconds recommended, but any length works.

### Q: Can I monetize the Shorts?
**A:** Yes. YouTube Shorts is part of YouTube Partner Program. Once eligible, all ad revenue is yours.

### Q: What if the script is boring?
**A:** Each run generates a new, random fact. Unhappy with one? Just run again. Different script, different video.

### Q: Can I edit the script before upload?
**A:** Not currently (fully automated). To customize: edit `generate_script.py` to modify the prompt Claude receives.

### Q: Is my dog footage uploaded anywhere?
**A:** No. Your dog footage stays on your computer. Only the final YouTube Short is uploaded to YouTube.

---

## Troubleshooting & Support

### Common Errors

| Error | Solution |
|-------|----------|
| `ANTHROPIC_API_KEY is not set` | Check `.env` file exists and API key is correctly pasted |
| `No .mp4 or .mov video clips found` | Add videos to `dog_footage/` folder |
| `ffmpeg not found` | Reinstall ffmpeg (Step 2 in SETUP.md) |
| `YouTube authentication failed` | Delete `token.pickle`, re-run, authorize in browser |
| `Video upload timeout` | Check internet, try again; uploads take 1-2 min |
| `Audio is silent` | Verify ElevenLabs API key and account has credits |

### Get More Help

1. **Check logs:** Look in `run_logs/` for detailed error messages
2. **Read SETUP.md:** Detailed setup steps and troubleshooting
3. **Verify APIs:** Check [console.anthropic.com](https://console.anthropic.com) and [elevenlabs.io](https://elevenlabs.io) to confirm credentials
4. **Test ffmpeg:** Run `ffmpeg -version` to confirm installation

---

## Built With

- **Claude AI** (Anthropic) — Script generation
- **ElevenLabs** — Text-to-speech narration
- **ffmpeg** — Video and audio editing
- **Google APIs** — YouTube upload
- **Python** — Orchestration

---

## License

This project is provided as-is. Use freely for personal or commercial purposes.

---

**Ready to go viral?** Start with [SETUP.md](./SETUP.md), then run `python main.py`. Your first Short publishes in minutes. 🐶🎬

**Questions?** Check the FAQ or troubleshooting section above.
