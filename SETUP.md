# Setup Guide — Canine Wisdom YouTube Shorts Pipeline

This guide takes **~15 minutes**. Follow each step in order. At the end, you'll have everything ready to generate and publish your first viral dog fact Short.

---

## Step 1: Install Python Dependencies

First, make sure you have Python 3.9+ installed. Then, in the project folder, run:

```bash
pip install -r requirements.txt
```

This installs:
- **anthropic** — AI model for script generation
- **requests** — API calls
- **google-auth**, **google-auth-oauthlib**, **google-api-python-client** — YouTube authentication
- **python-dotenv** — Environment variable loading

---

## Step 2: Install ffmpeg

ffmpeg is required to edit video and audio. Choose your OS:

### Mac
```bash
brew install ffmpeg
```

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install ffmpeg
```

### Windows
1. Visit [ffmpeg.org/download.html](https://ffmpeg.org/download.html)
2. Download the **full** version (not just the libraries)
3. Extract to a folder (e.g., `C:\ffmpeg`)
4. Add to your PATH:
   - Right-click **This PC** → **Properties** → **Advanced system settings**
   - Click **Environment Variables** → **New** (under System Variables)
   - Variable name: `Path`; Variable value: `C:\ffmpeg\bin`
   - Click **OK**, then restart your terminal

**Verify ffmpeg is installed:**
```bash
ffmpeg -version
```

---

## Step 3: Create .env File

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Then edit `.env` and add your keys:

```
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
ELEVENLABS_API_KEY=sk_your-actual-key-here
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB
```

### Get Your API Keys

**Anthropic API Key:**
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in
3. Click **API Keys** on the left
4. Click **Create Key**
5. Copy and paste into `.env`

**ElevenLabs API Key & Voice ID:**
1. Go to [elevenlabs.io](https://elevenlabs.io)
2. Sign up or log in
3. Click **Settings** → **API Keys**
4. Copy the API key into `.env`
5. To find Voice IDs, go to **Voices** → click any voice → copy the ID shown
6. Default ID `pNInz6obpgDQGcFmaJgB` (Joshua) is already set

---

## Step 4: Download Google OAuth Credentials

The pipeline needs permission to upload videos to your YouTube channel.

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project (or use existing):
   - Click the dropdown at top → **New Project**
   - Name: "Canine Wisdom" → **Create**
3. Enable YouTube API:
   - Search for **YouTube Data API v3**
   - Click **Enable**
4. Create OAuth 2.0 credentials:
   - Click **Create Credentials** → **OAuth client ID**
   - If prompted, create an OAuth consent screen first (Desktop app, add yourself)
   - Application type: **Desktop application**
   - Click **Create**
   - Click the download icon → **JSON**
5. Move the file to your project folder:
   ```bash
   mv ~/Downloads/client_secrets.json /path/to/canine-wisdom-automation/
   ```

**Important:** Keep `client_secrets.json` safe. Never share it.

---

## Step 5: Add Dog Footage

The pipeline randomly selects clips from your dog videos.

1. Create a `dog_footage/` folder (it should already exist)
2. Add your video files (`.mp4` or `.mov`):
   - Minimum 60 seconds per clip recommended
   - Any length works; pipeline clips to 59-60 seconds
   - Add at least 3-5 clips for variety
3. Example structure:
   ```
   dog_footage/
   ├── dog1.mp4
   ├── dog2.mov
   ├── dog3.mp4
   └── ...
   ```

**Don't have dog videos?** Search YouTube for free dog videos or use your own footage.

---

## Step 6: Run the Pipeline

In the project folder, run:

```bash
python main.py
```

You'll see output like:
```
🚀 Canine Wisdom — VIRAL SHORTS Pipeline
✅ Configuration valid
✅ Outputs directory cleared
[Step 1/4] Generating script...
✅ Script generated: "Dogs have 300 million olfactory receptors..."
[Step 2/4] Generating audio...
✅ Audio created (12 seconds)
[Step 3/4] Building video...
✅ Video built: outputs/short.mp4
[Step 4/4] Uploading to YouTube...
✅ Video uploaded!
🎉 Your Short is LIVE! Go check your channel!
📺 Watch here: https://www.youtube.com/shorts/...
```

The entire pipeline takes **2-5 minutes** depending on your internet speed.

---

## Step 7: Verify Success

1. Go to your YouTube channel: [youtube.com](https://youtube.com) → **My Channel**
2. Your Short should appear within **5 minutes**
3. Check the Short's title, description, and views
4. Done! It's live.

---

## Step 8: Automate Daily Posts (Optional)

Want the pipeline to run automatically every day?

### Mac / Linux (Cron)

1. Open crontab:
   ```bash
   crontab -e
   ```

2. Add this line to run daily at 9:00 AM:
   ```
   0 9 * * * cd /path/to/canine-wisdom-automation && python main.py >> run_logs/cron.log 2>&1
   ```
   Replace `/path/to/` with your actual project path.

3. Save and exit (Ctrl+X, then Y, then Enter if using nano)

4. Verify it's set:
   ```bash
   crontab -l
   ```

### Windows (Task Scheduler)

1. Open **Task Scheduler** (search in Start menu)
2. Click **Create Basic Task** on the right
3. Name: "Canine Wisdom Daily"
4. Trigger: **Daily** at **9:00 AM**
5. Action: **Start a program**
   - Program: `C:\Python312\python.exe` (your Python path)
   - Arguments: `main.py`
   - Start in: `C:\path\to\canine-wisdom-automation`
6. Click **Finish**

---

## Step 9: Troubleshooting

### "ANTHROPIC_API_KEY is not set"
- Check `.env` file exists in the project folder
- Verify you pasted your Anthropic API key correctly
- No spaces or quotes around the key

### "No .mp4 or .mov video clips found"
- Make sure `dog_footage/` folder exists in the project
- Add at least one `.mp4` or `.mov` file to it
- Check file extensions are lowercase

### "client_secrets.json not found"
- Download it from Google Cloud Console (Step 4)
- Save it in the project root folder (same level as `main.py`)

### ffmpeg errors ("ffmpeg not found")
- Run `ffmpeg -version` to check installation
- If not found, reinstall ffmpeg (Step 2)
- On Windows, restart your terminal after adding to PATH

### "YouTube authentication failed"
- Delete `token.pickle` if it exists
- Re-run `python main.py` to trigger fresh login
- A browser window will pop up — sign into your YouTube account
- Authorize the app to upload videos

### "Video upload timeout"
- Check your internet connection
- Try again; uploads can take 1-2 minutes
- Shorter videos upload faster

### "Audio is silent or distorted"
- Verify your ElevenLabs API key is correct in `.env`
- Try a different ElevenLabs voice ID: visit [elevenlabs.io/voices](https://elevenlabs.io/voices)
- Check your account has API credits available

### "Script generation fails"
- Verify Anthropic API key is valid
- Check you have API credits (go to console.anthropic.com)
- Restart and try again

---

## Questions?

- **Stuck?** Check `run_logs/` folder for detailed error messages
- **API issues?** Visit the API provider's dashboard to check account status
- **Video issues?** Verify your dog footage files aren't corrupted (try opening them in VLC)

**Ready to publish viral dog facts?** Run `python main.py` and watch your first Short go live! 🐶
