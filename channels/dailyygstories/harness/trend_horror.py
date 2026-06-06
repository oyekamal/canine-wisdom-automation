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

try:
    from pytrends.request import TrendReq
except ImportError:
    TrendReq = None

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
        if TrendReq is None:
            raise ImportError("pytrends not installed")
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

    settings = json.loads((channel_config.channel_dir / "settings.json").read_text())
    rss_urls = settings.get("news_rss_feeds", [])
    trend_kws = settings.get("google_trends_keywords", ["horror story"])

    all_candidates = []

    print("[trend_horror] Fetching news RSS...")
    news = harvest_news(rss_urls)
    print(f"[trend_horror] News: {len(news)} horror-signal items")
    all_candidates.extend(news)

    print("[trend_horror] Fetching Google Trends...")
    trends = harvest_trends(trend_kws, geo="PK")
    print(f"[trend_horror] Trends: {len(trends)} rising queries")
    all_candidates.extend(trends)

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
