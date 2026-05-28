"""
Download free horror ambient music tracks for the horror channel.
All tracks are CC0 or CC-BY licensed — safe for YouTube.
Run with: python3 -m harness.tools.horror_music_downloader
"""
import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

MUSIC_DIR = Path("assets/music/horror")

# CC0/CC-BY tracks — multiple sources for reliability
TRACKS = [
    {
        "name": "Unseen_Horrors.mp3",
        "urls": [
            "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Unseen%20Horrors.mp3",
            "https://archive.org/download/incompetech-albums-0002-small-collection-2/Kevin_MacLeod_-_Unseen_Horrors.mp3",
        ],
        "credit": "Kevin MacLeod — Unseen Horrors (CC-BY 4.0) incompetech.com",
    },
    {
        "name": "Dark_Times.mp3",
        "urls": [
            "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Dark%20Times.mp3",
            "https://archive.org/download/incompetech-albums-0002-small-collection-2/Kevin_MacLeod_-_Dark_Times.mp3",
        ],
        "credit": "Kevin MacLeod — Dark Times (CC-BY 4.0) incompetech.com",
    },
    {
        "name": "Lightless_Dawn.mp3",
        "urls": [
            "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Lightless%20Dawn.mp3",
        ],
        "credit": "Kevin MacLeod — Lightless Dawn (CC-BY 4.0) incompetech.com",
    },
    {
        "name": "Danse_Macabre.mp3",
        "urls": [
            "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Danse%20Macabre.mp3",
        ],
        "credit": "Kevin MacLeod — Danse Macabre (CC-BY 4.0) incompetech.com",
    },
    {
        "name": "Crossing_The_Chasm.mp3",
        "urls": [
            "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Crossing%20the%20Chasm.mp3",
        ],
        "credit": "Kevin MacLeod — Crossing The Chasm (CC-BY 4.0) incompetech.com",
    },
]

HEADERS = {"User-Agent": "horror_harness/1.0"}


def _try_download(name: str, urls: list, output_path: Path) -> bool:
    """Try each URL in order, return True on first success."""
    for url in urls:
        try:
            print(f"  → trying {url[:60]}...")
            r = requests.get(url, timeout=20, headers=HEADERS, stream=True)
            r.raise_for_status()
            content = r.content
            if len(content) < 10_000:  # less than 10KB is probably an error page
                continue
            output_path.write_bytes(content)
            size_kb = len(content) // 1024
            print(f"  ✅ {name} ({size_kb} KB)")
            return True
        except Exception as e:
            print(f"  ⚠️  {url[:50]} failed: {e}")
            continue
    return False


def download_horror_music():
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    attr_lines = ["Horror ambient music tracks", "CC0 or CC-BY licensed — safe for YouTube monetization.", ""]
    downloaded = 0

    for track in TRACKS:
        path = MUSIC_DIR / track["name"]
        if path.exists() and path.stat().st_size > 10_000:
            print(f"✓ Already have: {track['name']}")
            attr_lines.append(f"{track['name']}: {track['credit']}")
            continue

        print(f"⬇  {track['name']}")
        if _try_download(track["name"], track["urls"], path):
            downloaded += 1
            attr_lines.append(f"{track['name']}: {track['credit']}")
        else:
            print(f"  ❌ All URLs failed for {track['name']} — skipping")

    (MUSIC_DIR / "ATTRIBUTION.txt").write_text(
        "\n".join(attr_lines), encoding="utf-8"
    )
    print(f"\n✅ Done. {downloaded} new tracks in {MUSIC_DIR}/")
    print(f"📋 Total tracks: {len(list(MUSIC_DIR.glob('*.mp3')))}")


if __name__ == "__main__":
    download_horror_music()
