"""
Footage sourcing tool.
Primary: Pexels API (portrait dog clips, free tier).
Fallback: yt-dlp Creative Commons YouTube search.
Downloads clips to dog_footage/ so build_video.py picks them up automatically.
"""
import json
import os
import random
import subprocess
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent.parent
DOG_FOOTAGE_DIR = BASE_DIR / "dog_footage"
FOOTAGE_INDEX = BASE_DIR / "harness" / "data" / "footage_index.json"

# Topic → Pexels search queries mapping
# When the script topic matches a cluster, we use more specific search terms
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

DEFAULT_QUERIES = ["dog portrait", "puppy close up", "cute dog", "dog face"]


def _load_api_key() -> str:
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    key = os.getenv("PEXELS_API_KEY", "")
    if not key:
        raise ValueError("PEXELS_API_KEY not set in .env")
    return key


def _search_pexels(query: str, api_key: str, per_page: int = 15) -> list:
    """Search Pexels for portrait dog videos. Returns list of clip dicts."""
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "orientation": "portrait",
        "size": "medium",
        "per_page": per_page,
    }
    try:
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
    except Exception as e:
        print(f"[footage] Pexels search failed for '{query}': {e}")
        return []

    results = []
    for video in videos:
        if video.get("duration", 0) < 8:
            continue  # too short for a 15-30s script
        # Find best portrait file (height > width, highest resolution)
        portrait_files = [
            f for f in video.get("video_files", [])
            if f.get("height", 0) > f.get("width", 0) and f.get("height", 0) >= 720
        ]
        if not portrait_files:
            # Accept any file — we'll crop in ffmpeg
            all_files = [f for f in video.get("video_files", []) if f.get("height", 0) >= 720]
            if not all_files:
                continue
            portrait_files = all_files
        best = sorted(portrait_files, key=lambda f: f.get("height", 0), reverse=True)[0]
        results.append({
            "pexels_id": video["id"],
            "pexels_url": video.get("url", ""),
            "download_url": best["link"],
            "width": best["width"],
            "height": best["height"],
            "duration": video["duration"],
            "query": query,
        })
    return results


def _download_clip(clip: dict, output_path: Path) -> bool:
    """Download a video clip from URL. Returns True on success."""
    try:
        print(f"[footage] Downloading {clip['width']}x{clip['height']} clip ({clip['duration']}s)...")
        resp = requests.get(clip["download_url"], timeout=60, stream=True)
        resp.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"[footage] Downloaded {output_path.name} ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        print(f"[footage] Download failed: {e}")
        if output_path.exists():
            output_path.unlink()
        return False


def _yt_dlp_cc_fallback(query: str) -> Path | None:
    """Search YouTube for CC-licensed dog footage. Returns path if downloaded."""
    print(f"[footage] Trying yt-dlp CC fallback for: {query}")
    try:
        import yt_dlp

        output_template = str(DOG_FOOTAGE_DIR / "cc_%(id)s.%(ext)s")
        ydl_opts = {
            "quiet": True,
            "match_filter": yt_dlp.utils.match_filter_func(
                "license='Creative Commons Attribution license (reuse allowed)'"
            ),
            "playlistend": 10,
            "format": "bestvideo[height<=1920][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "sleep_interval": 1,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch10:{query} dog", download=True)
            if info and info.get("entries"):
                for entry in info["entries"]:
                    if entry:
                        downloaded = DOG_FOOTAGE_DIR / f"cc_{entry['id']}.mp4"
                        if downloaded.exists():
                            print(f"[footage] CC download: {downloaded.name}")
                            return downloaded
    except Exception as e:
        print(f"[footage] yt-dlp fallback failed: {e}")
    return None


def _record_footage(clip_path: Path, source: str, topic_cluster: str, query: str) -> None:
    """Record downloaded clip in footage_index.json."""
    index = {}
    if FOOTAGE_INDEX.exists():
        try:
            index = json.loads(FOOTAGE_INDEX.read_text())
        except Exception:
            index = {}

    index[clip_path.name] = {
        "path": str(clip_path),
        "source": source,
        "topic_cluster": topic_cluster,
        "query": query,
        "downloaded_at": datetime.now().isoformat(),
    }
    FOOTAGE_INDEX.parent.mkdir(parents=True, exist_ok=True)
    tmp = FOOTAGE_INDEX.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, indent=2, sort_keys=True))
    tmp.replace(FOOTAGE_INDEX)


def fetch_footage_for_topic(topic_cluster: str, topic: str) -> Path | None:
    """
    Main entry point. Find and download a dog clip relevant to the topic.
    Returns path to downloaded clip, or None if all sources failed.

    Priority:
    1. Pexels portrait clip matching topic cluster queries
    2. yt-dlp CC fallback
    """
    DOG_FOOTAGE_DIR.mkdir(exist_ok=True)
    api_key = _load_api_key()

    # Build query list for this topic cluster
    # Primary query: full topic string for maximum specificity
    primary = "dog " + topic.replace("_", " ").strip()
    # Secondary: topic-cluster queries, randomised
    cluster_queries = TOPIC_SEARCH_MAP.get(topic_cluster, DEFAULT_QUERIES).copy()
    random.shuffle(cluster_queries)
    queries = [primary] + cluster_queries

    for query in queries:
        clips = _search_pexels(query, api_key)
        if not clips:
            continue

        # Prefer clips 10-60s (good for Shorts background)
        good_clips = [c for c in clips if 8 <= c["duration"] <= 90]
        if not good_clips:
            good_clips = clips

        clip = random.choice(good_clips[:5])
        filename = f"pexels_{clip['pexels_id']}_{topic_cluster.replace(' ', '_')}.mp4"
        output_path = DOG_FOOTAGE_DIR / filename

        if output_path.exists():
            print(f"[footage] Already have: {filename}")
            _record_footage(output_path, "pexels", topic_cluster, query)
            return output_path

        if _download_clip(clip, output_path):
            _record_footage(output_path, "pexels", topic_cluster, query)
            return output_path

    # All Pexels queries failed — try yt-dlp CC
    cc_path = _yt_dlp_cc_fallback(topic)
    if cc_path:
        _record_footage(cc_path, "youtube_cc", topic_cluster, topic)
        return cc_path

    print(f"[footage] All sources failed for topic: {topic}")
    return None


def prefetch_footage_library(n_clips: int = 20) -> list:
    """
    Pre-download N diverse dog clips across all topic clusters.
    Call this once to seed the library with quality footage.
    """
    api_key = _load_api_key()
    DOG_FOOTAGE_DIR.mkdir(exist_ok=True)
    downloaded = []

    all_queries = []
    for queries in TOPIC_SEARCH_MAP.values():
        all_queries.extend(queries)
    random.shuffle(all_queries)

    for query in all_queries[:n_clips]:
        clips = _search_pexels(query, api_key, per_page=5)
        if not clips:
            continue
        clip = clips[0]
        filename = f"pexels_{clip['pexels_id']}.mp4"
        output_path = DOG_FOOTAGE_DIR / filename
        if output_path.exists():
            downloaded.append(output_path)
            continue
        if _download_clip(clip, output_path):
            _record_footage(output_path, "pexels", "general", query)
            downloaded.append(output_path)

    return downloaded
