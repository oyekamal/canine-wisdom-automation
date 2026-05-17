"""
Competitor Intel Agent.

Daily: refresh top-20 videos per tracked channel if >24h stale.
Weekly: deep scan with Whisper fallback + learnings update.
Monthly: re-rank and discover new channels.
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import requests
from anthropic import Anthropic
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

from harness.storage import atomic_write, DATA_DIR
from harness.tools.learnings import update_from_competitor, bootstrap_from_competitors
from upload_youtube import get_youtube_service

SEED_KEYWORDS = ["dog facts", "dog training tips", "dog breed comparison", "cute dog videos"]
MAX_COMPETITORS = 5
DAILY_TTL_HOURS = 24
VIDEOS_PER_CHANNEL = 20


def extract_hook(transcript_text: str) -> str:
    """Return first 15 words of transcript as the hook."""
    if not transcript_text:
        return ""
    words = transcript_text.split()[:15]
    return " ".join(words)


def compute_engagement(views: int, likes: int, comments: int, subscriber_count: int) -> dict:
    """Compute engagement ratios safely (no division by zero)."""
    return {
        "views_per_sub": views / subscriber_count if subscriber_count else 0.0,
        "like_rate": likes / views if views else 0.0,
        "comment_rate": comments / views if views else 0.0,
    }


def should_refresh(channel_json_path: Path, max_age_hours: int = DAILY_TTL_HOURS) -> bool:
    """Return True if channel data is missing or older than max_age_hours."""
    if not channel_json_path.exists():
        return True
    data = json.loads(channel_json_path.read_text())
    last = data.get("last_scanned")
    if not last:
        return True
    return datetime.now() - datetime.fromisoformat(last) > timedelta(hours=max_age_hours)


def _score_channel(sub_count: int, avg_views: float, video_count: int, niche_score: float) -> float:
    """Compute ranking score for a candidate channel."""
    upload_velocity = min(video_count / 30, 10)
    return (sub_count * 0.3) + (avg_views * 0.4) + (upload_velocity * 0.2) + (niche_score * 0.1)


def _batch_niche_scores(candidates: list) -> dict:
    """
    Score all candidate channels' niche match in a single Anthropic call.
    Returns dict mapping channel_id -> float score (0.0–1.0).
    """
    if not candidates:
        return {}

    lines = []
    for i, c in enumerate(candidates):
        lines.append(f'{i+1}. ID={c["channel_id"]} Title="{c.get("title","")}" Desc="{c.get("description","")[:100]}"')

    prompt = (
        "Rate each YouTube channel 0.0–1.0 on how closely it matches the dog-facts Shorts niche.\n"
        "Channels:\n" + "\n".join(lines) + "\n\n"
        'Respond ONLY with JSON: {"scores": {"<channel_id>": <float>, ...}}'
    )

    try:
        client = Anthropic()
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        if text.startswith("```"):
            text = "\n".join(text.splitlines()[1:-1])
        data = json.loads(text)
        return {k: float(v) for k, v in data.get("scores", {}).items()}
    except Exception:
        return {c["channel_id"]: 0.5 for c in candidates}


def discover_channels(youtube, seeds: list = None) -> list:
    """
    Search YouTube for top dog-niche channels.
    Returns list of dicts with channel_id, channel_name, ranking_score.
    """
    seeds = seeds or SEED_KEYWORDS
    seen_ids = set()
    candidates = []

    for keyword in seeds:
        resp = youtube.search().list(
            q=keyword, part="snippet", type="channel", maxResults=10
        ).execute()
        for item in resp.get("items", []):
            cid = item["snippet"]["channelId"]
            if cid not in seen_ids:
                seen_ids.add(cid)
                candidates.append({
                    "channel_id": cid,
                    "channel_name": item["snippet"]["channelTitle"],
                })

    all_ids = [c["channel_id"] for c in candidates]
    if not all_ids:
        return []

    stats_resp = youtube.channels().list(
        id=",".join(all_ids), part="snippet,statistics"
    ).execute()
    stats_map = {i["id"]: i for i in stats_resp.get("items", [])}

    # Build candidate info list for batch niche scoring
    candidate_info = []
    for c in candidates:
        info = stats_map.get(c["channel_id"])
        if not info:
            continue
        snippet = info.get("snippet", {})
        candidate_info.append({
            "channel_id": c["channel_id"],
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
        })

    niche_scores = _batch_niche_scores(candidate_info)

    scored = []
    for c in candidates:
        info = stats_map.get(c["channel_id"])
        if not info:
            continue
        stats = info.get("statistics", {})
        snippet = info.get("snippet", {})
        sub_count = int(stats.get("subscriberCount", 0))
        video_count = int(stats.get("videoCount", 0))

        # Get avg_views from a quick search (last 10 uploads)
        try:
            search_resp = youtube.search().list(
                channelId=c["channel_id"], part="id", type="video",
                order="date", maxResults=10
            ).execute()
            video_ids = [i["id"]["videoId"] for i in search_resp.get("items", []) if "videoId" in i.get("id", {})]
            avg_views = 0.0
            if video_ids:
                vresp = youtube.videos().list(id=",".join(video_ids), part="statistics").execute()
                view_counts = [int(v["statistics"].get("viewCount", 0)) for v in vresp.get("items", [])]
                avg_views = sum(view_counts) / len(view_counts) if view_counts else 0.0
        except Exception:
            avg_views = 0.0

        niche_score = niche_scores.get(c["channel_id"], 0.5)
        score = _score_channel(sub_count, avg_views, video_count, niche_score)
        scored.append({
            "channel_id": c["channel_id"],
            "channel_name": snippet.get("title", ""),
            "subscriber_count": sub_count,
            "ranking_score": score,
            "discovered_at": datetime.now().isoformat(),
        })

    scored.sort(key=lambda x: x["ranking_score"], reverse=True)
    return scored[:MAX_COMPETITORS]


def refresh_channel(youtube, channel_id: str, subscriber_count: int) -> dict:
    """
    Pull top VIDEOS_PER_CHANNEL videos from the last 7 days for a channel.
    Downloads thumbnails, fetches transcripts, computes engagement.
    Returns summary dict with videos_pulled count.
    """
    channel_dir = DATA_DIR / "competitors" / channel_id
    videos_dir = channel_dir / "videos"
    thumbs_dir = channel_dir / "thumbnails"
    trans_dir = channel_dir / "transcripts"
    for d in [videos_dir, thumbs_dir, trans_dir]:
        d.mkdir(parents=True, exist_ok=True)

    since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    search_resp = youtube.search().list(
        channelId=channel_id, part="id", type="video",
        order="viewCount", publishedAfter=since, maxResults=VIDEOS_PER_CHANNEL,
    ).execute()
    video_ids = [
        i["id"]["videoId"] for i in search_resp.get("items", [])
        if "videoId" in i.get("id", {})
    ]

    if not video_ids:
        return {"videos_pulled": 0, "video_data": []}

    videos_resp = youtube.videos().list(
        id=",".join(video_ids),
        part="snippet,statistics,contentDetails",
    ).execute()

    pulled = 0
    all_video_data = []
    for item in videos_resp.get("items", []):
        vid_id = item["id"]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})

        views = int(stats.get("viewCount", 0))
        likes = int(stats.get("likeCount", 0))
        comments = int(stats.get("commentCount", 0))
        engagement = compute_engagement(views, likes, comments, subscriber_count)

        transcript_text = ""
        transcript_status = "unavailable"
        try:
            segments = YouTubeTranscriptApi.get_transcript(vid_id)
            transcript_text = " ".join(s["text"] for s in segments)
            transcript_status = "available"
            (trans_dir / f"{vid_id}.txt").write_text(transcript_text, encoding="utf-8")
        except (TranscriptsDisabled, NoTranscriptFound):
            pass
        except Exception as e:
            # Unexpected error — log but don't halt the pipeline
            print(f"[competitor] transcript fetch unexpected error for {vid_id}: {e}")

        hook = extract_hook(transcript_text)

        thumb_url = snippet.get("thumbnails", {}).get("high", {}).get("url", "")
        thumb_path = ""
        if thumb_url:
            try:
                r = requests.get(thumb_url, timeout=10)
                if r.status_code == 200:
                    thumb_file = thumbs_dir / f"{vid_id}.jpg"
                    thumb_file.write_bytes(r.content)
                    thumb_path = str(thumb_file.relative_to(DATA_DIR))
            except Exception:
                pass

        published_at = snippet.get("publishedAt", "")
        try:
            pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            publish_hour_utc = pub_dt.hour
            publish_dow = pub_dt.strftime("%a")
        except Exception:
            publish_hour_utc = 0
            publish_dow = "Mon"

        video_data = {
            "video_id": vid_id,
            "channel_id": channel_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", "")[:500],
            "tags": snippet.get("tags", []),
            "published_at": published_at,
            "publish_hour_utc": publish_hour_utc,
            "publish_dow": publish_dow,
            "thumbnail_path": thumb_path,
            "transcript_status": transcript_status,
            "hook": hook,
            "view_count": views,
            "like_count": likes,
            "comment_count": comments,
            **engagement,
            "scraped_at": datetime.now().isoformat(),
        }

        atomic_write(videos_dir / f"{vid_id}.json", video_data)
        all_video_data.append(video_data)
        pulled += 1

    ch_file = channel_dir / "channel.json"
    ch_data = json.loads(ch_file.read_text()) if ch_file.exists() else {"channel_id": channel_id}
    ch_data["last_scanned"] = datetime.now().isoformat()
    atomic_write(ch_file, ch_data)

    return {"videos_pulled": pulled, "video_data": all_video_data}


def run_daily_refresh(channel_ids: list = None) -> dict:
    """
    Refresh all tracked channels if >24h stale.
    channel_ids: override list (used in tests). Defaults to state.json competitor_channels.
    """
    if channel_ids is None:
        from harness.storage import atomic_read, STATE_PATH
        state = atomic_read(STATE_PATH)
        channel_ids = state.get("competitor_channels", [])

    youtube = get_youtube_service()
    results = {}
    all_videos = []

    for cid in channel_ids:
        ch_file = DATA_DIR / "competitors" / cid / "channel.json"
        if not should_refresh(ch_file):
            results[cid] = "skipped (fresh)"
            continue

        ch_data = json.loads(ch_file.read_text()) if ch_file.exists() else {}
        sub_count = ch_data.get("subscriber_count", 0)
        summary = refresh_channel(youtube, cid, sub_count)
        results[cid] = f"pulled {summary['videos_pulled']} videos"
        all_videos.extend(summary.get("video_data", []))

    if all_videos:
        update_from_competitor("__daily__", all_videos)

    return results
