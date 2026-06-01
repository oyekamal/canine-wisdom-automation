# Horror Channel Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new channel `channels/horror-narration/` that harvests Reddit horror stories, scores and ranks them, rewrites them via Claude into original narration scripts, and runs the full existing video pipeline to produce and upload horror/paranormal Shorts and long-form videos.

**Architecture:** This plan requires Plan A (multi-channel infrastructure) to be complete first. The horror channel is a new directory under `channels/horror-narration/` with its own settings, prompt, and data. New modules (`reddit_harvest.py`, `story_scorer.py`, `story_rewriter.py`) live in `channels/horror-narration/harness/` and are orchestrated by a channel-specific orchestrator that calls the shared video/audio/upload pipeline. The shared pipeline (build_video, generate_audio, upload_youtube) is completely unchanged.

**Tech Stack:** Python 3, PRAW (Reddit API), Anthropic Claude API, existing ElevenLabs/FFmpeg/YouTube pipeline, pytest

**Prerequisites:** Plan A (2026-05-28-multi-channel-infrastructure.md) must be fully implemented before starting this plan.

---

## What this plan does NOT touch

- `build_video.py` — unchanged
- `generate_audio.py` — unchanged  
- `upload_youtube.py` — unchanged (just called with horror channel_config)
- `harness/evals/` — unchanged
- `harness/orchestrator.py` — horror channel gets its own orchestrator

## File Map

| File | Action | What it does |
|---|---|---|
| `channels/horror-narration/settings.json` | Create | Channel config: voice ID, category, description template, niche |
| `channels/horror-narration/prompt.txt` | Create | Claude rewrite prompt for horror narration |
| `channels/horror-narration/harness/__init__.py` | Create | Package marker |
| `channels/horror-narration/harness/reddit_harvest.py` | Create | Fetch top stories from configured subreddits via PRAW |
| `channels/horror-narration/harness/story_scorer.py` | Create | Score + rank stories by length fit, hook strength, novelty |
| `channels/horror-narration/harness/story_rewriter.py` | Create | Send story to Claude, get back script + title + description |
| `channels/horror-narration/harness/orchestrator.py` | Create | Entry point: harvest → score → rewrite → audio → video → upload |
| `channels/horror-narration/tests/test_reddit_harvest.py` | Create | Tests for harvest module |
| `channels/horror-narration/tests/test_story_scorer.py` | Create | Tests for scorer |
| `channels/horror-narration/tests/test_story_rewriter.py` | Create | Tests for rewriter |

---

### Task 1: Create `channels/horror-narration/settings.json` and `prompt.txt`

**Files:**
- Create: `channels/horror-narration/settings.json`
- Create: `channels/horror-narration/prompt.txt`
- Create: `channels/horror-narration/data/` (directory)
- Create: `channels/horror-narration/harness/__init__.py`
- Create: `channels/horror-narration/tests/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p channels/horror-narration/data
mkdir -p channels/horror-narration/harness
mkdir -p channels/horror-narration/tests
touch channels/horror-narration/harness/__init__.py
touch channels/horror-narration/tests/__init__.py
```

- [ ] **Step 2: Create `channels/horror-narration/settings.json`**

```json
{
  "channel_name": "Darkened Hours",
  "niche": "horror and paranormal narration channel that adapts Reddit horror stories into original narrations",
  "voice_id": "ErXwobaYiN019PkySvjV",
  "youtube_category_id": "24",
  "topic_clusters": [
    "nosleep",
    "paranormal",
    "true scary",
    "creepy encounters",
    "short horror",
    "unsolved mysteries",
    "night shift stories"
  ],
  "description_template": "🌑 {video_title}\n\n{video_script}\n\nStories are dramatized and rewritten from posts on Reddit with original narration and commentary. Original sources linked above. Stock footage used for atmosphere is not from the events described.\n\n{hashtags}\n\n🔔 Subscribe for new horror narrations every week.",
  "affiliate_links": {
    "nosleep": {
      "product": "Can't sleep after this? These noise-cancelling headphones help.",
      "url": "https://amzn.to/placeholder-nosleep"
    },
    "default": {
      "product": "Listen in the dark with these top-rated wireless earbuds.",
      "url": "https://amzn.to/placeholder-default"
    }
  },
  "subreddits": {
    "primary": ["nosleep", "shortscarystories", "TwoSentenceHorror"],
    "secondary": ["LetsNotMeet", "Paranormal"]
  },
  "min_upvotes": 500,
  "min_comments": 50,
  "short_word_range": [40, 120],
  "longform_word_range": [600, 1800],
  "opt_out_authors": []
}
```

**Note:** Replace `placeholder-nosleep` and `placeholder-default` URLs with real Amazon affiliate links when the client provides them.

- [ ] **Step 3: Create `channels/horror-narration/prompt.txt`**

Write this exact content:

```
You are a horror narration scriptwriter for a YouTube channel called "Darkened Hours". You adapt Reddit horror stories into original, polished narration scripts with a distinctive voice: calm and measured, building dread slowly, never rushing. You are NOT copying the story — you are rewriting it as original commentary and dramatization.

You will receive a raw Reddit story. Produce a JSON response with these exact fields:

{
  "script": "The full narration script. Rewrite the story in third-person past tense. Add an original opening hook (first 2 sentences must create immediate dread or curiosity). Weave in 2-3 short original commentary asides in parentheses where the narrator reflects. Never copy more than 10 consecutive words from the source. Word count: 60-90 for Shorts, 800-1400 for long-form.",
  "title": "Video title under 60 characters. Use curiosity gap. No clickbait lies. Examples: 'She heard breathing from inside the wall' or 'The gas station at mile 47 had no employees'",
  "hook_overlay": "3-6 word all-caps text for the first frame overlay. Must be a question or threat. Example: 'WHAT WAS IN THE BASEMENT'",
  "hashtags": ["horror", "scarystories", "nosleep", "paranormal", "truehorror"],
  "topic_cluster": "one of: nosleep, paranormal, true scary, creepy encounters, short horror, unsolved mysteries, night shift stories",
  "source_attribution": "Inspired by a story posted by u/[author] on r/[subreddit]. Original: [url]",
  "format": "short or long"
}

Rules:
- The script must be TRANSFORMATIVE — rewritten, not narrated verbatim.
- The opening hook must not be in the source story.
- No real full names of living private individuals.
- No content involving minors in any sexual or romantic context.
- If the story involves self-harm or suicide, decline and return {"error": "policy"}.
- Always include the source_attribution field.
```

- [ ] **Step 4: Verify settings load via ChannelConfig**

```
source venv/bin/activate && python3 -c "
from channel_config import load_channel_config
cfg = load_channel_config('horror-narration')
print('channel_name:', cfg.channel_name)
print('voice_id:', cfg.voice_id)
print('niche:', cfg.niche[:50])
print('topic_clusters:', cfg.topic_clusters)
print('✅ horror-narration config loads OK')
"
```

Expected: all values printed, no errors.

- [ ] **Step 5: Commit**

```bash
git add channels/horror-narration/
git commit -m "feat: channels/horror-narration — settings, prompt, directory structure"
```

---

### Task 2: Reddit Harvest module

**Files:**
- Create: `channels/horror-narration/harness/reddit_harvest.py`
- Create: `channels/horror-narration/tests/test_reddit_harvest.py`

**Prerequisite:** Register a Reddit script app at https://www.reddit.com/prefs/apps and add to `.env`:
```
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=horror_harness/1.0 by u/your_username
```

Install PRAW:
```bash
source venv/bin/activate && pip install praw && pip freeze | grep praw >> requirements.txt
```

- [ ] **Step 1: Write the failing tests**

Create `channels/horror-narration/tests/test_reddit_harvest.py`:

```python
import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


def test_harvest_returns_list_of_story_dicts():
    """harvest_subreddit returns a list of dicts with required keys."""
    from channels.horror_narration.harness.reddit_harvest import harvest_subreddit

    mock_post = MagicMock()
    mock_post.id = "abc123"
    mock_post.title = "I found something in the woods"
    mock_post.selftext = "It was dark. " * 100
    mock_post.author.name = "test_author"
    mock_post.score = 1500
    mock_post.num_comments = 120
    mock_post.permalink = "/r/nosleep/comments/abc123/i_found_something"
    mock_post.url = "https://www.reddit.com/r/nosleep/comments/abc123/"

    with patch("praw.Reddit") as mock_reddit:
        mock_reddit.return_value.subreddit.return_value.top.return_value = [mock_post]
        stories = harvest_subreddit("nosleep", limit=1, min_upvotes=100, min_comments=10)

    assert len(stories) == 1
    story = stories[0]
    assert story["id"] == "abc123"
    assert story["title"] == "I found something in the woods"
    assert story["author"] == "test_author"
    assert story["subreddit"] == "nosleep"
    assert story["score"] == 1500
    assert story["word_count"] > 0
    assert "permalink" in story
    assert "text" in story


def test_harvest_skips_deleted_authors():
    """Stories from deleted authors are excluded."""
    from channels.horror_narration.harness.reddit_harvest import harvest_subreddit

    mock_post = MagicMock()
    mock_post.id = "del1"
    mock_post.author = None  # deleted
    mock_post.score = 2000
    mock_post.num_comments = 200
    mock_post.selftext = "Long story " * 100

    with patch("praw.Reddit") as mock_reddit:
        mock_reddit.return_value.subreddit.return_value.top.return_value = [mock_post]
        stories = harvest_subreddit("nosleep", limit=1, min_upvotes=100, min_comments=10)

    assert stories == []


def test_harvest_skips_below_min_upvotes():
    """Stories with fewer upvotes than min_upvotes are excluded."""
    from channels.horror_narration.harness.reddit_harvest import harvest_subreddit

    mock_post = MagicMock()
    mock_post.id = "low1"
    mock_post.author.name = "someone"
    mock_post.score = 50
    mock_post.num_comments = 200
    mock_post.selftext = "Story text " * 100

    with patch("praw.Reddit") as mock_reddit:
        mock_reddit.return_value.subreddit.return_value.top.return_value = [mock_post]
        stories = harvest_subreddit("nosleep", limit=1, min_upvotes=500, min_comments=10)

    assert stories == []


def test_harvest_skips_opted_out_authors():
    """Authors in opt_out list are excluded."""
    from channels.horror_narration.harness.reddit_harvest import harvest_subreddit

    mock_post = MagicMock()
    mock_post.id = "opt1"
    mock_post.author.name = "opted_out_user"
    mock_post.score = 2000
    mock_post.num_comments = 200
    mock_post.selftext = "Story " * 100

    with patch("praw.Reddit") as mock_reddit:
        mock_reddit.return_value.subreddit.return_value.top.return_value = [mock_post]
        stories = harvest_subreddit(
            "nosleep", limit=1, min_upvotes=100, min_comments=10,
            opt_out_authors=["opted_out_user"]
        )

    assert stories == []
```

- [ ] **Step 2: Run to confirm tests fail**

```
python3 -m pytest channels/horror-narration/tests/test_reddit_harvest.py -v 2>&1 | tail -10
```

Expected: ImportError or ModuleNotFoundError.

- [ ] **Step 3: Create `channels/horror-narration/harness/reddit_harvest.py`**

```python
"""
Harvest horror stories from Reddit using PRAW.
Filters by upvotes, comment count, author validity, and opt-out list.
"""
import os
import praw
from pathlib import Path


def _get_reddit_client() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ.get("REDDIT_USER_AGENT", "horror_harness/1.0"),
        read_only=True,
    )


def harvest_subreddit(
    subreddit_name: str,
    limit: int = 50,
    time_filter: str = "week",
    min_upvotes: int = 500,
    min_comments: int = 50,
    opt_out_authors: list = None,
) -> list:
    """
    Fetch top posts from a subreddit and return filtered story dicts.

    Args:
        subreddit_name: e.g. "nosleep"
        limit: max posts to fetch from Reddit API
        time_filter: "week", "month", "year", "all"
        min_upvotes: minimum post score to include
        min_comments: minimum comment count to include
        opt_out_authors: list of usernames to always skip

    Returns:
        List of story dicts with keys:
            id, title, text, author, subreddit, score, num_comments,
            permalink, url, word_count
    """
    if opt_out_authors is None:
        opt_out_authors = []

    reddit = _get_reddit_client()
    sub = reddit.subreddit(subreddit_name)
    stories = []

    for post in sub.top(time_filter=time_filter, limit=limit):
        if post.author is None:
            continue
        if post.author.name in opt_out_authors:
            continue
        if post.score < min_upvotes:
            continue
        if post.num_comments < min_comments:
            continue
        text = post.selftext.strip()
        if not text or text in ("[deleted]", "[removed]"):
            continue

        stories.append({
            "id": post.id,
            "title": post.title,
            "text": text,
            "author": post.author.name,
            "subreddit": subreddit_name,
            "score": post.score,
            "num_comments": post.num_comments,
            "permalink": post.permalink,
            "url": f"https://www.reddit.com{post.permalink}",
            "word_count": len(text.split()),
        })

    return stories


def harvest_channel(channel_config) -> list:
    """
    Harvest stories for all subreddits configured in the channel settings.

    Reads subreddits, min_upvotes, min_comments, opt_out_authors from
    channel_config's raw settings (loaded from settings.json).

    Returns combined list of story dicts, deduplicated by post id.
    """
    import json
    settings = json.loads((channel_config.channel_dir / "settings.json").read_text())
    subreddits = (
        settings.get("subreddits", {}).get("primary", []) +
        settings.get("subreddits", {}).get("secondary", [])
    )
    min_upvotes = settings.get("min_upvotes", 500)
    min_comments = settings.get("min_comments", 50)
    opt_out = settings.get("opt_out_authors", [])

    seen_ids = set()
    all_stories = []
    for sub in subreddits:
        for story in harvest_subreddit(sub, min_upvotes=min_upvotes,
                                        min_comments=min_comments,
                                        opt_out_authors=opt_out):
            if story["id"] not in seen_ids:
                seen_ids.add(story["id"])
                all_stories.append(story)
    return all_stories
```

- [ ] **Step 4: Run tests**

```
python3 -m pytest channels/horror-narration/tests/test_reddit_harvest.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add channels/horror-narration/harness/reddit_harvest.py channels/horror-narration/tests/test_reddit_harvest.py
git commit -m "feat: reddit_harvest — fetch and filter horror stories from Reddit via PRAW"
```

---

### Task 3: Story scorer

**Files:**
- Create: `channels/horror-narration/harness/story_scorer.py`
- Create: `channels/horror-narration/tests/test_story_scorer.py`

Score each harvested story 0–10 on: length fit, hook strength, upvote signal. Pick the best story for this run.

- [ ] **Step 1: Write the failing tests**

Create `channels/horror-narration/tests/test_story_scorer.py`:

```python
from channels.horror_narration.harness.story_scorer import score_story, pick_best_story


def _make_story(**kwargs):
    base = {
        "id": "x1", "title": "The darkness came", "text": "word " * 100,
        "author": "author1", "subreddit": "nosleep", "score": 1000,
        "num_comments": 100, "permalink": "/r/nosleep/x1",
        "url": "https://reddit.com/r/nosleep/x1", "word_count": 100,
    }
    base.update(kwargs)
    return base


def test_score_story_returns_float_between_0_and_10():
    story = _make_story(word_count=80, title="What was hiding behind my door", score=2000)
    result = score_story(story, target="short", used_ids=set())
    assert 0.0 <= result <= 10.0


def test_short_target_prefers_short_word_count():
    short_story = _make_story(word_count=80)
    long_story = _make_story(word_count=1200)
    short_score = score_story(short_story, target="short", used_ids=set())
    long_score = score_story(long_story, target="short", used_ids=set())
    assert short_score > long_score


def test_long_target_prefers_long_word_count():
    short_story = _make_story(word_count=80)
    long_story = _make_story(word_count=1000)
    short_score = score_story(short_story, target="long", used_ids=set())
    long_score = score_story(long_story, target="long", used_ids=set())
    assert long_score > short_score


def test_already_used_story_scores_zero():
    story = _make_story(word_count=80)
    result = score_story(story, target="short", used_ids={"x1"})
    assert result == 0.0


def test_pick_best_story_returns_highest_scoring():
    stories = [
        _make_story(id="a", word_count=80, score=500, title="meh"),
        _make_story(id="b", word_count=75, score=5000, title="What was in the basement"),
        _make_story(id="c", word_count=90, score=300, title="ok"),
    ]
    best = pick_best_story(stories, target="short", used_ids=set())
    assert best["id"] == "b"


def test_pick_best_story_returns_none_when_all_used():
    stories = [_make_story(id="a"), _make_story(id="b")]
    best = pick_best_story(stories, target="short", used_ids={"a", "b"})
    assert best is None
```

- [ ] **Step 2: Run to confirm failure**

```
python3 -m pytest channels/horror-narration/tests/test_story_scorer.py -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Create `channels/horror-narration/harness/story_scorer.py`**

```python
"""
Score and rank harvested Reddit stories for suitability as video content.

Scoring criteria (each 0–1, weighted to 0–10 total):
- Length fit (3 pts): how well word_count matches target format
- Hook strength (4 pts): does the title contain question/threat words?
- Upvote signal (3 pts): log-scaled score vs 5000 ceiling
"""
import math


SHORT_WORD_RANGE = (40, 120)
LONG_WORD_RANGE  = (600, 1800)

HOOK_WORDS = {
    "what", "why", "who", "how", "found", "heard", "saw",
    "inside", "behind", "under", "never", "disappeared",
    "wrong", "dark", "never", "alone", "last", "door",
    "basement", "woods", "road", "night", "watching", "missing",
}


def _length_score(word_count: int, target: str) -> float:
    """0–1: how well word_count fits the target format."""
    lo, hi = SHORT_WORD_RANGE if target == "short" else LONG_WORD_RANGE
    if lo <= word_count <= hi:
        return 1.0
    if target == "short":
        dist = min(abs(word_count - lo), abs(word_count - hi))
        return max(0.0, 1.0 - dist / lo)
    dist = min(abs(word_count - lo), abs(word_count - hi))
    return max(0.0, 1.0 - dist / lo)


def _hook_score(title: str) -> float:
    """0–1: fraction of hook words present in title (capped at 1)."""
    words = set(title.lower().split())
    hits = len(words & HOOK_WORDS)
    return min(1.0, hits / 2)


def _upvote_score(score: int) -> float:
    """0–1: log-scaled, ceiling at 5000 upvotes."""
    return min(1.0, math.log1p(score) / math.log1p(5000))


def score_story(story: dict, target: str, used_ids: set) -> float:
    """
    Return a score 0–10 for this story.
    Returns 0.0 immediately if story id is in used_ids.

    Args:
        story: dict with keys word_count, title, score, id
        target: "short" or "long"
        used_ids: set of post IDs already used in previous runs
    """
    if story["id"] in used_ids:
        return 0.0

    length  = _length_score(story["word_count"], target) * 3
    hook    = _hook_score(story["title"]) * 4
    upvotes = _upvote_score(story["score"]) * 3
    return round(length + hook + upvotes, 2)


def pick_best_story(stories: list, target: str, used_ids: set) -> dict | None:
    """
    Return the highest-scoring story, or None if all are already used.

    Args:
        stories: list of story dicts from reddit_harvest
        target: "short" or "long"
        used_ids: set of already-used post IDs
    """
    scored = [(score_story(s, target, used_ids), s) for s in stories]
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_story = scored[0] if scored else (0, None)
    return best_story if best_score > 0 else None
```

- [ ] **Step 4: Run tests**

```
python3 -m pytest channels/horror-narration/tests/test_story_scorer.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add channels/horror-narration/harness/story_scorer.py channels/horror-narration/tests/test_story_scorer.py
git commit -m "feat: story_scorer — score Reddit stories by length fit, hook strength, upvotes"
```

---

### Task 4: Story rewriter (Claude integration)

**Files:**
- Create: `channels/horror-narration/harness/story_rewriter.py`
- Create: `channels/horror-narration/tests/test_story_rewriter.py`

- [ ] **Step 1: Write the failing tests**

Create `channels/horror-narration/tests/test_story_rewriter.py`:

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


def _make_story():
    return {
        "id": "abc123",
        "title": "I found something in the woods",
        "text": "It started on a Tuesday. " * 50,
        "author": "author1",
        "subreddit": "nosleep",
        "score": 2000,
        "num_comments": 150,
        "url": "https://www.reddit.com/r/nosleep/abc123/",
        "word_count": 250,
    }


def test_rewrite_returns_required_fields():
    """rewrite_story returns dict with all required keys."""
    from channels.horror_narration.harness.story_rewriter import rewrite_story

    fake_response = {
        "script": "The darkness had been following him for weeks.",
        "title": "What was following him home",
        "hook_overlay": "SOMETHING WAS FOLLOWING HIM",
        "hashtags": ["horror", "nosleep"],
        "topic_cluster": "nosleep",
        "source_attribution": "Inspired by u/author1 on r/nosleep",
        "format": "short",
    }

    with patch("anthropic.Anthropic") as mock_client:
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=json.dumps(fake_response))]
        mock_client.return_value.messages.create.return_value = mock_msg

        result = rewrite_story(_make_story(), target="short", prompt_text="rewrite this")

    assert result["script"] == fake_response["script"]
    assert result["title"] == fake_response["title"]
    assert result["hook_overlay"] == fake_response["hook_overlay"]
    assert result["source_attribution"] == fake_response["source_attribution"]
    assert result["topic_cluster"] == "nosleep"


def test_rewrite_raises_on_policy_error():
    """If Claude returns {"error": "policy"}, rewrite_story raises ValueError."""
    from channels.horror_narration.harness.story_rewriter import rewrite_story

    with patch("anthropic.Anthropic") as mock_client:
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=json.dumps({"error": "policy"}))]
        mock_client.return_value.messages.create.return_value = mock_msg

        with pytest.raises(ValueError, match="policy"):
            rewrite_story(_make_story(), target="short", prompt_text="rewrite")


def test_rewrite_includes_source_in_prompt():
    """The Claude prompt must include the story text and source URL."""
    from channels.horror_narration.harness.story_rewriter import _build_rewrite_prompt

    story = _make_story()
    prompt = _build_rewrite_prompt(story, target="short")
    assert story["text"][:50] in prompt
    assert story["url"] in prompt
    assert story["author"] in prompt
```

- [ ] **Step 2: Run to confirm failure**

```
python3 -m pytest channels/horror-narration/tests/test_story_rewriter.py -v 2>&1 | tail -10
```

Expected: ImportError.

- [ ] **Step 3: Create `channels/horror-narration/harness/story_rewriter.py`**

```python
"""
Rewrite a Reddit horror story into an original narration script using Claude.
"""
import json
import os
import anthropic


def _build_rewrite_prompt(story: dict, target: str) -> str:
    word_target = "60-90 words" if target == "short" else "800-1400 words"
    return (
        f"Rewrite the following Reddit story as an original horror narration script.\n"
        f"Target format: {target} ({word_target}).\n"
        f"Source: posted by u/{story['author']} on r/{story['subreddit']}\n"
        f"Original URL: {story['url']}\n\n"
        f"--- STORY START ---\n{story['text']}\n--- STORY END ---\n\n"
        f"Respond with a JSON object only. No markdown. No explanation."
    )


def rewrite_story(story: dict, target: str, prompt_text: str) -> dict:
    """
    Send a story to Claude for rewriting. Returns the parsed JSON response.

    Args:
        story: dict from reddit_harvest (has text, author, subreddit, url, id)
        target: "short" or "long"
        prompt_text: contents of the channel's prompt.txt (system prompt)

    Returns:
        dict with keys: script, title, hook_overlay, hashtags,
                        topic_cluster, source_attribution, format

    Raises:
        ValueError: if Claude returns a policy error
        json.JSONDecodeError: if response is not valid JSON
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    user_prompt = _build_rewrite_prompt(story, target)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=prompt_text,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()
    result = json.loads(raw)

    if result.get("error") == "policy":
        raise ValueError(f"Story declined by policy filter: {story['id']}")

    return result
```

- [ ] **Step 4: Run tests**

```
python3 -m pytest channels/horror-narration/tests/test_story_rewriter.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add channels/horror-narration/harness/story_rewriter.py channels/horror-narration/tests/test_story_rewriter.py
git commit -m "feat: story_rewriter — Claude rewrites Reddit story into original narration script"
```

---

### Task 5: Horror channel orchestrator

**Files:**
- Create: `channels/horror-narration/harness/orchestrator.py`

This orchestrator replaces `generate_script.py` for the horror channel. Everything after script generation (audio, video, upload) reuses the existing shared pipeline.

- [ ] **Step 1: Create `channels/horror-narration/harness/orchestrator.py`**

```python
"""
Horror-Narration Channel Orchestrator
Entry point: python -m harness.orchestrator --channel horror-narration
Overrides the script generation stage with Reddit harvest → score → rewrite.
All other stages (audio, video, upload, evals) are shared pipeline.
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Add repo root to path so shared modules are importable
import os
sys.path.insert(0, str(Path(__file__).parents[3]))

from channel_config import load_channel_config
from generate_audio import generate_audio
from build_video import build_video
from upload_youtube import upload_youtube
from utils import init_logger, log, clear_outputs_dir, move_outputs_to_archive
from harness.storage import atomic_write, atomic_read, get_state_path
from harness.evals.audio_eval import audio_eval
from harness.evals.video_eval import video_eval
from harness.evals.base import save_eval_result
from harness.agents.format_picker import pick_format
from config import VideoFormat

from .reddit_harvest import harvest_channel
from .story_scorer import pick_best_story
from .story_rewriter import rewrite_story


def run_horror_pipeline(channel_config=None) -> dict:
    if channel_config is None:
        channel_config = load_channel_config("horror-narration")

    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    init_logger(run_id)
    log(f"🕯️ Horror Narration Harness — starting pipeline [{channel_config.slug}]")
    clear_outputs_dir()

    state_path = get_state_path(channel_config)
    try:
        state = atomic_read(state_path)
    except FileNotFoundError:
        state = {}

    used_ids = set(state.get("used_story_ids", []))
    recent_runs = state.get("recent_runs", [])

    # ── Format decision ───────────────────────────────────────────────────────
    fmt = pick_format("nosleep", recent_runs)
    target = "long" if fmt == VideoFormat.LONG else "short"
    log(f"🎬 Format: {fmt.value} / target: {target}")

    # ── Harvest stories ───────────────────────────────────────────────────────
    log("🕸️  Harvesting Reddit stories...")
    try:
        stories = harvest_channel(channel_config)
        log(f"📚 Harvested {len(stories)} stories")
    except Exception as e:
        log(f"❌ Harvest failed: {e}", level="error")
        return {"success": False, "video_url": None, "reason": f"harvest failed: {e}"}

    # ── Pick best story ───────────────────────────────────────────────────────
    story = pick_best_story(stories, target=target, used_ids=used_ids)
    if story is None:
        return {"success": False, "video_url": None, "reason": "no unused stories available"}
    log(f"📖 Selected: '{story['title']}' by u/{story['author']} (r/{story['subreddit']})")

    # ── Rewrite with Claude ───────────────────────────────────────────────────
    prompt_text = channel_config.prompt_path.read_text(encoding="utf-8")
    try:
        script_data = rewrite_story(story, target=target, prompt_text=prompt_text)
    except ValueError as e:
        return {"success": False, "video_url": None, "reason": str(e)}
    log(f"✍️  Script rewritten: {len(script_data['script'].split())} words")

    # Write metadata.json for upload_youtube to read
    metadata = {
        "title": script_data["title"],
        "script": script_data["script"],
        "hashtags": script_data.get("hashtags", ["horror", "scarystories"]),
        "topic_cluster": script_data.get("topic_cluster", "nosleep"),
        "hook_overlay": script_data.get("hook_overlay", ""),
        "source_attribution": script_data.get("source_attribution", ""),
    }
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    (outputs_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Audio generation ──────────────────────────────────────────────────────
    log("🎙️ Generating voiceover...")
    try:
        audio_duration, word_timestamps = generate_audio(
            script=script_data["script"],
            voice_id=channel_config.voice_id,
        )
    except Exception as e:
        return {"success": False, "video_url": None, "reason": f"audio failed: {e}"}

    audio_path = Path("outputs/voiceover.mp3")
    audio_result = audio_eval(audio_path)
    save_eval_result(audio_result, run_id)
    if not audio_result.passed:
        move_outputs_to_archive(run_id)
        return {"success": False, "video_url": None, "reason": "audio_eval failed"}

    # ── Video build ───────────────────────────────────────────────────────────
    log("🎬 Building video...")
    video_path = build_video(
        audio_duration,
        word_timestamps=word_timestamps,
        hook_overlay=metadata["hook_overlay"],
        fmt=fmt,
    )
    video_result = video_eval(Path(video_path), fmt=fmt)
    save_eval_result(video_result, run_id)
    if not video_result.passed:
        move_outputs_to_archive(run_id)
        return {"success": False, "video_url": None, "reason": "video_eval failed"}

    # ── Upload ────────────────────────────────────────────────────────────────
    video_url = upload_youtube(channel_config=channel_config)
    log(f"🎉 Live: {video_url}")

    # ── Save state ────────────────────────────────────────────────────────────
    used_ids.add(story["id"])
    state["used_story_ids"] = list(used_ids)
    state.setdefault("recent_runs", []).insert(0, {
        "topic_cluster": metadata["topic_cluster"],
        "format": fmt.value,
        "run_id": run_id,
    })
    state["recent_runs"] = state["recent_runs"][:50]
    atomic_write(state_path, state)

    move_outputs_to_archive(run_id)
    return {"success": True, "video_url": video_url, "reason": None}


if __name__ == "__main__":
    result = run_horror_pipeline()
    if not result["success"]:
        log(f"❌ Pipeline failed: {result['reason']}", level="error")
        sys.exit(1)
    sys.exit(0)
```

- [ ] **Step 2: Check `generate_audio` accepts `voice_id` param**

```
python3 -c "import inspect; from generate_audio import generate_audio; print(inspect.signature(generate_audio))"
```

If `generate_audio` does NOT accept `voice_id`, read the function and add it as an optional param that overrides the config default. The orchestrator needs to pass the channel's voice_id.

- [ ] **Step 3: Run a dry-run test (no Reddit API, mock harvest)**

```
source venv/bin/activate && python3 -c "
from channels.horror_narration.harness.story_scorer import pick_best_story
from channels.horror_narration.harness.story_rewriter import _build_rewrite_prompt

# Verify imports work
print('✅ story_scorer imported')
print('✅ story_rewriter imported')

story = {
    'id': 'test1', 'title': 'What was watching from the treeline',
    'text': 'word ' * 100, 'author': 'test_author', 'subreddit': 'nosleep',
    'score': 2000, 'num_comments': 100,
    'url': 'https://reddit.com/r/nosleep/test1/', 'word_count': 100,
}
best = pick_best_story([story], target='short', used_ids=set())
print('best story:', best['title'])
prompt = _build_rewrite_prompt(story, 'short')
print('prompt contains author:', story['author'] in prompt)
print('✅ All imports and logic OK')
"
```

Expected: all ✅ lines.

- [ ] **Step 4: Commit**

```bash
git add channels/horror-narration/harness/orchestrator.py
git commit -m "feat: horror-narration orchestrator — harvest → score → rewrite → audio → video → upload"
```

---

### Task 6: Add `generate_audio` voice_id param if missing

**Files:**
- Modify: `generate_audio.py` (only if voice_id param doesn't exist)

- [ ] **Step 1: Check current signature**

```
python3 -c "import inspect; from generate_audio import generate_audio; print(inspect.signature(generate_audio))"
```

If output includes `voice_id` already → skip this task entirely.

- [ ] **Step 2: If voice_id param is missing — add it**

Read `generate_audio.py`. Find where `voice_id` is loaded from config:
```python
    voice_id = cfg["elevenlabs_voice_id"]
```
Change the function signature from:
```python
def generate_audio() -> tuple:
```
to:
```python
def generate_audio(script: str = None, voice_id: str = None) -> tuple:
```

At the top of the function, after loading config:
```python
    if voice_id is None:
        voice_id = cfg["elevenlabs_voice_id"]
    if script is None:
        # load from outputs/metadata.json as before
        ...
```

- [ ] **Step 3: Run full test suite to confirm nothing broke**

```
python3 -m pytest tests/ -q 2>&1 | tail -10
```

- [ ] **Step 4: Commit**

```bash
git add generate_audio.py
git commit -m "feat: generate_audio accepts optional voice_id and script params for multi-channel"
```

---

### Task 7: End-to-end smoke test (mocked Reddit)

- [ ] **Step 1: Create a smoke test script**

Create `channels/horror-narration/tests/test_smoke.py`:

```python
"""
Smoke test: runs the full horror pipeline with mocked Reddit and Claude calls.
Does NOT make real API calls. Does NOT upload to YouTube.
"""
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_horror_pipeline_smoke(tmp_path, monkeypatch):
    """Full pipeline with all external calls mocked returns success."""
    from channel_config import load_channel_config
    cfg = load_channel_config("horror-narration")

    fake_story = {
        "id": "smoke1", "title": "What was in the basement",
        "text": "word " * 100, "author": "testuser", "subreddit": "nosleep",
        "score": 3000, "num_comments": 200,
        "url": "https://reddit.com/r/nosleep/smoke1/", "word_count": 100,
    }
    fake_script = {
        "script": "The darkness crept in slowly. " * 5,
        "title": "What was in the basement",
        "hook_overlay": "WHAT WAS DOWNSTAIRS",
        "hashtags": ["horror"],
        "topic_cluster": "nosleep",
        "source_attribution": "Inspired by u/testuser on r/nosleep",
        "format": "short",
    }

    with patch("channels.horror_narration.harness.orchestrator.harvest_channel", return_value=[fake_story]), \
         patch("channels.horror_narration.harness.orchestrator.rewrite_story", return_value=fake_script), \
         patch("channels.horror_narration.harness.orchestrator.generate_audio", return_value=(20.0, [])), \
         patch("channels.horror_narration.harness.orchestrator.build_video", return_value="outputs/final_video.mp4"), \
         patch("channels.horror_narration.harness.orchestrator.audio_eval") as mock_audio_eval, \
         patch("channels.horror_narration.harness.orchestrator.video_eval") as mock_video_eval, \
         patch("channels.horror_narration.harness.orchestrator.upload_youtube", return_value="https://youtube.com/shorts/test"), \
         patch("channels.horror_narration.harness.orchestrator.move_outputs_to_archive"), \
         patch("channels.horror_narration.harness.orchestrator.clear_outputs_dir"), \
         patch("channels.horror_narration.harness.orchestrator.save_eval_result"), \
         patch("channels.horror_narration.harness.orchestrator.atomic_write"), \
         patch("channels.horror_narration.harness.orchestrator.atomic_read", return_value={}), \
         patch("Path.mkdir"):

        from harness.evals.base import EvalResult
        mock_audio_eval.return_value = EvalResult(name="audio_eval", passed=True, score=1.0, reasoning="ok")
        mock_video_eval.return_value = EvalResult(name="video_eval", passed=True, score=1.0, reasoning="ok")

        from channels.horror_narration.harness.orchestrator import run_horror_pipeline
        result = run_horror_pipeline(channel_config=cfg)

    assert result["success"] is True
    assert "youtube.com" in result["video_url"]
```

- [ ] **Step 2: Run the smoke test**

```
python3 -m pytest channels/horror-narration/tests/test_smoke.py -v
```

Expected: 1 passed.

- [ ] **Step 3: Run full test suite**

```
python3 -m pytest tests/ channels/horror-narration/tests/ -q 2>&1 | tail -15
```

Expected: horror-narration tests pass, no regressions in main suite.

- [ ] **Step 4: Commit**

```bash
git add channels/horror-narration/tests/test_smoke.py
git commit -m "test: horror-narration smoke test — full pipeline with mocked external calls"
```

---

## Self-Review

**Spec coverage:**
- ✅ Separate channel dir (`channels/horror-narration/`) — Task 1
- ✅ Reddit harvest (PRAW, primary+secondary subreddits, filters) — Task 2
- ✅ Opt-out author list — Task 2 (`opt_out_authors` param)
- ✅ Story scoring (length fit, hook strength, upvote signal, dedup by used_ids) — Task 3
- ✅ Claude rewrite (original script, title, hook_overlay, attribution) — Task 4
- ✅ Policy filter (suicide/self-harm stories declined) — Task 4 (handled in prompt.txt + error raise)
- ✅ Source attribution in every video description — Task 4 + metadata.json
- ✅ Voice ID per channel — Task 1 (settings.json) + Task 6 (generate_audio param)
- ✅ Separate state/used_ids per channel — Task 5 (state stored in channel data dir)
- ✅ Format picker (Short vs Long) — Task 5 (uses existing pick_format)
- ✅ Does not break Canine Wisdom — new modules are isolated in channels/horror-narration/
- ✅ Smoke test covering full pipeline — Task 7

**Placeholder scan:**
- `affiliate_links` in settings.json uses placeholder Amazon URLs — replace with real links when client provides them (noted inline).
- `voice_id: "ErXwobaYiN019PkySvjV"` — this is an ElevenLabs sample voice ID; client must replace with their chosen voice.

**Type consistency:**
- `story` dict keys (`id`, `title`, `text`, `author`, `subreddit`, `score`, `word_count`, `url`) consistent across harvest → scorer → rewriter.
- `channel_config` param name consistent with Plan A throughout.
- `target` ("short"/"long") distinct from `fmt` (VideoFormat enum) — used correctly in scorer/rewriter, converted to VideoFormat in orchestrator.
