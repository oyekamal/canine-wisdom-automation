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

from config import VideoFormat

BASE_DIR = Path(__file__).parent.parent.parent
DOG_FOOTAGE_DIR = BASE_DIR / "dog_footage"
FOOTAGE_INDEX = BASE_DIR / "harness" / "data" / "footage_index.json"

# Topic → Pexels search queries mapping
# When the script topic matches a cluster, we use more specific search terms
TOPIC_SEARCH_MAP = {
    # Horror / paranormal clusters
    "nosleep": [
        "dark foggy forest night",
        "abandoned house hallway dark",
        "empty road night fog",
        "dark basement stairs",
        "shadow silhouette night",
    ],
    "paranormal": [
        "foggy graveyard night",
        "dark haunted house exterior",
        "misty forest eerie night",
        "candle flame darkness",
        "empty corridor dark building",
    ],
    "true scary": [
        "empty dark road night",
        "abandoned building interior dark",
        "dark woods trail night",
        "figure silhouette darkness",
        "storm approaching dark sky",
    ],
    "creepy encounters": [
        "dark path forest night",
        "abandoned rural house",
        "misty lake night",
        "empty parking lot night",
        "dark alley city night",
    ],
    "short horror": [
        "dark room single light",
        "shadow on wall",
        "foggy night street lamp",
        "creepy window reflection night",
        "dark hallway door end",
    ],
    "unsolved mysteries": [
        "crime scene tape dark",
        "old photograph mystery",
        "dark detective office noir",
        "foggy cold case file",
        "empty road disappearance",
    ],
    "night shift stories": [
        "empty hospital corridor night",
        "security guard dark building",
        "night shift worker alone",
        "empty office building night",
        "factory worker alone night",
    ],
    "dog health": [
        "veterinarian examining dog",
        "dog anxiety panting",
        "dog health checkup vet",
        "dog scratching itching skin",
        "dog limping injured paw",
    ],
    "dog behavior": [
        "dog anxiety panting stressed",
        "dog barking aggressive",
        "dog separation anxiety alone",
        "dog jumping on people",
        "dog tail wagging happy",
    ],
    "dog breeds": [
        "golden retriever puppy portrait",
        "german shepherd alert closeup",
        "french bulldog sitting",
        "husky dog blue eyes closeup",
        "labrador retriever running",
    ],
    "dog training": [
        "puppy learning tricks training",
        "dog sit command obedience",
        "dog trainer reward treat",
        "dog agility obstacle course",
        "puppy first training lesson",
    ],
    "dog history": [
        "wolf pack running wild",
        "dog human bond loyal",
        "ancient dog companion human",
        "dog working farm herding",
        "dog guard protection",
    ],
    "dog science": [
        "dog nose sniffing closeup",
        "dog dna test swab mouth",
        "dog eye vision closeup",
        "dog brain intelligence test",
        "dog smell detect scent",
    ],
    "dog fun": [
        "puppy playing fetch ball",
        "dog running beach waves",
        "dog swimming water happy",
        "puppy zoomies running fast",
        "dog catching frisbee air",
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


def _load_pixabay_key() -> str | None:
    """Load Pixabay API key from .env. Returns None if not set (fallback disabled)."""
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    return os.getenv("PIXABAY_API_KEY") or None


def _search_pexels(query: str, api_key: str, per_page: int = 15, orientation: str = "portrait") -> list:
    """Search Pexels for dog videos. Returns list of clip dicts."""
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "orientation": orientation,
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
        # Find best file matching requested orientation
        def _keep_file(f):
            w, h = f.get("width", 0), f.get("height", 0)
            if orientation == "portrait":
                return h > w and h >= 720
            else:
                return w > h and w >= 1280
        portrait_files = [f for f in video.get("video_files", []) if _keep_file(f)]
        if not portrait_files:
            # Accept any file — we'll crop in ffmpeg
            min_dim = 720 if orientation == "portrait" else 1280
            all_files = [f for f in video.get("video_files", []) if max(f.get("height", 0), f.get("width", 0)) >= min_dim]
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


def _search_pixabay(query: str, api_key: str, per_page: int = 15, orientation: str = "vertical") -> list:
    """Search Pixabay for dog videos. Returns list of clip dicts matching _search_pexels format."""
    try:
        resp = requests.get(
            "https://pixabay.com/api/videos/",
            params={
                "key": api_key,
                "q": query,
                "video_type": "film",
                "orientation": orientation,
                "per_page": per_page,
            },
            timeout=15,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
    except Exception as e:
        print(f"[footage] Pixabay search failed for '{query}': {e}")
        return []

    results = []
    for hit in hits:
        if hit.get("duration", 0) < 8:
            continue
        large = hit.get("videos", {}).get("large", {})
        if not large.get("url"):
            medium = hit.get("videos", {}).get("medium", {})
            if not medium.get("url"):
                continue
            large = medium
        results.append({
            "pexels_id": f"pixabay_{hit['id']}",
            "pexels_url": hit.get("pageURL", ""),
            "download_url": large["url"],
            "width": large.get("width", 0),
            "height": large.get("height", 0),
            "duration": hit["duration"],
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
    """Record downloaded clip in a per-directory footage_index.json (dict keyed by filename)."""
    index_path = clip_path.parent / "footage_index.json"
    index = {}
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text())
            # footage_db writes a list; _record_footage uses a dict — convert if needed
            if isinstance(existing, list):
                index = {item["filename"]: item for item in existing if "filename" in item}
            elif isinstance(existing, dict):
                index = existing
        except Exception:
            index = {}

    index[clip_path.name] = {
        "path": str(clip_path),
        "source": source,
        "topic_cluster": topic_cluster,
        "query": query,
        "downloaded_at": datetime.now().isoformat(),
    }
    tmp = index_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, indent=2, sort_keys=True))
    tmp.replace(index_path)


def fetch_footage_for_topic(topic_cluster: str, topic: str, fmt=VideoFormat.SHORT, save_dir: Path = None) -> Path | None:
    """
    Main entry point. Find and download a clip relevant to the topic.
    Returns path to downloaded clip, or None if all sources failed.

    Args:
        save_dir: Directory to save clip into. Defaults to DOG_FOOTAGE_DIR.

    Priority:
    1. Pexels portrait/landscape clip matching topic cluster queries
    2. Pixabay fallback
    3. yt-dlp CC fallback
    """
    orientation_pexels  = "portrait"   if fmt == VideoFormat.SHORT else "landscape"
    orientation_pixabay = "vertical"   if fmt == VideoFormat.SHORT else "horizontal"

    footage_dir = save_dir if save_dir is not None else DOG_FOOTAGE_DIR
    footage_dir.mkdir(parents=True, exist_ok=True)
    api_key = _load_api_key()

    # Build query list for this topic cluster
    cluster_queries = TOPIC_SEARCH_MAP.get(topic_cluster, DEFAULT_QUERIES).copy()
    random.shuffle(cluster_queries)
    # Don't prepend "dog" prefix when using non-dog topic maps
    dog_topics = {"dog health","dog behavior","dog breeds","dog training","dog history","dog science","dog fun",
                  "dog anxiety","dog calming","dog separation anxiety","senior dog","dog joint health","dog nutrition","dog safety"}
    if topic_cluster in dog_topics:
        primary = "dog " + topic.replace("_", " ").strip()
        queries = [primary] + cluster_queries
    else:
        queries = cluster_queries  # horror topics — no "dog" prefix

    for query in queries:
        clips = _search_pexels(query, api_key, orientation=orientation_pexels)
        if not clips:
            continue

        good_clips = [c for c in clips if 8 <= c["duration"] <= 90]
        if not good_clips:
            good_clips = clips

        clip = random.choice(good_clips[:5])
        filename = f"pexels_{clip['pexels_id']}_{topic_cluster.replace(' ', '_')}.mp4"
        output_path = footage_dir / filename

        if output_path.exists():
            print(f"[footage] Already have: {filename}")
            _record_footage(output_path, "pexels", topic_cluster, query)
            return output_path

        if _download_clip(clip, output_path):
            _record_footage(output_path, "pexels", topic_cluster, query)
            return output_path

    # All Pexels queries failed — try Pixabay
    pixabay_key = _load_pixabay_key()
    if pixabay_key:
        print(f"[footage] Pexels exhausted — trying Pixabay for: {topic}")
        for query in queries:
            clips = _search_pixabay(query, pixabay_key, orientation=orientation_pixabay)
            if not clips:
                continue
            good_clips = [c for c in clips if 8 <= c["duration"] <= 90]
            if not good_clips:
                good_clips = clips
            clip = random.choice(good_clips[:5])
            filename = f"pixabay_{clip['pexels_id'].replace('pixabay_', '')}_{topic_cluster.replace(' ', '_')}.mp4"
            output_path = footage_dir / filename
            if output_path.exists():
                print(f"[footage] Already have (Pixabay): {filename}")
                _record_footage(output_path, "pixabay", topic_cluster, query)
                return output_path
            if _download_clip(clip, output_path):
                _record_footage(output_path, "pixabay", topic_cluster, query)
                return output_path
    else:
        print("[footage] PIXABAY_API_KEY not set — skipping Pixabay fallback")

    # All Pixabay queries failed — try yt-dlp CC
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
