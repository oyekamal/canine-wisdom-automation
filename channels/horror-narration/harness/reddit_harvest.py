"""
Harvest horror stories from Reddit using PullPush API (no credentials needed).
Reddit's public JSON endpoints now return 403 — PullPush is the reliable alternative.
"""
import time
import requests
from pathlib import Path


# PullPush is a community-maintained Pushshift mirror — free, no auth required
PULLPUSH_BASE = "https://api.pullpush.io/reddit/search/submission"
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
    Fetch top posts from a subreddit via PullPush API.
    No credentials required.

    Returns list of story dicts with keys:
        id, title, text, author, subreddit, score, num_comments, permalink, url, word_count
    """
    if opt_out_authors is None:
        opt_out_authors = []

    params = {
        "subreddit": subreddit_name,
        "sort": "score",
        "sort_type": "score",
        "size": min(limit, 100),
    }

    try:
        resp = requests.get(PULLPUSH_BASE, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        posts = resp.json().get("data", [])
    except Exception as e:
        return []

    stories = []
    for d in posts:
        # PullPush returns fields directly (no nested "data" key)
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

        post_id = d.get("id", "")
        permalink = d.get("permalink", f"/r/{subreddit_name}/comments/{post_id}/")
        stories.append({
            "id": post_id,
            "title": d.get("title", ""),
            "text": text,
            "author": author,
            "subreddit": subreddit_name,
            "score": d.get("score", 0),
            "num_comments": d.get("num_comments", 0),
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
