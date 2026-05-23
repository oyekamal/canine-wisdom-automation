# Client Update Round 2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all 5 client requests: replace placeholder affiliate links, strengthen hook prompts, tighten footage keyword matching, improve caption style + add background music, and make evals non-blocking with a skip-log.

**Architecture:** Changes spread across `youtube_settings.json` (affiliate links), `generate_script.py` (hook prompt), `harness/tools/footage.py` (keyword matching), `caption_engine.py` + `build_video.py` (caption style + music), and `harness/orchestrator.py` (non-blocking evals). Each task is independent.

**Tech Stack:** Python 3, ffmpeg (amix filter for background music), existing pipeline infrastructure, ElevenLabs, Anthropic Claude.

---

## File Map

| File | Change |
|---|---|
| `youtube_settings.json` | Real topic-matched Amazon affiliate links keyed by topic_cluster |
| `upload_youtube.py` | Inject affiliate block based on video topic_cluster |
| `generate_script.py` | Strengthen hook prompt with emotional/urgency examples |
| `harness/tools/footage.py` | Tighten `TOPIC_SEARCH_MAP` + use script topic words as primary Pexels query |
| `caption_engine.py` | Increase font size, switch font, improve ASS style |
| `build_video.py` | Add background music mixing via ffmpeg `amix` |
| `harness/orchestrator.py` | Wrap all evals in try/except, log skipped-eval videos to `harness/data/eval_skips.json` |

---

## Task 1: Topic-matched affiliate links

**Files:**
- Modify: `youtube_settings.json` — store real affiliate links keyed by topic cluster
- Modify: `upload_youtube.py` — pick the right link based on video topic cluster, inject into description

**Client-provided links (use exactly as given):**

| Topic cluster | Product | URL |
|---|---|---|
| dog breeds | Dog DNA Test | https://amzn.to/4d1CdKq |
| dog training | Puzzle Toy (Outward Hound) | https://amzn.to/4d14ulL |
| dog behavior | ThunderShirt | https://amzn.to/4whfoeI |
| dog health | Joint Supplement | https://amzn.to/4wjWweX |
| dog science | Dog DNA Test | https://amzn.to/4d1CdKq |
| dog history | Dog DNA Test | https://amzn.to/4d1CdKq |
| dog fun | Puzzle Toy | https://amzn.to/4d14ulL |
| default | Puzzle Toy | https://amzn.to/4d14ulL |

**Format per client:** after intro blurb, before hashtags:
```
🐾 [Short product recommendation line]
👉 [AFFILIATE LINK]
(Affiliate link — we may earn a small commission at no extra cost to you)
```

- [ ] **Step 1: Replace youtube_settings.json entirely**

```json
{
  "channel_name": "Canine Wisdom",
  "description_template": "🐕 {video_title}\n\n{video_script}\n\n{affiliate_block}\n\n{hashtags}\n\n✨ Subscribe for daily dog facts and tips!",
  "hashtags_in_description": true,
  "playlist_id": null,
  "affiliate_links": {
    "dog breeds": {
      "product": "Want to know your dog's breed mix? This DNA test reveals everything.",
      "url": "https://amzn.to/4d1CdKq"
    },
    "dog training": {
      "product": "Keep your dog mentally sharp with this puzzle toy trainers love.",
      "url": "https://amzn.to/4d14ulL"
    },
    "dog behavior": {
      "product": "Does your dog get anxious? This ThunderShirt calms them fast.",
      "url": "https://amzn.to/4whfoeI"
    },
    "dog health": {
      "product": "Support your dog's joints with this vet-recommended supplement.",
      "url": "https://amzn.to/4wjWweX"
    },
    "dog science": {
      "product": "Curious about your dog's breed? This DNA test reveals it all.",
      "url": "https://amzn.to/4d1CdKq"
    },
    "dog history": {
      "product": "Discover your dog's ancient breed origins with this DNA test.",
      "url": "https://amzn.to/4d1CdKq"
    },
    "dog fun": {
      "product": "Keep your dog busy and happy with this top-rated puzzle toy.",
      "url": "https://amzn.to/4d14ulL"
    },
    "default": {
      "product": "Keep your dog mentally stimulated with this top-rated puzzle toy.",
      "url": "https://amzn.to/4d14ulL"
    }
  }
}
```

- [ ] **Step 2: Update upload_youtube.py to inject topic-matched affiliate block**

Read `upload_youtube.py`. Find the description assembly block (around lines 225–244). Replace it with:

```python
        affiliate_links = yt_settings.get("affiliate_links", {})
        topic_cluster = metadata.get("topic_cluster", "default")
        link_entry = affiliate_links.get(topic_cluster) or affiliate_links.get("default", {})

        if link_entry:
            affiliate_block = (
                f"🐾 {link_entry['product']}\n"
                f"👉 {link_entry['url']}\n"
                f"(Affiliate link — we may earn a small commission at no extra cost to you)"
            )
        else:
            affiliate_block = ""

        description_template = yt_settings.get("description_template", "{video_script}\n\n{hashtags}")
        description = description_template.format(
            video_title=metadata.get("title", ""),
            video_script=script,
            hashtags=hashtags_str,
            affiliate_block=affiliate_block,
        )
```

- [ ] **Step 3: Write unit tests**

Create `tests/test_affiliate_links.py`:

```python
import json
from pathlib import Path


def test_all_topic_clusters_have_real_links():
    settings = json.loads(Path("youtube_settings.json").read_text())
    links = settings["affiliate_links"]
    required = ["dog breeds", "dog training", "dog behavior",
                "dog health", "dog science", "dog history", "dog fun", "default"]
    for cluster in required:
        assert cluster in links, f"Missing cluster: {cluster}"
        assert "url" in links[cluster], f"Missing url for: {cluster}"
        assert "amzn.to" in links[cluster]["url"], f"Not Amazon URL for: {cluster}"
        assert "product" in links[cluster], f"Missing product text for: {cluster}"


def test_no_placeholder_links():
    content = Path("youtube_settings.json").read_text()
    assert "example.com" not in content
    assert "barkbox.com" not in content
    assert "[AFFILIATE_LINK" not in content
```

- [ ] **Step 4: Run tests**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
source venv/bin/activate
python -m pytest tests/test_affiliate_links.py -v
```
Expected: 2 tests PASS.

- [ ] **Step 5: Verify import**

```bash
python -c "import upload_youtube; print('OK')"
```
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add youtube_settings.json upload_youtube.py tests/test_affiliate_links.py
git commit -m "feat: topic-matched Amazon affiliate links in video descriptions"
```

---

## Task 2: Strengthen hook prompt

**Files:**
- Modify: `generate_script.py` — update the hook instruction inside the prompt

- [ ] **Step 1: Read generate_script.py lines 88–120** to see the current prompt hook section.

- [ ] **Step 2: Update hook rule #1 in the prompt**

Find this block inside the `prompt = f"""..."""`:
```python
1. FIRST SENTENCE = HOOK. Make it a bold, specific claim or question that dog owners can't ignore.
   Examples of good hooks: "STOP doing this when your dog jumps on you.", "Most owners get this completely wrong.", "Did you know a dog's nose print is as unique as a fingerprint?"
```

Replace with:
```python
1. FIRST SENTENCE = HOOK. It must stop the scroll in under 1.5 seconds. Use urgency, fear, or curiosity directed personally at the dog owner.
   REQUIRED hook styles (pick one):
   - Accusation/secret: "YOUR DOG IS HIDING THIS FROM YOU." / "VET WON'T TELL YOU THIS."
   - Challenge: "MOST OWNERS GET THIS COMPLETELY WRONG." / "YOU'VE BEEN DOING THIS WRONG YOUR WHOLE LIFE."
   - Surprising fact with personal stakes: "Your dog's [X] is 40% [worse/better] than you think — and it's your fault."
   NEVER start with: "Did you know", "Have you ever", or any gentle question. Always personal and direct.
```

- [ ] **Step 3: Update hook_overlay rule #6 in the prompt**

Find:
```python
6. Suggest one bold TEXT OVERLAY phrase (3–6 words, all caps) that should appear on screen in the first 2 seconds. Example: "STOP DOING THIS", "MOST OWNERS GET THIS WRONG".
```

Replace with:
```python
6. Suggest one TEXT OVERLAY phrase (3–6 words, ALL CAPS) for the first 1.5 seconds. Must be emotionally charged and owner-directed. Examples: "YOUR DOG IS HIDING THIS", "VET WON'T TELL YOU THIS", "STOP DOING THIS NOW", "YOU'RE HURTING YOUR DOG". Never vague or generic.
```

- [ ] **Step 4: Write a quick smoke test**

```bash
source venv/bin/activate
python -c "
import generate_script
import inspect
src = inspect.getsource(generate_script)
assert 'VET WON' in src or 'HIDING THIS' in src, 'Hook prompt not updated'
assert 'NEVER start with' in src, 'Gentle question ban not present'
print('Hook prompt OK')
"
```
Expected: `Hook prompt OK`

- [ ] **Step 5: Commit**

```bash
git add generate_script.py
git commit -m "feat: strengthen hook prompt with urgency/accusation styles, ban gentle openers"
```

---

## Task 3: Tighten footage keyword matching

**Files:**
- Modify: `harness/tools/footage.py` — expand `TOPIC_SEARCH_MAP` with specific visual queries per topic

The current map has generic cluster-level queries. We need topic-word-level specificity.

- [ ] **Step 1: Replace TOPIC_SEARCH_MAP in footage.py**

Find the `TOPIC_SEARCH_MAP` dict (lines ~22–30) and replace with:

```python
TOPIC_SEARCH_MAP = {
    "dog health": [
        "dog veterinarian examination",
        "dog vaccination needle",
        "dog health check",
        "dog nose sniffing close up",
        "sick dog owner comfort",
    ],
    "dog behavior": [
        "dog wagging tail excited",
        "dog growling aggressive",
        "dog jumping owner",
        "dog separation anxiety",
        "dog body language",
    ],
    "dog breeds": [
        "golden retriever portrait",
        "labrador puppy close up",
        "husky blue eyes",
        "german shepherd alert",
        "border collie running",
    ],
    "dog training": [
        "dog training sit command",
        "dog agility course",
        "puppy obedience lesson",
        "dog trainer reward treat",
        "dog learning trick",
    ],
    "dog history": [
        "wolf running wild",
        "dog human bond ancient",
        "dog loyalty owner",
        "dog companion walking",
        "dog working farm",
    ],
    "dog science": [
        "dog nose sniffing close up",
        "dog brain scan",
        "dog dna test swab",
        "dog senses research",
        "dog eye close up",
    ],
    "dog fun": [
        "puppy playing ball",
        "dog running beach",
        "dog excited jumping",
        "cute puppy face",
        "dog funny reaction",
    ],
}
```

- [ ] **Step 2: Update `fetch_footage_for_topic` to use the full topic string as primary query**

In `fetch_footage_for_topic`, find:
```python
    topic_words = topic.replace("_", " ").split()[:3]
    queries.insert(0, "dog " + " ".join(topic_words))
    random.shuffle(queries[1:])  # randomise after the topic-specific one
```

Replace with:
```python
    # Primary query: use full topic string (e.g. "dog dna testing", "jumping behavior fix")
    primary = "dog " + topic.replace("_", " ").strip()
    # Secondary: topic-cluster queries, randomised
    cluster_queries = TOPIC_SEARCH_MAP.get(topic_cluster, DEFAULT_QUERIES).copy()
    random.shuffle(cluster_queries)
    queries = [primary] + cluster_queries
```

- [ ] **Step 3: Write a unit test**

Create `tests/test_footage_queries.py`:

```python
from harness.tools.footage import TOPIC_SEARCH_MAP, DEFAULT_QUERIES


def test_all_clusters_have_specific_queries():
    clusters = ["dog health", "dog behavior", "dog breeds", "dog training",
                "dog history", "dog science", "dog fun"]
    for cluster in clusters:
        assert cluster in TOPIC_SEARCH_MAP, f"Missing cluster: {cluster}"
        assert len(TOPIC_SEARCH_MAP[cluster]) >= 3, f"Too few queries for {cluster}"


def test_queries_are_specific_not_generic():
    # No query should be just "dog" — all must have at least 2 words
    for cluster, queries in TOPIC_SEARCH_MAP.items():
        for q in queries:
            assert len(q.split()) >= 2, f"Too generic query '{q}' in {cluster}"
```

- [ ] **Step 4: Run tests**

```bash
source venv/bin/activate
python -m pytest tests/test_footage_queries.py -v
```
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add harness/tools/footage.py tests/test_footage_queries.py
git commit -m "feat: tighten footage keyword matching with topic-specific Pexels queries"
```

---

## Task 4: Improve caption style (bolder + cleaner font)

**Files:**
- Modify: `caption_engine.py` — update `CaptionStyle` defaults and ASS style line
- Modify: `build_video.py` — update `CaptionStyle` instantiation to match

- [ ] **Step 1: Update CaptionStyle defaults in caption_engine.py**

Find the `CaptionStyle` dataclass and replace the defaults:

```python
@dataclass
class CaptionStyle:
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_color: str = "white"          # white pops on any background
    stroke_color: str = "black"
    stroke_width: int = 6              # thicker stroke = cleaner on busy footage
    font_size: int = 88                # larger = more readable on phone
    x_expr: str = "(w-text_w)/2"
    y_expr: str = "(h*0.72)"
    shadow_x: int = 4
    shadow_y: int = 4
```

- [ ] **Step 2: Update ASS style in write_word_ass()**

In the ASS header, find the `Style: Word,...` line inside the `header = f"""..."""` block:

```python
Style: Word,Arial,{style.font_size},{font_color_ass},&H000000FF,{stroke_color_ass},&H00000000,-1,0,0,0,100,100,0,0,1,{style.stroke_width},{style.shadow_x},2,10,10,{bottom_margin},1
```

Replace `Arial` with `Arial Black` for a bolder built-in font that renders on all Linux systems:

```python
Style: Word,Arial Black,{style.font_size},{font_color_ass},&H000000FF,{stroke_color_ass},&H00000000,-1,0,0,0,100,100,0,0,1,{style.stroke_width},{style.shadow_x},2,10,10,{bottom_margin},1
Style: Hook,Arial Black,100,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,5,8,10,10,{hook_top_margin},1
```

(The Hook style also bumps to font size 100 and stroke 6.)

- [ ] **Step 3: Update build_video.py CaptionStyle instantiation**

In `build_video.py`, find:
```python
        style = CaptionStyle(font_size=68, font_color="yellow", stroke_width=4)
```

Replace with:
```python
        style = CaptionStyle(font_size=88, font_color="white", stroke_width=6)
```

- [ ] **Step 4: Run caption engine tests**

```bash
source venv/bin/activate
python -m pytest tests/test_caption_engine.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add caption_engine.py build_video.py
git commit -m "feat: bolder caption style — white text, size 88, stroke 6, Arial Black"
```

---

## Task 5: Add background music

**Files:**
- Modify: `build_video.py` — mix a music track into the final ffmpeg encode
- Add: `assets/music/` directory with one royalty-free background music file

Background music file must be royalty-free. We'll use a local MP3 placed at `assets/music/background.mp3`. The ffmpeg `amix` filter blends it under the voiceover at low volume (music at ~15% of voiceover volume).

- [ ] **Step 1: Create assets/music/ directory and add a placeholder README**

```bash
mkdir -p /home/oye/Documents/free_work/repos/canine-wisdom-automation/assets/music
echo "Place royalty-free background music MP3 here named 'background.mp3'" > /home/oye/Documents/free_work/repos/canine-wisdom-automation/assets/music/README.txt
```

- [ ] **Step 2: Add music mixing to build_video.py**

In `build_video.py`, add a constant near the top of the file (after other imports):
```python
MUSIC_PATH = Path(__file__).parent / "assets" / "music" / "background.mp3"
MUSIC_VOLUME = 0.12  # music at 12% relative to voiceover
```

In `build_video()`, find the `cmd = [...]` ffmpeg command. Replace it with a version that conditionally mixes music if `MUSIC_PATH` exists:

```python
    if MUSIC_PATH.exists():
        # Mix voiceover + background music: loop music, duck to MUSIC_VOLUME
        cmd = [
            "ffmpeg",
            "-i", actual_video_path,
            "-i", str(voiceover_path),
            "-stream_loop", "-1", "-i", str(MUSIC_PATH),
            "-c:v", enc_params["codec"],
            "-crf", enc_params["crf"],
            "-preset", enc_params["preset"],
            "-vf", video_filter,
            "-filter_complex",
            f"[1:a]volume=1.0[voice];[2:a]volume={MUSIC_VOLUME}[music];[voice][music]amix=inputs=2:duration=first[aout]",
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:a", "aac",
            "-b:a", AUDIO_BITRATE,
            "-ar", str(AUDIO_SAMPLE_RATE),
            "-t", str(audio_duration),
            "-y",
            "outputs/final_video.mp4"
        ]
        log(f"🎵 Mixing background music at {int(MUSIC_VOLUME*100)}% volume")
    else:
        cmd = [
            "ffmpeg",
            "-i", actual_video_path,
            "-i", str(voiceover_path),
            "-c:v", enc_params["codec"],
            "-crf", enc_params["crf"],
            "-preset", enc_params["preset"],
            "-vf", video_filter,
            "-c:a", "aac",
            "-b:a", AUDIO_BITRATE,
            "-ar", str(AUDIO_SAMPLE_RATE),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-t", str(audio_duration),
            "-y",
            "outputs/final_video.mp4"
        ]
```

- [ ] **Step 3: Verify import check**

```bash
source venv/bin/activate
python -c "from build_video import build_video, MUSIC_PATH, MUSIC_VOLUME; print('OK'); print('Music path:', MUSIC_PATH); print('Music exists:', MUSIC_PATH.exists())"
```
Expected: `OK`, path printed, `Music exists: False` (until client adds the MP3).

- [ ] **Step 4: Commit**

```bash
git add build_video.py assets/music/README.txt
git commit -m "feat: add background music mixing via ffmpeg amix, skips gracefully if file absent"
```

> **NOTE FOR CLIENT:** Place a royalty-free background music MP3 at `assets/music/background.mp3`. Until then the pipeline runs without music. Good free sources: FreeMusicArchive.org, Pixabay Music, YouTube Audio Library.

---

## Task 6: Make evals non-blocking with skip log

**Files:**
- Modify: `harness/orchestrator.py` — wrap all blocking evals in try/except, write skip log

Currently `hook_eval`, `script_eval`, `title_eval` are hard gates that stop the pipeline if they fail or error. The client wants publishing to continue even when evals error, with a log file for manual review.

- [ ] **Step 1: Add _log_eval_skip() helper to orchestrator.py**

After the `_write_incident()` function, add:

```python
def _log_eval_skip(run_id: str, skipped_evals: list, video_url: str) -> None:
    """Append to harness/data/eval_skips.json so client can review manually."""
    skip_log = DATA_DIR / "eval_skips.json"
    existing = []
    if skip_log.exists():
        try:
            existing = json.loads(skip_log.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    existing.append({
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "video_url": video_url,
        "skipped_evals": skipped_evals,
        "review_status": "pending",
    })
    atomic_write(skip_log, existing)
    log(f"📋 Eval skip logged for manual review: {skip_log}")
```

- [ ] **Step 2: Add `import json` if not already present in orchestrator.py**

Check top of file — if `import json` is missing, add it with the other imports.

- [ ] **Step 3: Replace the blocking eval loop with non-blocking version**

Find the `for attempt in range(MAX_LLM_RETRIES):` block and replace the entire block (including hook, script, title evals) with:

```python
        skipped_evals = []
        hook_result = script_result = title_result = None

        for attempt in range(MAX_LLM_RETRIES):
            try:
                metadata = generate_script()
            except Exception as e:
                log(f"⚠️  Script generation failed (attempt {attempt+1}): {e}", level="warning")
                if attempt == MAX_LLM_RETRIES - 1:
                    raise
                continue

            script_text = metadata["script"]
            title = metadata["title"]
            hook_sentence = script_text.split(".")[0] + "."

            # Hook eval — non-blocking on API error
            try:
                hook_result = retry_with_backoff(lambda: hook_eval(hook_sentence), max_retries=2, initial_backoff=5, step_name="hook_eval")
                save_eval_result(hook_result, run_id)
                if not hook_result.passed:
                    log(f"⚠️  hook_eval score {hook_result.score:.1f} (attempt {attempt+1}): {hook_result.reasoning}")
                    if attempt < MAX_LLM_RETRIES - 1:
                        continue
                    log("⚠️  hook_eval below threshold after max retries — publishing anyway")
                    skipped_evals.append({"eval": "hook_eval", "reason": f"score {hook_result.score:.1f} below threshold", "score": hook_result.score})
            except Exception as e:
                log(f"⚠️  hook_eval errored (API issue) — skipping: {e}", level="warning")
                skipped_evals.append({"eval": "hook_eval", "reason": str(e)})

            # Script eval — non-blocking on API error
            try:
                script_result = retry_with_backoff(lambda: script_eval(script_text, recent_topics=[]), max_retries=2, initial_backoff=5, step_name="script_eval")
                save_eval_result(script_result, run_id)
                if not script_result.passed:
                    log(f"⚠️  script_eval score {script_result.score:.1f} (attempt {attempt+1}): {script_result.reasoning}")
                    if attempt < MAX_LLM_RETRIES - 1:
                        continue
                    log("⚠️  script_eval below threshold after max retries — publishing anyway")
                    skipped_evals.append({"eval": "script_eval", "reason": f"score {script_result.score:.1f} below threshold", "score": script_result.score})
            except Exception as e:
                log(f"⚠️  script_eval errored (API issue) — skipping: {e}", level="warning")
                skipped_evals.append({"eval": "script_eval", "reason": str(e)})

            # Title eval — non-blocking on API error
            try:
                title_result = retry_with_backoff(lambda: title_eval(title), max_retries=2, initial_backoff=5, step_name="title_eval")
                save_eval_result(title_result, run_id)
                if not title_result.passed:
                    log(f"⚠️  title_eval score {title_result.score:.1f} (attempt {attempt+1}): {title_result.reasoning}")
                    if attempt < MAX_LLM_RETRIES - 1:
                        continue
                    log("⚠️  title_eval below threshold after max retries — publishing anyway")
                    skipped_evals.append({"eval": "title_eval", "reason": f"score {title_result.score:.1f} below threshold", "score": title_result.score})
            except Exception as e:
                log(f"⚠️  title_eval errored (API issue) — skipping: {e}", level="warning")
                skipped_evals.append({"eval": "title_eval", "reason": str(e)})

            break
```

- [ ] **Step 4: Add skip log call after upload**

After `log(f"🎉 Short is LIVE: {video_url}")`, add:

```python
        if skipped_evals:
            _log_eval_skip(run_id, skipped_evals, video_url)
```

- [ ] **Step 5: Fix post-upload eval score references**

The `track_video` call references `hook_result.score` etc. Guard against None:

Find:
```python
                "eval_scores": {
                    "hook_eval": hook_result.score,
                    "script_eval": script_result.score,
                    "title_eval": title_result.score,
                },
```

Replace with:
```python
                "eval_scores": {
                    "hook_eval": hook_result.score if hook_result else None,
                    "script_eval": script_result.score if script_result else None,
                    "title_eval": title_result.score if title_result else None,
                },
```

- [ ] **Step 6: Verify import check**

```bash
source venv/bin/activate
python -c "from harness.orchestrator import run_pipeline; print('OK')"
```
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add harness/orchestrator.py
git commit -m "feat: make all evals non-blocking, log skipped evals to harness/data/eval_skips.json"
```

---

## Task 7: Run orchestrator end-to-end and verify

- [ ] **Step 1: Run full test suite**

```bash
source venv/bin/activate
python -m pytest tests/ -v --tb=short
```
All tests should PASS.

- [ ] **Step 2: Run the orchestrator**

```bash
python -m harness.orchestrator 2>&1
```

Expected: pipeline completes to upload even if eval API is slow. If evals error, `harness/data/eval_skips.json` is written.

- [ ] **Step 3: Verify eval_skips.json if evals were skipped**

```bash
python -c "
from harness.storage import atomic_read
from pathlib import Path
p = Path('harness/data/eval_skips.json')
if p.exists():
    import json
    skips = json.loads(p.read_text())
    for s in skips[-3:]:
        print(s)
else:
    print('No skips logged (evals all passed)')
"
```

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: verify round 2 client updates end-to-end"
```

---

## Self-Review

| Client request | Task |
|---|---|
| Topic-matched Amazon affiliate links (real URLs) | Task 1 |
| Affiliate block injected into description per topic_cluster | Task 1 |
| Stronger hook prompt (urgency/accusation) | Task 2 |
| Tighter footage keyword matching to topic | Task 3 |
| No still images / more specific queries | Task 3 (video-only Pexels filter already in place) |
| Bolder cleaner caption font | Task 4 |
| Background music | Task 5 |
| Evals non-blocking on error | Task 6 |
| Log skipped-eval videos for manual review | Task 6 |

**Placeholder scan:** Task 1 intentionally uses `[AFFILIATE_LINK_*]` as client-instruction markers — these are the deliverable, not placeholders in our plan. All other steps have complete code. ✅

**Type consistency:** `skipped_evals` list used in Task 6 is initialised before the loop and passed to `_log_eval_skip()` which expects `list`. `hook_result`, `script_result`, `title_result` initialised to `None`, guarded before `.score` access. ✅
