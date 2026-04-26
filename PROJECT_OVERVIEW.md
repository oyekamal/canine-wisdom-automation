# Canine Wisdom by King — Project Overview

## What Are We Building?

A **fully automated YouTube Shorts production pipeline** that generates viral dog fact videos and publishes them with a single command.

**One command:** `python main.py`  
**Output:** A published YouTube Short (2-4 minutes later)  
**No manual steps required** — completely hands-off automation

---

## The Problem We're Solving

Creating YouTube Shorts is time-consuming:
- ❌ Write scripts manually
- ❌ Record voiceovers
- ❌ Find video footage
- ❌ Edit videos (crop, resize, format)
- ❌ Upload to YouTube
- ❌ Add titles, descriptions, hashtags

**Our solution:** Automate all of it with AI.

---

## How It Works — The 4-Step Pipeline

### Step 1: Generate Viral Script (Claude API)
**Input:** Nothing (AI creates from scratch)  
**Process:**
- Use Claude (Anthropic) to write a compelling 45-second dog fact script
- Ask Claude for a catchy title (under 60 characters)
- Ask Claude for 10 relevant hashtags
- Ensure it starts with a hook and ends with "Follow for daily dog facts!"

**Output:**
- `outputs/script.txt` — The spoken script
- `outputs/metadata.json` — Title, script, hashtags

**Why:** Claude generates fresh, viral-worthy content every time. Each script is unique and engaging.

---

### Step 2: Create Voiceover (ElevenLabs API)
**Input:** Script text from Step 1  
**Process:**
- Send script to ElevenLabs text-to-speech API
- Use "Adam" voice with high-energy settings:
  - Stability: 0.4 (natural speech)
  - Similarity Boost: 0.8 (match voice)
  - Style: 0.6 (expressiveness)
  - Speaker Boost: enabled
- ElevenLabs generates MP3 audio

**Output:**
- `outputs/voiceover.mp3` — High-quality audio file

**Why:** ElevenLabs produces natural-sounding, energetic voiceovers. No robot voice.

---

### Step 3: Build Video (ffmpeg)
**Input:**
- Random dog video clip from `dog_footage/` folder
- Voiceover MP3 from Step 2

**Process:**
1. **Select random dog clip** — Pick one video at random from user's dog_footage folder
2. **Resize & crop** — Fit video to 1080x1920 (vertical shorts format)
3. **Center content** — Add padding if needed to maintain aspect ratio
4. **Enhance visuals** — Boost brightness (+0.02) and saturation (1.3x) for pop
5. **Loop video** — Repeat dog footage to match audio duration
6. **Encode video** — H.264 codec, CRF 20 (high quality), fast preset
7. **Encode audio** — AAC codec, 192k bitrate, 44100 Hz sample rate
8. **Sync audio** — Use `-shortest` flag to cut at end of voiceover

**Output:**
- `outputs/final_video.mp4` — Vertical 1080x1920 YouTube Short

**Why:** ffmpeg is fast, free, and produces YouTube-compatible videos in the exact format needed.

---

### Step 4: Upload to YouTube (YouTube Data API v3)
**Input:**
- Video file from Step 3
- Metadata (title, script, hashtags) from Step 1

**Process:**
1. **Authenticate** — Use Google OAuth2 to authorize with YouTube
   - First run: Opens browser for login
   - Future runs: Uses saved `token.json`
2. **Build description** — Combine script + hashtags + #Shorts + #YouTubeShorts
3. **Upload video** — Use resumable upload (handles large files)
4. **Set metadata** — Title, description, tags, category (Pets & Animals)
5. **Publish** — Set to public, not marked as kids content

**Output:**
- YouTube Short URL (e.g., `https://youtube.com/shorts/VIDEO_ID`)

**Why:** YouTube Data API handles all the upload details. No manual YouTube UI clicks needed.

---

## File-Based State Passing

Each step is **completely independent**. State passes via files on disk:

```
Step 1 generates:     outputs/script.txt
                      outputs/metadata.json
                      ↓
Step 2 reads:         outputs/script.txt
                      generates: outputs/voiceover.mp3
                      ↓
Step 3 reads:         outputs/voiceover.mp3
                      generates: outputs/final_video.mp4
                      ↓
Step 4 reads:         outputs/metadata.json
                      outputs/final_video.mp4
                      uploads to YouTube
```

**Why:** If any step fails, you can fix it and re-run just that step. No need to regenerate everything.

---

## Architecture

### Core Modules

**`config.py`** — Configuration Management
- Loads API keys from `.env` file
- Validates all required settings exist
- Defines API endpoints and constants
- Prevents accidental use of bad configuration

**`utils.py`** — Shared Utilities
- **Logging:** Terminal + file logging with timestamps
- **Retry Logic:** Automatic retry with backoff for transient API failures
- **File Helpers:** Random dog clip selection, archiving, cleanup

**`main.py`** — Orchestrator
- Runs all 4 steps in sequence
- Handles errors gracefully
- Cleans up and archives completed runs
- User's entry point: `python main.py`

**`generate_script.py`** — Step 1
- Calls Claude API with dog fact prompt
- Returns JSON with script, title, hashtags
- Writes to `outputs/script.txt` and `outputs/metadata.json`

**`generate_audio.py`** — Step 2
- Reads script from `outputs/script.txt`
- Calls ElevenLabs API with voice settings
- Writes to `outputs/voiceover.mp3`

**`build_video.py`** — Step 3
- Selects random dog clip from `dog_footage/`
- Runs ffmpeg with specific encoding parameters
- Writes to `outputs/final_video.mp4`

**`upload_youtube.py`** — Step 4
- Handles Google OAuth2 authentication
- Reads metadata and video files
- Uploads to YouTube with resumable upload
- Returns published video URL

---

## Error Handling Strategy

### Retry Logic
All API calls (Claude, ElevenLabs, YouTube) automatically retry **once** with 2-second backoff:
- First attempt fails → Wait 2 seconds → Try again
- Second attempt fails → Give up and show error message

**Why:** Transient network issues are common. One retry handles most cases.

### Error Messages
When something fails, user sees:
1. **What failed** — Which step (Script generation, Audio, Video, Upload)
2. **Why it failed** — Error message from the API or system
3. **What to do** — Suggestion to check logs
4. **Where logs are** — `run_logs/YYYY-MM-DD_HH-MM-SS.log`

Example:
```
❌ Pipeline failed at Step 2 (Audio Generation)
Error: ElevenLabs API returned 401 Unauthorized
Check: ELEVENLABS_API_KEY in .env is correct
Details: See run_logs/2026-04-25_14-32-45.log
```

---

## Logging System

### Terminal Output (Real-Time)
User sees emoji-prefixed messages with timestamps:
```
🚀 Canine Wisdom — VIRAL SHORTS Pipeline
[14:32:45] 📝 Step 1: Writing viral script + title...
[14:32:53] ✅ Viral script generated!
[14:32:54] 🎤 Step 2: Creating energetic voiceover...
[14:33:12] ✅ Energetic voiceover created!
[14:33:13] 🎬 Step 3: Building vertical Shorts video...
[14:33:34] ✅ Vertical Shorts video built!
[14:33:35] 📤 Step 4: Uploading to YouTube Shorts...
[14:33:45] ✅ Short uploaded! 🔗 https://youtube.com/shorts/VIDEO_ID
🎉 Your Short is LIVE! Go check your channel!
```

### File Logs
Detailed logs saved to `run_logs/YYYY-MM-DD_HH-MM-SS.log`:
- Full API requests and responses
- File paths and sizes
- Timing for each step
- Complete error traces
- Perfect for debugging

---

## Data Flow

```
┌─────────────────────┐
│  User runs:         │
│  python main.py     │
└──────────┬──────────┘
           ↓
┌─────────────────────────────────────┐
│ 1. Load config from .env            │
│    - Validate API keys exist        │
│    - Check dog_footage/ has clips   │
└──────────┬──────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ 2. Initialize logger                │
│    - Create run_logs/ timestamp     │
│    - Start logging to file + screen │
└──────────┬──────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ 3. Clear outputs/ from last run     │
└──────────┬──────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ Step 1: Generate Script             │
│ API: Claude (Anthropic)             │
│ Output: script.txt, metadata.json   │
└──────────┬──────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ Step 2: Generate Audio              │
│ API: ElevenLabs TTS                 │
│ Input: script.txt                   │
│ Output: voiceover.mp3               │
└──────────┬──────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ Step 3: Build Video                 │
│ Tool: ffmpeg                        │
│ Input: dog_footage + voiceover.mp3  │
│ Output: final_video.mp4             │
└──────────┬──────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ Step 4: Upload to YouTube           │
│ API: YouTube Data API v3            │
│ Input: metadata.json + video        │
│ Output: YouTube Shorts URL          │
└──────────┬──────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ Archive Run                         │
│ Move outputs/ → archive/TIMESTAMP/  │
│ Move logs → archive/TIMESTAMP/      │
└──────────┬──────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│ Success!                            │
│ Display YouTube URL                 │
│ Ready to run again tomorrow         │
└─────────────────────────────────────┘
```

---

## Directory Structure

```
repos/canine-wisdom-automation/
├── main.py                         # Entry point - run this
├── config.py                       # Configuration
├── utils.py                        # Shared utilities
├── generate_script.py              # Step 1: Script
├── generate_audio.py               # Step 2: Audio
├── build_video.py                  # Step 3: Video
├── upload_youtube.py               # Step 4: Upload
├── test_*.py                       # Test scripts
├── .env                            # Your API keys (gitignored)
├── .env.example                    # Template for .env
├── requirements.txt                # Python dependencies
├── .gitignore                      # Exclude secrets
├── dog_footage/                    # Your dog videos (you add these)
│   ├── dog1.mp4
│   ├── dog2.mov
│   └── ...
├── outputs/                        # Current run artifacts
│   ├── script.txt
│   ├── metadata.json
│   ├── voiceover.mp3
│   └── final_video.mp4
├── archive/                        # Old runs (timestamped)
│   ├── 2026-04-25_14-32-45/
│   │   ├── script.txt
│   │   ├── metadata.json
│   │   ├── voiceover.mp3
│   │   ├── final_video.mp4
│   │   └── 2026-04-25_14-32-45.log
│   └── 2026-04-25_15-10-22/
│       └── ...
└── run_logs/                       # Detailed logs
    ├── 2026-04-25_14-32-45.log
    └── 2026-04-25_15-10-22.log
```

---

## Costs

**Per video:**
- **Claude API:** ~$0.001 (500 tokens)
- **ElevenLabs API:** ~$0.01-0.02 (600-800 characters)
- **ffmpeg:** Free (local processing)
- **YouTube API:** Free (unlimited uploads)

**Total:** ~$0.01-0.03 per video

---

## What Makes This Different

1. **Fully Automated** — No manual editing, scheduling, or intervention needed
2. **AI-Generated Content** — Fresh, unique scripts every time (never repeats)
3. **One Command** — Run `python main.py`, done
4. **Reproducible** — Archive stores every run for future reference
5. **Error Resilient** — Retry logic + detailed logs for debugging
6. **Non-Technical** — Channel owner doesn't need to understand code
7. **Cost-Effective** — ~$0.01 per video (less than $0.30/day)

---

## Next Steps

1. **Setup:** Follow SETUP.md (15 minutes)
2. **Add dog videos:** Copy videos to `dog_footage/` folder
3. **Run:** `python main.py`
4. **Watch:** Video appears on YouTube within 5 minutes
5. **Automate:** Set up daily cron job (optional)

