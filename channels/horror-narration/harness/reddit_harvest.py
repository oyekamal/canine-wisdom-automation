"""
Harvest horror stories from Reddit using public JSON endpoints.
No API key or credentials needed — uses Reddit's public .json feed.
"""
import time
import requests
from pathlib import Path


REDDIT_BASE = "https://www.reddit.com"
HEADERS = {"User-Agent": "horror_harness/1.0"}


def harvest_subreddit(
    subreddit_name: str,
    limit: int = 25,
    time_filter: str = "week",
    min_upvotes: int = 100,
    min_comments: int = 10,
    opt_out_authors: list = None,
) -> list:
    """
    Fetch top posts from a subreddit via Reddit's public JSON API.
    No credentials required.

    Returns list of story dicts with keys:
        id, title, text, author, subreddit, score, num_comments, permalink, url, word_count
    """
    if opt_out_authors is None:
        opt_out_authors = []

    url = f"{REDDIT_BASE}/r/{subreddit_name}/top.json"
    params = {"limit": limit, "t": time_filter}

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        posts = resp.json()["data"]["children"]
    except Exception as e:
        return []

    stories = []
    for post in posts:
        d = post["data"]

        author = d.get("author", "")
        if not author or author in ("[deleted]", "[removed]", "AutoModerator"):
            continue
        if author in opt_out_authors:
            continue
        if d.get("score", 0) < min_upvotes:
            continue
        if d.get("num_comments", 0) < min_comments:
            continue

        text = d.get("selftext", "").strip()
        if not text or text in ("[deleted]", "[removed]"):
            continue

        permalink = d.get("permalink", "")
        stories.append({
            "id": d["id"],
            "title": d["title"],
            "text": text,
            "author": author,
            "subreddit": subreddit_name,
            "score": d["score"],
            "num_comments": d["num_comments"],
            "permalink": permalink,
            "url": f"{REDDIT_BASE}{permalink}",
            "word_count": len(text.split()),
        })

    return stories


def harvest_channel(channel_config) -> list:
    """
    Harvest stories for all subreddits in the channel's settings.
    Returns deduplicated list ordered by score descending.
    """
    import json
    settings = json.loads((channel_config.channel_dir / "settings.json").read_text())
    subreddits = (
        settings.get("subreddits", {}).get("primary", []) +
        settings.get("subreddits", {}).get("secondary", [])
    )
    min_upvotes = settings.get("min_upvotes", 100)
    min_comments = settings.get("min_comments", 10)
    opt_out = settings.get("opt_out_authors", [])

    seen_ids = set()
    all_stories = []
    for sub in subreddits:
        for story in harvest_subreddit(
            sub,
            min_upvotes=min_upvotes,
            min_comments=min_comments,
            opt_out_authors=opt_out,
        ):
            if story["id"] not in seen_ids:
                seen_ids.add(story["id"])
                all_stories.append(story)
        time.sleep(0.5)  # be polite to Reddit

    all_stories.sort(key=lambda s: s["score"], reverse=True)
    return all_stories
