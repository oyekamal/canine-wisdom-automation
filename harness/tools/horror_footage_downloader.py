"""
One-time downloader for the horror channel footage library.
Downloads dark atmospheric clips into horror_footage/.
Run with: python3 -m harness.tools.horror_footage_downloader
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from harness.tools.footage import _search_pexels, _search_pixabay

HORROR_FOOTAGE_DIR = Path("horror_footage")

# (query, topic_cluster, n_clips)
DOWNLOAD_QUERIES = [
    ("dark foggy forest night",           "nosleep",            3),
    ("abandoned house interior dark",     "nosleep",            2),
    ("empty road night fog",              "creepy_encounters",  2),
    ("dark hallway shadows corridor",     "short_horror",       2),
    ("misty graveyard fog night",         "paranormal",         2),
    ("abandoned building dark corridor",  "unsolved_mysteries", 2),
    ("dark basement stairs horror",       "short_horror",       1),
    ("candle flame darkness closeup",     "paranormal",         1),
    ("storm dark sky lightning",          "true_scary",         2),
    ("empty night street lamp fog",       "night_shift_stories",2),
]


def _download_clip_direct(url: str, output_path: Path) -> bool:
    """Download a video clip from a direct URL. Returns True on success."""
    import requests
    try:
        r = requests.get(url, stream=True, timeout=60,
                         headers={"User-Agent": "horror_harness/1.0"})
        r.raise_for_status()
        output_path.write_bytes(r.content)
        return True
    except Exception as e:
        print(f"    ❌ Download failed: {e}")
        return False


def download_horror_footage():
    """Download horror clips into horror_footage/ and build footage index."""
    HORROR_FOOTAGE_DIR.mkdir(exist_ok=True)
    import os
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parents[2] / ".env")
    pexels_key = os.getenv("PEXELS_API_KEY", "")
    pixabay_key = os.getenv("PIXABAY_API_KEY", "")

    if not pexels_key and not pixabay_key:
        print("❌ No PEXELS_API_KEY or PIXABAY_API_KEY found in environment")
        return

    downloaded = 0

    for query, topic_cluster, n in DOWNLOAD_QUERIES:
        print(f"\n🔍 '{query}' [{topic_cluster}] — need {n} clips")
        clips = []

        if pexels_key:
            clips = _search_pexels(query, pexels_key, per_page=n * 3,
                                    orientation="portrait")
        if not clips and pixabay_key:
            clips = _search_pixabay(query, pixabay_key, per_page=n * 3,
                                     orientation="vertical")

        added = 0
        for clip in clips:
            if added >= n:
                break

            clip_id = clip.get("pexels_id") or clip.get("id", "unknown")
            filename = f"pexels_{clip_id}_{topic_cluster}.mp4"
            output_path = HORROR_FOOTAGE_DIR / filename

            if output_path.exists():
                print(f"  ✓ Already have: {filename}")
                added += 1
                continue

            url = clip.get("url") or clip.get("download_url", "")
            if not url:
                continue

            print(f"  ⬇  {filename} ...")
            if _download_clip_direct(url, output_path):
                added += 1
                downloaded += 1
                size_mb = output_path.stat().st_size / 1_000_000
                print(f"  ✅ {filename} ({size_mb:.1f} MB)")

            time.sleep(0.3)

        if added == 0:
            print(f"  ⚠️  No clips found for '{query}'")

    print(f"\n✅ Done. {downloaded} new clips downloaded to {HORROR_FOOTAGE_DIR}/")

    # Build footage index
    from footage_db import build_footage_index
    index_path = HORROR_FOOTAGE_DIR / "footage_index.json"
    clips_list = build_footage_index(HORROR_FOOTAGE_DIR, index_path)
    print(f"📋 Footage index: {len(clips_list)} total clips at {index_path}")


if __name__ == "__main__":
    download_horror_footage()
