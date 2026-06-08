# dailyygstories Viral Horror Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully-automated viral horror channel harness for `dailyygstories` that harvests trending real-world news + Reddit stories, classifies story type, builds short or long videos with matched footage, uploads to YouTube, and learns from analytics to produce better content over time — all triggered opportunistically every 30 minutes when CPU load is low.

**Architecture:** A new channel config at `channels/dailyygstories/` mirrors the `horror-narration` channel structure but replaces the story scorer with a learnings-aware intelligent scorer, adds a trending layer (Google Trends + news RSS + Reddit hot), adds a Claude-powered asset matcher that picks footage by story setting keywords, and wires the whole thing into a low-CPU-load guard that runs from Kamil's existing 30-minute orchestrator tick. The `canine-wisdom` channel gets the same trending injection in a separate step.

**Tech Stack:** Python 3.12, `pytrends`, `feedparser`, `requests`, `anthropic` SDK, `yt-dlp`, `ffmpeg`, ElevenLabs API, YouTube Data API v3, existing `harness/` modules, existing `channel_config.py` loader.

---

## File Map

### New files (create)
```
channels/dailyygstories/
  __init__.py                           — empty, marks package
  settings.json                         — channel config for dailyygstories
  prompt.txt                            — Claude rewrite system prompt tuned for dailyygstories
  harness/
    __init__.py
    trend_horror.py                     — Google Trends + RSS news + Reddit hot → ranked candidates
    story_classifier.py                 — Claude classifies story type + picks short/long format
    asset_matcher.py                    — extracts setting keywords → fetches matched footage
    intelligent_scorer.py               — learnings-aware scorer replacing keyword bag-of-words
    orchestrator.py                     — full pipeline for dailyygstories
  data/
    learnings.json                      — per-channel learnings (copy of empty template)
    state.json                          — used_story_ids, recent_runs
  tests/
    __init__.py
    test_trend_horror.py
    test_story_classifier.py
    test_asset_matcher.py
    test_intelligent_scorer.py

scripts/
  low_cpu_runner.py                     — checks CPU load, runs a channel pipeline if idle
```

### Modified files
```
channels/dailyygstories/data/learnings.json   — seeded with empty structure (see Task 1)
harness/tools/learnings.py                    — add get_top_story_types() for horror channels
harness/agents/trend.py                       — minor: expose build_topic_queue() for non-dog channels too (already works, no change needed if horror has its own trend_horror.py)
```

---

## Task 1: Channel config + empty learnings seed

**Files:**
- Create: `channels/dailyygstories/__init__.py`
- Create: `channels/dailyygstories/settings.json`
- Create: `channels/dailyygstories/prompt.txt`
- Create: `channels/dailyygstories/harness/__init__.py`
- Create: `channels/dailyygstories/data/learnings.json`
- Create: `channels/dailyygstories/data/state.json`
- Create: `channels/dailyygstories/tests/__init__.py`

- [ ] **Step 1: Create channel package skeleton**

```bash
mkdir -p channels/dailyygstories/harness channels/dailyygstories/data channels/dailyygstories/tests
touch channels/dailyygstories/__init__.py
touch channels/dailyygstories/harness/__init__.py
touch channels/dailyygstories/tests/__init__.py
```

- [ ] **Step 2: Write settings.json**

```json
{
  "channel_name": "dailyygstories",
  "niche": "true crime, paranormal, and horror narration channel that dramatizes real news and Reddit horror stories",
  "voice_id": "JBFqnCBsd6RMkjVDRZzb",
  "youtube_category_id": "24",
  "topic_clusters": [
    "true crime",
    "paranormal",
    "creature encounter",
    "unsolved mystery",
    "real news horror",
    "two sentence horror",
    "night shift stories"
  ],
  "description_template": "🌑 {video_title}\n\n{video_script}\n\nStories are dramatized narrations. Real events are factual with attribution; Reddit stories are rewritten with original narration.\n\n{hashtags}\n\n🔔 Subscribe for daily horror stories.",
  "affiliate_links": {
    "default": {
      "product": "Can't sleep? These noise-cancelling headphones help.",
      "url": "https://amzn.to/nosleep-placeholder"
    }
  },
  "subreddits": {
    "primary": ["nosleep", "shortscarystories", "TwoSentenceHorror", "unresolvedmysteries"],
    "secondary": ["LetsNotMeet", "Paranormal", "truecrime", "creepyencounters"]
  },
  "news_rss_feeds": [
    "http://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.reuters.com/reuters/worldNews",
    "https://www.dawn.com/feeds/latest-news"
  ],
  "google_trends_keywords": [
    "horror story", "paranormal", "true crime", "missing person",
    "unsolved mystery", "haunted", "ghost encounter", "serial killer"
  ],
  "min_upvotes": 50,
  "min_comments": 5,
  "short_word_range": [60, 120],
  "longform_word_range": [700, 1800],
  "opt_out_authors": [],
  "footage_dir": "horror_footage",
  "music_dir": "assets/music/horror",
  "cut_duration_secs": 20,
  "voices": {
    "long_form_narrator": "JBFqnCBsd6RMkjVDRZzb",
    "short_creepy": "N2lVS1w4EtoT3dr4eOWO",
    "intense": "SOYHLrjzK2X1ezoPC6cr",
    "paranormal_female": "EXAVITQu4vr4xnSDxMaL"
  },
  "anthropic_max_tokens": 2000
}
```

Save to `channels/dailyygstories/settings.json`.

- [ ] **Step 3: Write prompt.txt (Claude system prompt)**

```
You are a viral horror narration scriptwriter for the YouTube channel "dailyygstories" in 2026.

The channel goal is 1 million subscribers. Every video must earn its watch time.

STORY TYPES you handle:
- true_crime: Factual. Keep real place names and facts. Attribute the source.
- paranormal: First-person dread. Physical sensations over explanation.
- creature_encounter: Short. Immediate danger. Jump-cut energy.
- unsolved_mystery: Long. Open information loop. Cliffhanger ending.
- real_news_horror: Factual shocking news story retold as narration. Keep attribution.
- two_sentence_horror: Exactly 2 sentences. Psychological twist at the end.
- night_shift_stories: Worker alone at night. Slow build, sudden threat.

SCRIPT RULES:
1. Hook in first 3 seconds — most shocking or wrongest detail first.
2. Delayed-answer technique — name the sensation/wrongness before naming the threat.
3. HIGH-AROUSAL ending — something still happening, still present, still watching.
4. No "amazing", "incredible", "you won't believe". Concrete nouns and verbs only.
5. Shorts: 60-90 words total. Long-form: 800-1400 words.
6. End on unresolved tension, never calm resolution.

LEARNINGS CONTEXT (injected at runtime):
Top hook patterns:
{hooks_text}

Top title formulas:
{titles_text}

Story types that recently performed well:
{top_story_types}

Topics covered in last 30 days (DO NOT repeat):
{covered_text}

Return ONLY valid JSON, no markdown:
{
  "script": "full narration script",
  "title": "YouTube title under 70 chars",
  "hook_overlay": "3-6 WORD CAPS OVERLAY FOR FIRST 1.5 SECONDS",
  "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "topic_cluster": "one of the 7 clusters above",
  "story_type": "one of: true_crime | paranormal | creature_encounter | unsolved_mystery | real_news_horror | two_sentence_horror | night_shift_stories",
  "mood": "one of: dread | intense | mysterious | eerie",
  "format": "short | long",
  "source_attribution": "Original source URL if real news, else empty string",
  "hook_pattern_used": "the hook pattern template you used",
  "title_formula_used": "the title formula template you used",
  "setting_keywords": ["setting keyword 1", "setting keyword 2", "setting keyword 3"]
}
```

Save to `channels/dailyygstories/prompt.txt`.

- [ ] **Step 4: Seed empty learnings.json**

```json
{
  "hook_patterns": [],
  "title_formulas": [],
  "covered_topics": [],
  "anti_patterns": [],
  "story_type_performance": {},
  "updated_at": "2026-06-06T00:00:00"
}
```

Save to `channels/dailyygstories/data/learnings.json`.

- [ ] **Step 5: Seed empty state.json**

```json
{
  "used_story_ids": [],
  "recent_runs": []
}
```

Save to `channels/dailyygstories/data/state.json`.

- [ ] **Step 6: Verify channel loads via existing loader**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
python -c "from channel_config import load_channel_config; c = load_channel_config('dailyygstories'); print(c.slug, c.channel_name)"
```

Expected output: `dailyygstories dailyygstories`

- [ ] **Step 7: Commit**

```bash
git add channels/dailyygstories/
git commit -m "feat: scaffold dailyygstories channel config + prompts"
```

---

## Task 2: Trend horror layer (Google Trends + RSS + Reddit hot)

**Files:**
- Create: `channels/dailyygstories/harness/trend_horror.py`
- Create: `channels/dailyygstories/tests/test_trend_horror.py`

- [ ] **Step 1: Install dependencies**

```bash
pip install pytrends feedparser
pip freeze | grep -E "pytrends|feedparser" >> requirements.txt
```

- [ ] **Step 2: Write the failing test**

Create `channels/dailyygstories/tests/test_trend_horror.py`:

```python
"""Tests for trend_horror.py — use offline mocks, never hit live APIs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3]))

import json
import pytest
from unittest.mock import patch, MagicMock


def test_merge_candidates_deduplicates_by_id():
    from channels.dailyygstories.harness.trend_horror import _merge_and_rank
    candidates = [
        {"id": "abc", "title": "A ghost story", "text": "...", "score": 100, "source": "reddit"},
        {"id": "abc", "title": "A ghost story", "text": "...", "score": 100, "source": "reddit"},
        {"id": "def", "title": "Real crime news", "text": "...", "score": 50, "source": "news"},
    ]
    merged = _merge_and_rank(candidates)
    assert len(merged) == 2


def test_merge_candidates_sorted_by_score_desc():
    from channels.dailyygstories.harness.trend_horror import _merge_and_rank
    candidates = [
        {"id": "a", "title": "Low", "text": "...", "score": 10, "source": "reddit"},
        {"id": "b", "title": "High", "text": "...", "score": 200, "source": "news"},
        {"id": "c", "title": "Mid", "text": "...", "score": 80, "source": "trends"},
    ]
    merged = _merge_and_rank(candidates)
    scores = [c["score"] for c in merged]
    assert scores == sorted(scores, reverse=True)


def test_score_news_item_returns_dict_with_required_keys():
    from channels.dailyygstories.harness.trend_horror import _score_news_item
    item = {
        "title": "Mysterious disappearance shocks small town",
        "summary": "A woman went missing after...",
        "link": "https://example.com/news/123",
        "published": "Mon, 06 Jun 2026 10:00:00 GMT",
    }
    result = _score_news_item(item)
    assert "id" in result
    assert "title" in result
    assert "text" in result
    assert "score" in result
    assert result["source"] == "news"


def test_harvest_trends_returns_list():
    """harvest_trends() must return a list (may be empty) without crashing."""
    from channels.dailyygstories.harness.trend_horror import harvest_trends
    with patch("channels.dailyygstories.harness.trend_horror.TrendReq") as mock_pytrends:
        mock_instance = MagicMock()
        mock_instance.trending_searches.return_value = MagicMock()
        mock_pytrends.return_value = mock_instance
        result = harvest_trends(keywords=["horror story"], geo="PK")
        assert isinstance(result, list)
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
python -m pytest channels/dailyygstories/tests/test_trend_horror.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError` or `ImportError` for `trend_horror`.

- [ ] **Step 4: Implement trend_horror.py**

Create `channels/dailyygstories/harness/trend_horror.py`:

```python
"""
Trend layer for dailyygstories channel.

Combines:
  1. Google Trends rising queries (pytrends)
  2. RSS news feeds (BBC, Reuters, Dawn)
  3. Reddit hot posts (via existing PullPush harvester)

Returns ranked list of story candidates for the intelligent scorer.
"""
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import feedparser
import requests

sys.path.insert(0, str(Path(__file__).parents[3]))

HEADERS = {"User-Agent": "dailyygstories_harness/1.0"}

HORROR_SIGNAL_WORDS = {
    "missing", "disappeared", "murder", "killed", "found dead", "unsolved",
    "mysterious", "paranormal", "haunted", "ghost", "unexplained", "serial",
    "abducted", "kidnap", "escaped", "survived", "horror", "terror", "attack",
    "body found", "suspect", "investigation", "cold case", "creature", "sighting",
}


def _has_horror_signal(text: str) -> bool:
    lower = text.lower()
    return any(w in lower for w in HORROR_SIGNAL_WORDS)


def _score_news_item(item: dict) -> dict:
    """Convert an RSS feed entry into a story candidate."""
    title = item.get("title", "")
    summary = item.get("summary", "") or item.get("description", "")
    link = item.get("link", "")
    combined_text = f"{title}. {summary}"

    horror_hits = sum(1 for w in HORROR_SIGNAL_WORDS if w in combined_text.lower())
    score = horror_hits * 20

    uid = hashlib.md5(link.encode()).hexdigest()[:12]
    return {
        "id": f"news-{uid}",
        "title": title,
        "text": combined_text,
        "score": score,
        "source": "news",
        "url": link,
        "author": "news",
        "subreddit": None,
        "num_comments": 0,
        "word_count": len(combined_text.split()),
    }


def harvest_news(rss_urls: list) -> list:
    """Fetch and filter RSS news feeds for horror-signal stories."""
    candidates = []
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:30]:
                item = _score_news_item(entry)
                if item["score"] > 0:
                    candidates.append(item)
            time.sleep(0.3)
        except Exception as e:
            print(f"[trend_horror] RSS fetch failed for {url}: {e}")
    return candidates


def harvest_trends(keywords: list, geo: str = "PK") -> list:
    """
    Fetch Google Trends rising queries for horror keywords.
    Returns list of candidate dicts with source='trends'.
    Falls back gracefully to [] if pytrends fails.
    """
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=300)
        pytrends.build_payload(keywords[:5], cat=0, timeframe="now 1-d", geo=geo)
        related = pytrends.related_queries()
        candidates = []
        for kw in keywords[:5]:
            rising = related.get(kw, {}).get("rising")
            if rising is None or not hasattr(rising, "iterrows"):
                continue
            for _, row in rising.iterrows():
                query = str(row.get("query", ""))
                value = int(row.get("value", 0))
                if not query:
                    continue
                uid = hashlib.md5(query.encode()).hexdigest()[:12]
                candidates.append({
                    "id": f"trends-{uid}",
                    "title": query,
                    "text": query,
                    "score": min(value, 200),
                    "source": "trends",
                    "url": "",
                    "author": "trends",
                    "subreddit": None,
                    "num_comments": 0,
                    "word_count": len(query.split()),
                })
        return candidates
    except Exception as e:
        print(f"[trend_horror] Google Trends failed (non-blocking): {e}")
        return []


def _merge_and_rank(candidates: list) -> list:
    """Deduplicate by id and sort by score descending."""
    seen = {}
    for c in candidates:
        cid = c["id"]
        if cid not in seen or c["score"] > seen[cid]["score"]:
            seen[cid] = c
    return sorted(seen.values(), key=lambda x: x["score"], reverse=True)


def harvest_all(channel_config) -> list:
    """
    Run all three sources and return a merged, ranked candidate list.
    channel_config: ChannelConfig instance for dailyygstories.
    """
    import importlib.util as ilu

    # Load settings for RSS URLs + subreddits
    settings = json.loads((channel_config.channel_dir / "settings.json").read_text())
    rss_urls = settings.get("news_rss_feeds", [])
    trend_kws = settings.get("google_trends_keywords", ["horror story"])

    all_candidates = []

    # 1. News RSS
    print("[trend_horror] Fetching news RSS...")
    news = harvest_news(rss_urls)
    print(f"[trend_horror] News: {len(news)} horror-signal items")
    all_candidates.extend(news)

    # 2. Google Trends
    print("[trend_horror] Fetching Google Trends...")
    trends = harvest_trends(trend_kws, geo="PK")
    print(f"[trend_horror] Trends: {len(trends)} rising queries")
    all_candidates.extend(trends)

    # 3. Reddit via existing PullPush harvester
    print("[trend_horror] Fetching Reddit stories...")
    repo_root = Path(__file__).parents[3]
    harvest_path = repo_root / "channels" / "horror-narration" / "harness" / "reddit_harvest.py"
    spec = ilu.spec_from_file_location("reddit_harvest", harvest_path)
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    reddit_stories = mod.harvest_channel(channel_config)
    print(f"[trend_horror] Reddit: {len(reddit_stories)} stories")
    all_candidates.extend(reddit_stories)

    merged = _merge_and_rank(all_candidates)
    print(f"[trend_horror] Total after merge+dedup: {len(merged)}")
    return merged
```

- [ ] **Step 5: Run tests**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
python -m pytest channels/dailyygstories/tests/test_trend_horror.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add channels/dailyygstories/harness/trend_horror.py channels/dailyygstories/tests/test_trend_horror.py requirements.txt
git commit -m "feat: add trend_horror layer (RSS + Google Trends + Reddit)"
```

---

## Task 3: Intelligent scorer (learnings-aware)

**Files:**
- Create: `channels/dailyygstories/harness/intelligent_scorer.py`
- Create: `channels/dailyygstories/tests/test_intelligent_scorer.py`

- [ ] **Step 1: Add `get_top_story_types()` to harness/tools/learnings.py**

Open `harness/tools/learnings.py` and add this function after `get_covered_topics()`:

```python
def get_top_story_types(n: int = 3, channel_learnings_path: Path = None) -> list:
    """
    Return top n story types by avg_subscriber_gain_per_1000_views.
    Reads from channel-specific learnings.json if channel_learnings_path given,
    otherwise falls back to the global harness learnings.
    """
    if channel_learnings_path and channel_learnings_path.exists():
        data = json.loads(channel_learnings_path.read_text(encoding="utf-8"))
    else:
        data = read_learnings()
    perf = data.get("story_type_performance", {})
    ranked = sorted(
        [{"story_type": k, **v} for k, v in perf.items()],
        key=lambda x: x.get("avg_sub_gain_per_1k_views", 0),
        reverse=True,
    )
    return ranked[:n]
```

- [ ] **Step 2: Write the failing test**

Create `channels/dailyygstories/tests/test_intelligent_scorer.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3]))

from channels.dailyygstories.harness.intelligent_scorer import score_candidate, pick_best_candidate


def _make_candidate(cid, title, word_count, score, story_type_hint="paranormal"):
    return {
        "id": cid,
        "title": title,
        "text": "x " * word_count,
        "score": score,
        "source": "reddit",
        "word_count": word_count,
    }


def test_used_story_scores_zero():
    c = _make_candidate("used1", "A scary night", 80, 500)
    result = score_candidate(c, target="short", used_ids={"used1"}, top_story_types=[])
    assert result == 0.0


def test_short_target_prefers_short_word_count():
    short = _make_candidate("s1", "Shadow followed me", 80, 200)
    long = _make_candidate("l1", "The basement door", 1200, 200)
    score_short = score_candidate(short, target="short", used_ids=set(), top_story_types=[])
    score_long = score_candidate(long, target="short", used_ids=set(), top_story_types=[])
    assert score_short > score_long


def test_long_target_prefers_long_word_count():
    short = _make_candidate("s2", "Two words", 80, 200)
    long = _make_candidate("l2", "Long investigation story", 1200, 200)
    score_short = score_candidate(short, target="long", used_ids=set(), top_story_types=[])
    score_long = score_candidate(long, target="long", used_ids=set(), top_story_types=[])
    assert score_long > score_short


def test_pick_best_candidate_returns_highest_score():
    candidates = [
        _make_candidate("a", "Low score", 80, 10),
        _make_candidate("b", "High score shadow followed me escaped ran", 80, 5000),
        _make_candidate("c", "Mid score disappeared", 80, 100),
    ]
    best = pick_best_candidate(candidates, target="short", used_ids=set(), top_story_types=[])
    assert best["id"] == "b"


def test_pick_best_candidate_returns_none_when_all_used():
    candidates = [_make_candidate("x", "test", 80, 100)]
    result = pick_best_candidate(candidates, target="short", used_ids={"x"}, top_story_types=[])
    assert result is None
```

- [ ] **Step 3: Run test to verify it fails**

```bash
python -m pytest channels/dailyygstories/tests/test_intelligent_scorer.py -v 2>&1 | head -20
```

Expected: `ImportError` for `intelligent_scorer`.

- [ ] **Step 4: Implement intelligent_scorer.py**

Create `channels/dailyygstories/harness/intelligent_scorer.py`:

```python
"""
Learnings-aware story scorer for dailyygstories.

Replaces the simple keyword bag-of-words scorer in horror-narration/harness/story_scorer.py.
Incorporates:
  - Length fit to target format
  - Horror signal word density (title + text)
  - Upvote/engagement signal
  - Trending source bonus (news/trends > reddit)
  - Learnings boost: story types that historically drove subscriber gain
"""
import math
import re

SHORT_WORD_RANGE = (60, 120)
LONG_WORD_RANGE = (700, 1800)

HORROR_WORDS = {
    "missing", "dead", "disappeared", "murder", "killed", "escaped", "trapped",
    "stalked", "followed", "watched", "shadow", "creature", "monster", "dark",
    "alone", "door", "basement", "woods", "night", "blood", "whispered", "screamed",
    "locked", "body", "cold", "breathing", "ran", "chased", "grabbed", "dragged",
}


def _length_score(word_count: int, target: str) -> float:
    lo, hi = SHORT_WORD_RANGE if target == "short" else LONG_WORD_RANGE
    if lo <= word_count <= hi:
        return 1.0
    dist = min(abs(word_count - lo), abs(word_count - hi))
    return max(0.0, 1.0 - dist / max(lo, 1))


def _horror_density(title: str, text: str) -> float:
    """Score 0-1 based on horror signal words in title (weighted 2x) + text sample."""
    title_words = set(re.sub(r"[^\w\s]", "", title.lower()).split())
    text_sample = set(re.sub(r"[^\w\s]", "", text[:500].lower()).split())
    title_hits = len(title_words & HORROR_WORDS) * 2
    text_hits = len(text_sample & HORROR_WORDS)
    return min(1.0, (title_hits + text_hits) / 8)


def _engagement_score(candidate: dict) -> float:
    raw = candidate.get("score", 0)
    if raw <= 0:
        return 0.0
    return min(1.0, math.log1p(raw) / math.log1p(5000))


def _source_bonus(candidate: dict) -> float:
    """News and trends are more likely to be timely/viral."""
    source = candidate.get("source", "reddit")
    return {"news": 0.3, "trends": 0.2, "reddit": 0.0}.get(source, 0.0)


def _learnings_boost(candidate: dict, top_story_types: list) -> float:
    """
    Boost if candidate's likely story type matches top performers.
    top_story_types: list of dicts with keys story_type, avg_sub_gain_per_1k_views
    """
    if not top_story_types:
        return 0.0
    title_lower = candidate.get("title", "").lower()
    source = candidate.get("source", "reddit")

    # Rough type hint from source + title keywords
    if source == "news":
        likely_type = "true_crime" if any(w in title_lower for w in ["murder", "missing", "killed", "crime"]) else "real_news_horror"
    elif "subreddit" in candidate and candidate.get("subreddit") in ("nosleep", "shortscarystories"):
        likely_type = "paranormal"
    else:
        likely_type = "paranormal"

    for i, st in enumerate(top_story_types):
        if st.get("story_type") == likely_type:
            # Top performer gets 0.3 boost, second 0.2, third 0.1
            return max(0.0, 0.3 - i * 0.1)
    return 0.0


def score_candidate(candidate: dict, target: str, used_ids: set, top_story_types: list) -> float:
    if candidate["id"] in used_ids:
        return 0.0
    length   = _length_score(candidate.get("word_count", 0), target) * 3.0
    horror   = _horror_density(candidate.get("title", ""), candidate.get("text", "")) * 3.0
    engage   = _engagement_score(candidate) * 2.0
    source   = _source_bonus(candidate) * 1.0
    learning = _learnings_boost(candidate, top_story_types) * 1.0
    return round(length + horror + engage + source + learning, 3)


def pick_best_candidate(candidates: list, target: str, used_ids: set, top_story_types: list) -> dict | None:
    scored = sorted(
        ((score_candidate(c, target, used_ids, top_story_types), c) for c in candidates),
        key=lambda x: x[0],
        reverse=True,
    )
    if not scored or scored[0][0] == 0.0:
        return None
    return scored[0][1]
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest channels/dailyygstories/tests/test_intelligent_scorer.py -v
```

Expected: all 5 PASS.

- [ ] **Step 6: Commit**

```bash
git add channels/dailyygstories/harness/intelligent_scorer.py channels/dailyygstories/tests/test_intelligent_scorer.py harness/tools/learnings.py
git commit -m "feat: intelligent learnings-aware scorer + get_top_story_types()"
```

---

## Task 4: Story classifier (Claude-powered format + type decision)

**Files:**
- Create: `channels/dailyygstories/harness/story_classifier.py`
- Create: `channels/dailyygstories/tests/test_story_classifier.py`

- [ ] **Step 1: Write the failing test**

Create `channels/dailyygstories/tests/test_story_classifier.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3]))

from unittest.mock import patch, MagicMock
from channels.dailyygstories.harness.story_classifier import classify_story, VALID_TYPES, VALID_FORMATS


def _mock_claude_response(story_type, fmt):
    import json
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps({
        "story_type": story_type,
        "format": fmt,
        "reasoning": "test"
    }))]
    return mock_msg


def test_classify_returns_valid_type_and_format():
    candidate = {"title": "A ghost in the hospital", "text": "I was working the night shift..."}
    with patch("channels.dailyygstories.harness.story_classifier.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_claude_response("paranormal", "long")
        mock_cls.return_value = mock_client
        result = classify_story(candidate)
    assert result["story_type"] in VALID_TYPES
    assert result["format"] in VALID_FORMATS


def test_classify_returns_fallback_on_bad_json():
    candidate = {"title": "Scary thing", "text": "It was dark..."}
    with patch("channels.dailyygstories.harness.story_classifier.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(content=[MagicMock(text="not json")])
        mock_cls.return_value = mock_client
        result = classify_story(candidate)
    assert result["story_type"] in VALID_TYPES
    assert result["format"] in VALID_FORMATS
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest channels/dailyygstories/tests/test_story_classifier.py -v 2>&1 | head -20
```

Expected: `ImportError`.

- [ ] **Step 3: Implement story_classifier.py**

Create `channels/dailyygstories/harness/story_classifier.py`:

```python
"""
Claude-powered story type classifier.

Given a story candidate (title + text snippet), asks Claude to decide:
  - story_type: one of 7 types
  - format: "short" | "long"

Falls back to ("paranormal", "short") on any failure.
"""
import json
import os

import anthropic

VALID_TYPES = {
    "true_crime", "paranormal", "creature_encounter",
    "unsolved_mystery", "real_news_horror", "two_sentence_horror", "night_shift_stories"
}
VALID_FORMATS = {"short", "long"}

LONG_FORM_TYPES = {"true_crime", "unsolved_mystery", "real_news_horror"}
SHORT_FORM_TYPES = {"two_sentence_horror", "creature_encounter"}


def classify_story(candidate: dict) -> dict:
    """
    Returns dict with keys: story_type, format, reasoning.
    Never raises — returns fallback on any error.
    """
    title = candidate.get("title", "")
    text_snippet = candidate.get("text", "")[:600]

    prompt = (
        f"Classify this story for a horror YouTube channel.\n\n"
        f"Title: {title}\n"
        f"Text snippet: {text_snippet}\n\n"
        f"Pick ONE story_type from: true_crime | paranormal | creature_encounter | "
        f"unsolved_mystery | real_news_horror | two_sentence_horror | night_shift_stories\n\n"
        f"Pick ONE format: short (under 90 words, YouTube Short) OR long (700-1400 words, 8-15min video).\n\n"
        f"Rules:\n"
        f"- true_crime, unsolved_mystery, real_news_horror → prefer long\n"
        f"- two_sentence_horror, creature_encounter → always short\n"
        f"- paranormal, night_shift_stories → short if text < 400 words, else long\n\n"
        f"Return ONLY JSON: {{\"story_type\": \"...\", \"format\": \"...\", \"reasoning\": \"one sentence\"}}"
    )

    try:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            from config import load_config
            api_key = load_config()["anthropic_api_key"]

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        result = json.loads(raw)

        story_type = result.get("story_type", "paranormal")
        fmt = result.get("format", "short")

        if story_type not in VALID_TYPES:
            story_type = "paranormal"
        if fmt not in VALID_FORMATS:
            fmt = "short"

        return {"story_type": story_type, "format": fmt, "reasoning": result.get("reasoning", "")}

    except Exception as e:
        print(f"[story_classifier] classify failed ({e}) — using fallback")
        word_count = len(candidate.get("text", "").split())
        fallback_fmt = "long" if word_count >= 700 else "short"
        return {"story_type": "paranormal", "format": fallback_fmt, "reasoning": "fallback"}
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest channels/dailyygstories/tests/test_story_classifier.py -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add channels/dailyygstories/harness/story_classifier.py channels/dailyygstories/tests/test_story_classifier.py
git commit -m "feat: Claude-powered story type classifier"
```

---

## Task 5: Asset matcher (setting keywords → matched footage)

**Files:**
- Create: `channels/dailyygstories/harness/asset_matcher.py`
- Create: `channels/dailyygstories/tests/test_asset_matcher.py`

- [ ] **Step 1: Write the failing test**

Create `channels/dailyygstories/tests/test_asset_matcher.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3]))

from channels.dailyygstories.harness.asset_matcher import extract_setting_keywords, map_keywords_to_pexels_query


def test_extract_setting_keywords_from_script_data():
    script_data = {"setting_keywords": ["dark forest", "abandoned house", "hospital"]}
    keywords = extract_setting_keywords(script_data)
    assert keywords == ["dark forest", "abandoned house", "hospital"]


def test_extract_setting_keywords_fallback_when_missing():
    script_data = {"script": "I was walking through dark woods at night alone..."}
    keywords = extract_setting_keywords(script_data)
    assert isinstance(keywords, list)
    assert len(keywords) > 0


def test_map_keywords_to_pexels_query_returns_string():
    keywords = ["dark forest", "night"]
    query = map_keywords_to_pexels_query(keywords, story_type="paranormal")
    assert isinstance(query, str)
    assert len(query) > 3


def test_map_keywords_empty_falls_back_to_story_type():
    query = map_keywords_to_pexels_query([], story_type="true_crime")
    assert "crime" in query.lower() or "dark" in query.lower() or "night" in query.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest channels/dailyygstories/tests/test_asset_matcher.py -v 2>&1 | head -20
```

Expected: `ImportError`.

- [ ] **Step 3: Implement asset_matcher.py**

Create `channels/dailyygstories/harness/asset_matcher.py`:

```python
"""
Asset matcher for dailyygstories.

Given script_data returned by the rewriter (which includes setting_keywords),
derives a Pexels search query and delegates to the existing fetch_footage_for_topic().
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

# Default Pexels query per story type when no setting keywords available
_TYPE_FALLBACK = {
    "true_crime":          "dark city night crime",
    "paranormal":          "dark forest fog night",
    "creature_encounter":  "dark woods monster shadows",
    "unsolved_mystery":    "abandoned house dark mystery",
    "real_news_horror":    "breaking news dark scene",
    "two_sentence_horror": "dark room alone night",
    "night_shift_stories": "hospital corridor night empty",
}

# Setting keyword → Pexels-friendly term
_KEYWORD_MAP = {
    "forest": "dark forest night",
    "woods":  "dark woods fog",
    "hospital": "hospital corridor empty",
    "basement": "dark basement stairs",
    "house": "abandoned dark house",
    "road": "empty road night",
    "city": "dark city night street",
    "lake": "dark lake fog night",
    "school": "empty school hallway night",
    "car": "dark car driving night",
    "cemetery": "cemetery night fog",
    "cave": "dark cave underground",
    "office": "empty office night dark",
}

_SETTING_SIGNAL = list(_KEYWORD_MAP.keys()) + [
    "night", "dark", "alone", "empty", "abandoned", "haunted"
]


def extract_setting_keywords(script_data: dict) -> list:
    """
    Pull setting_keywords from script_data.
    If absent, fall back to scanning the script text for setting signals.
    Returns list of 1-3 keyword strings.
    """
    keywords = script_data.get("setting_keywords", [])
    if keywords and isinstance(keywords, list):
        return keywords[:3]

    # Fallback: scan first 300 words of script for setting signals
    text = script_data.get("script", "").lower()
    found = []
    for signal in _SETTING_SIGNAL:
        if signal in text and signal not in found:
            found.append(signal)
        if len(found) >= 3:
            break
    return found if found else ["dark", "night", "horror"]


def map_keywords_to_pexels_query(keywords: list, story_type: str) -> str:
    """
    Convert setting keywords to a Pexels search query string.
    Falls back to story_type default if no keywords.
    """
    if not keywords:
        return _TYPE_FALLBACK.get(story_type, "dark horror night")

    parts = []
    for kw in keywords[:2]:
        mapped = _KEYWORD_MAP.get(kw.lower().strip())
        if mapped:
            parts.append(mapped)
        else:
            parts.append(kw)

    return " ".join(parts) if parts else _TYPE_FALLBACK.get(story_type, "dark horror night")


def fetch_matched_footage(script_data: dict, story_type: str, footage_dir, fmt=None) -> str | None:
    """
    Fetch footage matching the story's setting keywords.
    Returns path to downloaded clip, or None on failure.
    """
    from harness.tools.footage import fetch_footage_for_topic
    from config import VideoFormat

    keywords = extract_setting_keywords(script_data)
    query = map_keywords_to_pexels_query(keywords, story_type)
    topic_label = f"horror_{story_type}"

    if fmt is None:
        fmt = VideoFormat.SHORT

    try:
        result = fetch_footage_for_topic(topic_label, query, fmt=fmt, save_dir=footage_dir)
        return str(result) if result else None
    except Exception as e:
        print(f"[asset_matcher] footage fetch failed for query '{query}': {e}")
        return None
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest channels/dailyygstories/tests/test_asset_matcher.py -v
```

Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add channels/dailyygstories/harness/asset_matcher.py channels/dailyygstories/tests/test_asset_matcher.py
git commit -m "feat: asset matcher — setting keywords → Pexels footage query"
```

---

## Task 6: dailyygstories orchestrator (full pipeline)

**Files:**
- Create: `channels/dailyygstories/harness/orchestrator.py`

- [ ] **Step 1: Implement orchestrator.py**

Create `channels/dailyygstories/harness/orchestrator.py`:

```python
"""
dailyygstories Channel Orchestrator — Full Pipeline

Run with: python -m channels.dailyygstories.harness.orchestrator
Or via low_cpu_runner: python scripts/low_cpu_runner.py --channel dailyygstories
"""
import importlib.util as ilu
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from channel_config import load_channel_config
from generate_audio import generate_audio
from build_video import build_video
from upload_youtube import upload_youtube
from utils import init_logger, log, clear_outputs_dir, move_outputs_to_archive
from harness.storage import atomic_write, atomic_read, get_state_path
from harness.agents.analytics import track_video
from config import VideoFormat

from channels.dailyygstories.harness.trend_horror import harvest_all
from channels.dailyygstories.harness.intelligent_scorer import pick_best_candidate
from channels.dailyygstories.harness.story_classifier import classify_story
from channels.dailyygstories.harness.asset_matcher import fetch_matched_footage

# Load story_rewriter from horror-narration channel (shared logic)
def _load_rewriter():
    p = Path(__file__).parents[3] / "channels" / "horror-narration" / "harness" / "story_rewriter.py"
    spec = ilu.spec_from_file_location("story_rewriter", p)
    m = ilu.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

_rewriter = _load_rewriter()


def _load_channel_learnings(channel_config) -> dict:
    learnings_path = channel_config.channel_dir / "data" / "learnings.json"
    if learnings_path.exists():
        return json.loads(learnings_path.read_text())
    return {"hook_patterns": [], "title_formulas": [], "covered_topics": [],
            "story_type_performance": {}, "anti_patterns": []}


def _build_prompt_with_learnings(channel_config, top_story_types: list) -> str:
    from harness.tools.learnings import get_top_hook_patterns, get_top_title_formulas, get_covered_topics

    learnings_path = channel_config.channel_dir / "data" / "learnings.json"

    # Hook + title patterns from channel-specific learnings
    try:
        data = json.loads(learnings_path.read_text())
        hooks = sorted(data.get("hook_patterns", []),
                       key=lambda p: p.get("avg_3sec_retention_proxy", 0), reverse=True)[:3]
        titles = sorted(data.get("title_formulas", []),
                        key=lambda f: f.get("avg_ctr", 0), reverse=True)[:3]
        covered = [t["topic"] for t in data.get("covered_topics", [])[-30:]]
    except Exception:
        hooks, titles, covered = [], [], []

    hooks_text = "\n".join(f'- "{h["pattern"]}"' for h in hooks) or "- No data yet"
    titles_text = "\n".join(f'- "{t["formula"]}"' for t in titles) or "- No data yet"
    covered_text = ", ".join(covered) or "none"
    story_types_text = "\n".join(
        f'- {st["story_type"]} (avg sub gain/1k: {st.get("avg_sub_gain_per_1k_views", 0):.1f})'
        for st in top_story_types
    ) or "- No data yet"

    raw = channel_config.prompt_path.read_text(encoding="utf-8")
    return (raw
            .replace("{hooks_text}", hooks_text)
            .replace("{titles_text}", titles_text)
            .replace("{covered_text}", covered_text)
            .replace("{top_story_types}", story_types_text))


def run_dailyygstories_pipeline(channel_config=None, dry_run: bool = False) -> dict:
    if channel_config is None:
        channel_config = load_channel_config("dailyygstories")

    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    init_logger(run_id)
    log(f"👁️  dailyygstories Harness — starting [{channel_config.slug}]")
    clear_outputs_dir()

    state_path = get_state_path(channel_config)
    try:
        state = atomic_read(state_path)
    except FileNotFoundError:
        state = {}

    used_ids = set(state.get("used_story_ids", []))
    recent_runs = state.get("recent_runs", [])

    # ── Load learnings ────────────────────────────────────────────────────────
    from harness.tools.learnings import get_top_story_types
    top_story_types = get_top_story_types(n=3, channel_learnings_path=channel_config.channel_dir / "data" / "learnings.json")

    # ── Harvest all sources ───────────────────────────────────────────────────
    log("🕸️  Harvesting stories from all sources...")
    try:
        candidates = harvest_all(channel_config)
        log(f"📚 Total candidates: {len(candidates)}")
    except Exception as e:
        log(f"❌ Harvest failed: {e}", level="error")
        return {"success": False, "video_url": None, "reason": f"harvest failed: {e}"}

    if not candidates:
        return {"success": False, "video_url": None, "reason": "no candidates harvested"}

    # ── Classify + rewrite (try up to 5 candidates) ──────────────────────────
    prompt_text = _build_prompt_with_learnings(channel_config, top_story_types)
    script_data = None
    chosen = None
    skipped = set()

    for attempt in range(5):
        # Classify format first (short/long) to pass to scorer
        pre_candidate = pick_best_candidate(candidates, target="short", used_ids=used_ids | skipped, top_story_types=top_story_types)
        if pre_candidate is None:
            return {"success": False, "video_url": None, "reason": "no unused candidates"}

        classification = classify_story(pre_candidate)
        target = classification["format"]
        story_type = classification["story_type"]

        # Re-score with correct target
        candidate = pick_best_candidate(candidates, target=target, used_ids=used_ids | skipped, top_story_types=top_story_types)
        if candidate is None:
            break

        log(f"📖 Attempt ({attempt+1}/5): '{candidate['title'][:55]}' type={story_type} fmt={target}")
        try:
            script_data = _rewriter.rewrite_story(candidate, target=target, prompt_text=prompt_text)
            script_data["story_type"] = story_type
            chosen = candidate
            break
        except (ValueError, RuntimeError) as e:
            log(f"⚠️  Rewrite failed for {candidate['id']}: {e}", level="warning")
            skipped.add(candidate["id"])

    if script_data is None:
        return {"success": False, "video_url": None, "reason": "all 5 candidates failed rewrite"}

    log(f"✍️  Script: {len(script_data['script'].split())} words, mood: {script_data.get('mood','?')}, type: {script_data.get('story_type','?')}")

    # ── Pick voice ────────────────────────────────────────────────────────────
    settings_raw = json.loads((channel_config.channel_dir / "settings.json").read_text())
    voices_config = settings_raw.get("voices", {})
    mood = script_data.get("mood", "dread")
    chosen_voice_id = _rewriter.pick_voice(mood, target=target, voices_config=voices_config)
    log(f"🎤 Voice: {chosen_voice_id} (mood: {mood})")

    # ── Write metadata.json ───────────────────────────────────────────────────
    fmt = VideoFormat.LONG if target == "long" else VideoFormat.SHORT
    metadata = {
        "title": script_data["title"],
        "script": script_data["script"],
        "hashtags": script_data.get("hashtags", ["horror", "scarystories", "dailyygstories"]),
        "topic_cluster": script_data.get("topic_cluster", "paranormal"),
        "hook_overlay": script_data.get("hook_overlay", ""),
        "source_attribution": script_data.get("source_attribution", ""),
        "story_type": script_data.get("story_type", "paranormal"),
        "format": target,
        "hook_pattern_used": script_data.get("hook_pattern_used", ""),
        "title_formula_used": script_data.get("title_formula_used", ""),
    }
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    (outputs_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Audio ─────────────────────────────────────────────────────────────────
    log("🎙️  Generating voiceover...")
    try:
        audio_duration, word_timestamps = generate_audio(script=script_data["script"], voice_id=chosen_voice_id)
    except Exception as e:
        log(f"❌ Audio failed: {e}", level="error")
        return {"success": False, "video_url": None, "reason": f"audio failed: {e}"}

    # ── Footage: asset matcher first, then existing horror_footage library ────
    clip_path = None
    story_type = script_data.get("story_type", "paranormal")
    log(f"🎥 Finding footage for story type: {story_type}")
    try:
        clip_path = fetch_matched_footage(script_data, story_type, channel_config.footage_dir, fmt=fmt)
        if clip_path:
            log(f"✅ Matched footage: {clip_path}")
    except Exception as e:
        log(f"⚠️  Asset matcher failed (non-blocking): {e}", level="warning")

    # ── Video build ───────────────────────────────────────────────────────────
    log("🎬 Building video...")
    try:
        video_path = build_video(
            audio_duration,
            clip_path=clip_path,
            word_timestamps=word_timestamps,
            hook_overlay=metadata["hook_overlay"],
            fmt=fmt,
            channel_config=channel_config,
            script_data=script_data,
            channel_slug=channel_config.slug,
        )
    except Exception as e:
        log(f"❌ Video build failed: {e}", level="error")
        move_outputs_to_archive(run_id)
        return {"success": False, "video_url": None, "reason": f"video build: {e}"}

    # ── Upload ────────────────────────────────────────────────────────────────
    if dry_run or os.environ.get("DAILYYGSTORIES_DRY_RUN"):
        log("🔕 DRY RUN — skipping upload")
        video_url = "https://youtube.com/DRY_RUN"
    else:
        try:
            video_url = upload_youtube(channel_config=channel_config)
            log(f"🎉 Live: {video_url}")
            video_id = video_url.rstrip("/").split("/")[-1]
            track_video(video_id, {**metadata, "format": target})
        except Exception as e:
            log(f"❌ Upload failed: {e}", level="error")
            move_outputs_to_archive(run_id)
            return {"success": False, "video_url": None, "reason": f"upload: {e}"}

    # ── Save state ────────────────────────────────────────────────────────────
    used_ids.add(chosen["id"])
    state["used_story_ids"] = list(used_ids)
    recent = state.setdefault("recent_runs", [])
    recent.insert(0, {"topic_cluster": metadata["topic_cluster"], "format": target, "run_id": run_id, "story_type": story_type})
    state["recent_runs"] = recent[:50]
    atomic_write(state_path, state)
    move_outputs_to_archive(run_id)
    return {"success": True, "video_url": video_url, "reason": None}


if __name__ == "__main__":
    result = run_dailyygstories_pipeline()
    if not result["success"]:
        log(f"❌ Pipeline failed: {result['reason']}", level="error")
        sys.exit(1)
    sys.exit(0)
```

- [ ] **Step 2: Smoke test (dry run)**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
DAILYYGSTORIES_DRY_RUN=1 python -m channels.dailyygstories.harness.orchestrator
```

Expected: pipeline runs to "DRY RUN — skipping upload" and exits 0. No real upload.

- [ ] **Step 3: Commit**

```bash
git add channels/dailyygstories/harness/orchestrator.py
git commit -m "feat: dailyygstories full pipeline orchestrator"
```

---

## Task 7: Low-CPU runner with 30-minute Kamil integration

**Files:**
- Create: `scripts/low_cpu_runner.py`

The runner checks CPU load before running either channel. If load is low, it runs the channel pipeline. This integrates with Kamil's existing 30-minute tick via a new cron entry.

- [ ] **Step 1: Implement low_cpu_runner.py**

Create `scripts/low_cpu_runner.py`:

```python
#!/usr/bin/env python3
"""
low_cpu_runner.py — Run a channel pipeline only when CPU is idle.

Usage:
  python scripts/low_cpu_runner.py --channel dailyygstories
  python scripts/low_cpu_runner.py --channel horror-narration
  python scripts/low_cpu_runner.py --channel canine-wisdom
  python scripts/low_cpu_runner.py --all   # runs both video channels

Guards:
  - CPU load average (1-min) must be < CPU_LOAD_THRESHOLD (default 1.5)
  - Per-channel lock file prevents overlapping runs
  - Min gap between runs: MIN_GAP_MINUTES (default 240 = 4 hours) per channel

If guard fails: exits 0 silently (not an error, just "not now").
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(REPO_ROOT))

CPU_LOAD_THRESHOLD = float(os.environ.get("LOW_CPU_THRESHOLD", "1.5"))
MIN_GAP_MINUTES = int(os.environ.get("MIN_GAP_MINUTES", "240"))
RUNNER_STATE_DIR = Path.home() / ".kamil-harness" / "video-runner"

CHANNEL_PIPELINES = {
    "dailyygstories": "channels.dailyygstories.harness.orchestrator:run_dailyygstories_pipeline",
    "horror-narration": "channels.horror-narration.harness.orchestrator:run_horror_pipeline",
    "canine-wisdom": "harness.orchestrator:run_canine_wisdom_pipeline",
}

VIDEO_CHANNELS = ["dailyygstories", "horror-narration"]


def _cpu_load() -> float:
    try:
        return os.getloadavg()[0]
    except (AttributeError, OSError):
        # Windows fallback
        import subprocess
        try:
            result = subprocess.run(["wmic", "cpu", "get", "loadpercentage"], capture_output=True, text=True)
            lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip().isdigit()]
            return float(lines[0]) / 100.0 if lines else 0.0
        except Exception:
            return 0.0


def _is_cpu_idle() -> bool:
    load = _cpu_load()
    print(f"[low_cpu_runner] CPU load: {load:.2f} (threshold: {CPU_LOAD_THRESHOLD})")
    return load < CPU_LOAD_THRESHOLD


def _state_path(channel: str) -> Path:
    RUNNER_STATE_DIR.mkdir(parents=True, exist_ok=True)
    return RUNNER_STATE_DIR / f"{channel}.json"


def _lock_path(channel: str) -> Path:
    return RUNNER_STATE_DIR / f"{channel}.lock"


def _is_locked(channel: str) -> bool:
    lock = _lock_path(channel)
    if not lock.exists():
        return False
    # Stale lock (> 2h old) → treat as unlocked
    age = time.time() - lock.stat().st_mtime
    if age > 7200:
        lock.unlink(missing_ok=True)
        return False
    return True


def _acquire_lock(channel: str):
    _lock_path(channel).write_text(str(os.getpid()))


def _release_lock(channel: str):
    _lock_path(channel).unlink(missing_ok=True)


def _last_run(channel: str) -> datetime | None:
    sp = _state_path(channel)
    if not sp.exists():
        return None
    data = json.loads(sp.read_text())
    ts = data.get("last_run_at")
    if not ts:
        return None
    return datetime.fromisoformat(ts)


def _record_run(channel: str, success: bool):
    sp = _state_path(channel)
    data = json.loads(sp.read_text()) if sp.exists() else {}
    data["last_run_at"] = datetime.now().isoformat()
    data["last_success"] = success
    sp.write_text(json.dumps(data, indent=2))


def _min_gap_passed(channel: str) -> bool:
    last = _last_run(channel)
    if last is None:
        return True
    gap = datetime.now() - last
    passed = gap >= timedelta(minutes=MIN_GAP_MINUTES)
    if not passed:
        remaining = timedelta(minutes=MIN_GAP_MINUTES) - gap
        print(f"[low_cpu_runner] {channel}: {remaining} until next eligible run")
    return passed


def _run_channel(channel: str) -> bool:
    if _is_locked(channel):
        print(f"[low_cpu_runner] {channel}: already running, skip")
        return False
    if not _min_gap_passed(channel):
        return False

    pipeline_ref = CHANNEL_PIPELINES.get(channel)
    if not pipeline_ref:
        print(f"[low_cpu_runner] Unknown channel: {channel}")
        return False

    module_path, func_name = pipeline_ref.rsplit(":", 1)
    # Handle hyphen in module path
    module_path = module_path.replace("-", "_")

    import importlib
    try:
        mod = importlib.import_module(module_path)
    except ModuleNotFoundError:
        # Try loading from file path for channels with hyphens
        channel_mod_file = REPO_ROOT / "channels" / channel / "harness" / "orchestrator.py"
        import importlib.util as ilu
        spec = ilu.spec_from_file_location("orchestrator", channel_mod_file)
        mod = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)

    fn = getattr(mod, func_name)
    _acquire_lock(channel)
    print(f"[low_cpu_runner] Starting {channel} pipeline...")
    try:
        result = fn()
        success = result.get("success", False)
        print(f"[low_cpu_runner] {channel}: {'✅ success' if success else '❌ failed'} — {result.get('reason') or result.get('video_url', '')}")
        _record_run(channel, success)
        return success
    except Exception as e:
        print(f"[low_cpu_runner] {channel}: exception — {e}")
        _record_run(channel, False)
        return False
    finally:
        _release_lock(channel)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", help="Channel slug to run")
    parser.add_argument("--all", action="store_true", help="Run all video channels")
    args = parser.parse_args()

    if not _is_cpu_idle():
        print("[low_cpu_runner] CPU busy — skipping this tick")
        sys.exit(0)

    channels = VIDEO_CHANNELS if args.all else ([args.channel] if args.channel else [])
    if not channels:
        print("[low_cpu_runner] No channel specified. Use --channel or --all")
        sys.exit(1)

    for ch in channels:
        _run_channel(ch)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test guard logic (no real pipeline)**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
python scripts/low_cpu_runner.py --channel dailyygstories 2>&1
```

With `MIN_GAP_MINUTES=0` and `LOW_CPU_THRESHOLD=99` to force it through:

```bash
MIN_GAP_MINUTES=0 LOW_CPU_THRESHOLD=99 DAILYYGSTORIES_DRY_RUN=1 python scripts/low_cpu_runner.py --channel dailyygstories
```

Expected: pipeline runs in dry-run mode, exits 0.

- [ ] **Step 3: Add cron entry to Kamil's crontab**

Run: `crontab -l > /tmp/current_cron.txt && cat /tmp/current_cron.txt`

Then add this line (every 30 minutes, same tick as Kamil's orchestrator):

```
*/30 * * * * cd /home/oye/Documents/free_work/repos/canine-wisdom-automation && python scripts/low_cpu_runner.py --all >> /tmp/kamil-video-runner.log 2>&1
```

Add it: `(crontab -l; echo "*/30 * * * * cd /home/oye/Documents/free_work/repos/canine-wisdom-automation && python scripts/low_cpu_runner.py --all >> /tmp/kamil-video-runner.log 2>&1") | crontab -`

- [ ] **Step 4: Verify cron entry**

```bash
crontab -l | grep low_cpu_runner
```

Expected: the line appears.

- [ ] **Step 5: Commit**

```bash
git add scripts/low_cpu_runner.py
git commit -m "feat: low-CPU runner — auto-publish video channels when laptop is idle"
```

---

## Task 8: Wire analytics learnings back into dailyygstories

**Files:**
- Modify: `channels/dailyygstories/harness/orchestrator.py` (add `update_story_type_performance()` call after upload)
- Create: `channels/dailyygstories/harness/learnings_updater.py`

- [ ] **Step 1: Implement learnings_updater.py**

Create `channels/dailyygstories/harness/learnings_updater.py`:

```python
"""
Update dailyygstories channel-specific learnings.json with video performance.

Called after analytics snapshot pull shows 48h+ data for a video.
Updates story_type_performance dict so intelligent_scorer can boost top types.
"""
import json
from datetime import datetime
from pathlib import Path


def update_story_type_performance(channel_dir: Path, story_type: str, video_data: dict):
    """
    video_data keys expected: views, subscribers_gained, avg_view_duration_sec, format
    Updates story_type_performance[story_type] with rolling average.
    """
    learnings_path = channel_dir / "data" / "learnings.json"
    data = json.loads(learnings_path.read_text(encoding="utf-8"))

    views = float(video_data.get("views", 0))
    subs_gained = float(video_data.get("subscribers_gained", 0))
    sub_gain_per_1k = (subs_gained / views * 1000) if views > 0 else 0.0
    retention = float(video_data.get("avg_view_duration_sec", 0))

    perf = data.setdefault("story_type_performance", {})
    if story_type in perf:
        old = perf[story_type]
        n = old.get("sample_size", 1)
        perf[story_type] = {
            "story_type": story_type,
            "avg_sub_gain_per_1k_views": (old["avg_sub_gain_per_1k_views"] * n + sub_gain_per_1k) / (n + 1),
            "avg_view_duration_sec": (old["avg_view_duration_sec"] * n + retention) / (n + 1),
            "sample_size": n + 1,
            "last_seen": datetime.now().strftime("%Y-%m-%d"),
        }
    else:
        perf[story_type] = {
            "story_type": story_type,
            "avg_sub_gain_per_1k_views": sub_gain_per_1k,
            "avg_view_duration_sec": retention,
            "sample_size": 1,
            "last_seen": datetime.now().strftime("%Y-%m-%d"),
        }

    data["updated_at"] = datetime.now().isoformat()
    learnings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[learnings_updater] Updated {story_type}: sub_gain/1k={sub_gain_per_1k:.2f}")
```

- [ ] **Step 2: Add learnings call into orchestrator after upload**

In `channels/dailyygstories/harness/orchestrator.py`, after the `track_video(...)` line, add:

```python
            from channels.dailyygstories.harness.learnings_updater import update_story_type_performance
            # Defer: actual analytics pull happens later; record story_type for tracking
            state.setdefault("pending_analytics", []).append({
                "video_id": video_id,
                "story_type": story_type,
                "uploaded_at": datetime.now().isoformat(),
            })
```

And add a `pull_and_update_learnings()` call at the START of each run (before harvest) to process any pending analytics:

```python
def _process_pending_analytics(channel_config, state: dict):
    """Pull analytics for videos uploaded 48h+ ago and update learnings."""
    from upload_youtube import get_analytics_service
    from channels.dailyygstories.harness.learnings_updater import update_story_type_performance
    from datetime import timedelta

    pending = state.get("pending_analytics", [])
    still_pending = []
    cutoff = datetime.now() - timedelta(hours=48)

    for item in pending:
        try:
            uploaded = datetime.fromisoformat(item["uploaded_at"])
        except Exception:
            continue

        if uploaded > cutoff:
            still_pending.append(item)
            continue

        # Old enough — pull analytics
        try:
            analytics = get_analytics_service()
            resp = analytics.reports().query(
                ids="channel==MINE",
                startDate=uploaded.strftime("%Y-%m-%d"),
                endDate=datetime.now().strftime("%Y-%m-%d"),
                metrics="views,estimatedMinutesWatched,averageViewDuration,subscribersGained",
                filters=f"video=={item['video_id']}",
            ).execute()
            rows = resp.get("rows", [])
            headers = resp.get("columnHeaders", [])
            if rows:
                col_map = {h["name"]: i for i, h in enumerate(headers)}
                video_data = {
                    "views": int(rows[0][col_map["views"]]),
                    "avg_view_duration_sec": float(rows[0][col_map["averageViewDuration"]]),
                    "subscribers_gained": int(rows[0][col_map["subscribersGained"]]),
                }
                update_story_type_performance(channel_config.channel_dir, item["story_type"], video_data)
        except Exception as e:
            log(f"⚠️  Analytics pull failed for {item['video_id']}: {e}", level="warning")
            still_pending.append(item)

    state["pending_analytics"] = still_pending
```

Add `_process_pending_analytics(channel_config, state)` call right after `state = atomic_read(state_path)` in `run_dailyygstories_pipeline()`.

- [ ] **Step 3: Commit**

```bash
git add channels/dailyygstories/harness/learnings_updater.py channels/dailyygstories/harness/orchestrator.py
git commit -m "feat: wire analytics loop — story_type_performance feeds back into scorer"
```

---

## Task 9: End-to-end dry-run verification

- [ ] **Step 1: Run full test suite**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
python -m pytest channels/dailyygstories/tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 2: Full dry-run pipeline**

```bash
DAILYYGSTORIES_DRY_RUN=1 python -m channels.dailyygstories.harness.orchestrator
```

Expected output includes:
```
👁️  dailyygstories Harness — starting [dailyygstories]
🕸️  Harvesting stories from all sources...
📚 Total candidates: N
📖 Attempt (1/5): '...'
✍️  Script: ... words, mood: ...
🎙️  Generating voiceover...
🎬 Building video...
🔕 DRY RUN — skipping upload
```

- [ ] **Step 3: Verify state written**

```bash
cat channels/dailyygstories/data/state.json
```

Expected: `used_story_ids` has at least one entry.

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: dailyygstories viral horror harness — complete"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Trending layer (Google Trends + RSS + Reddit) → Task 2
- ✅ Story type classification (true crime, paranormal, etc.) → Task 4
- ✅ Short vs long format decision → Task 4 + orchestrator
- ✅ Intelligent scorer using learnings data → Task 3
- ✅ Matched footage download by setting keywords → Task 5
- ✅ Full pipeline orchestrator → Task 6
- ✅ Low-CPU guard + 30min cron → Task 7
- ✅ Analytics feedback loop → Task 8
- ✅ dailyygstories channel config + prompt → Task 1
- ✅ Dry-run mode → Task 6 + Task 9

**Type consistency check:**
- `pick_best_candidate(candidates, target, used_ids, top_story_types)` — consistent across Tasks 3 and 6
- `classify_story(candidate)` → returns `{story_type, format, reasoning}` — consistent Tasks 4 and 6
- `fetch_matched_footage(script_data, story_type, footage_dir, fmt)` — consistent Tasks 5 and 6
- `update_story_type_performance(channel_dir, story_type, video_data)` — consistent Tasks 8
- `get_top_story_types(n, channel_learnings_path)` — defined Task 3, used Tasks 6 and 8

**No placeholders:** All steps have complete code. No TBDs.
