"""
Asset matcher for dailyygstories.

Given script_data returned by the rewriter (which includes setting_keywords),
derives a Pexels search query and delegates to the existing fetch_footage_for_topic().
"""
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
