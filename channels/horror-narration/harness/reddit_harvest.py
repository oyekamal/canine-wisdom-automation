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


# ── Media detection and download ─────────────────────────────────────────────

IMAGE_DOMAINS = {"i.redd.it", "i.imgur.com", "preview.redd.it"}
VIDEO_DOMAINS = {"v.redd.it"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
IMAGE_HINTS = {"image"}
VIDEO_HINTS = {"hosted:video"}


def _detect_media(post: dict) -> dict | None:
    """
    Detect whether a Reddit post has attached image or video media.

    Returns {"type": "image"|"video", "url": str} or None.
    Returns None for text posts and unsupported external links.
    """
    url = post.get("url", "")
    domain = post.get("domain", "")
    hint = post.get("post_hint", "")
    is_video = post.get("is_video", False)

    # Reddit-hosted video
    if domain in VIDEO_DOMAINS:
        return {"type": "video", "url": url}

    # Direct image from Reddit or Imgur
    if domain in IMAGE_DOMAINS:
        return {"type": "image", "url": url}

    # URL ends in an image extension
    from pathlib import Path as _Path
    url_clean = url.split("?")[0]
    if _Path(url_clean).suffix.lower() in IMAGE_EXTENSIONS:
        return {"type": "image", "url": url}

    # post_hint says image and not a self-post
    if hint in IMAGE_HINTS and not domain.startswith("self."):
        return {"type": "image", "url": url}

    return None


def _download_reddit_image(url: str, output_path) -> bool:
    """Download a direct image URL. Returns True on success."""
    try:
        r = requests.get(url, timeout=20, headers=HEADERS, stream=True)
        r.raise_for_status()
        content = r.content
        if len(content) < 1000:
            return False
        from pathlib import Path as _Path
        _Path(output_path).write_bytes(content)
        return True
    except Exception:
        return False


def _download_reddit_video(url: str, output_path) -> bool:
    """
    Download a Reddit-hosted video (v.redd.it) using yt-dlp.
    These have separate video+audio streams that yt-dlp merges.
    Returns True on success.
    """
    import subprocess
    from pathlib import Path as _Path
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--quiet",
                "--no-warnings",
                "-f", "bestvideo[height<=1920]+bestaudio/best[height<=1920]",
                "--merge-output-format", "mp4",
                "-o", str(output_path),
                url,
            ],
            capture_output=True, text=True, timeout=120,
        )
        return result.returncode == 0 and _Path(output_path).exists()
    except Exception:
        return False


def extract_media(post: dict, save_dir, story_id: str) -> str | None:
    """
    If the Reddit post has attached media, download it into save_dir.

    For images: saves as {story_id}_reddit_media.jpg (or original ext)
    For videos: saves as {story_id}_reddit_media.mp4

    Returns path to downloaded file as str, or None if no media or download fails.
    """
    from pathlib import Path as _Path
    media = _detect_media(post)
    if media is None:
        return None

    save_dir = _Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)

    if media["type"] == "image":
        ext = _Path(media["url"].split("?")[0]).suffix.lower()
        if ext not in IMAGE_EXTENSIONS:
            ext = ".jpg"
        output_path = save_dir / f"{story_id}_reddit_media{ext}"
        if output_path.exists():
            return str(output_path)
        return str(output_path) if _download_reddit_image(media["url"], output_path) else None

    elif media["type"] == "video":
        output_path = save_dir / f"{story_id}_reddit_media.mp4"
        if output_path.exists():
            return str(output_path)
        return str(output_path) if _download_reddit_video(media["url"], output_path) else None

    return None
