"""
Trend & keyword research agent.

Builds a ranked daily topic queue from:
1. YouTube autocomplete (search suggest) — free, zero API quota
2. Competitor video title keyword frequency (from cached competitor data)

Output: harness/data/topics/YYYY-MM-DD.json
"""
import json
import re
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

from harness.storage import atomic_write, DATA_DIR

TOPICS_DIR = DATA_DIR / "topics"
COMPETITORS_DIR = DATA_DIR / "competitors"

DOG_SEED_TERMS = [
    "dog facts", "dog behavior", "dog health", "why do dogs",
    "dog breeds", "dog training tips", "dog science",
    "dogs can", "dogs detect", "dog nose", "dog hearing",
]

TOPIC_CLUSTERS = {
    "dog health": ["dog health", "dog sick", "dog cancer", "dog detect", "dog nose", "dog disease"],
    "dog behavior": ["dog behavior", "why do dogs", "dog lick", "dog bark", "dog tail", "dog sleep"],
    "dog breeds": ["dog breed", "dog size", "biggest dog", "smallest dog", "dog comparison"],
    "dog training": ["dog training", "dog obedience", "dog sit", "dog command", "dog learn"],
    "dog history": ["dog history", "dog ancient", "dog wolf", "dog evolution", "dog origin"],
    "dog science": ["dog science", "dog brain", "dog smell", "dog detect", "dogs can"],
    "dog fun": ["dog funny", "cute dog", "puppy facts", "dog love", "dog loyal"],
}


def _youtube_autocomplete(query: str) -> list:
    """
    Fetch YouTube search suggestions for a query.
    Uses the public suggest API — zero quota cost.
    Returns list of suggestion strings.
    """
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q={encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8")
        # Response is JSONP: window.google.ac.h([...])
        # Extract the JSON array
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if not match:
            return []
        data = json.loads(match.group(0))
        if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
            suggestions = []
            for item in data[1]:
                if isinstance(item, list) and item:
                    suggestions.append(str(item[0]))
                elif isinstance(item, str):
                    suggestions.append(item)
            return suggestions[:10]
    except Exception as e:
        print(f"[trend] autocomplete failed for '{query}': {e}")
    return []


def _get_competitor_topics() -> Counter:
    """
    Extract topic keywords from cached competitor video titles.
    Returns Counter of topic terms weighted by view count.
    """
    counts = Counter()
    if not COMPETITORS_DIR.exists():
        return counts

    for channel_dir in COMPETITORS_DIR.iterdir():
        if not channel_dir.is_dir():
            continue
        videos_dir = channel_dir / "videos"
        if not videos_dir.exists():
            continue
        for video_file in videos_dir.glob("*.json"):
            try:
                data = json.loads(video_file.read_text())
                title = data.get("title", "").lower()
                views = data.get("view_count", 0)
                weight = max(1, min(views // 10000, 10))  # cap weight at 10
                for cluster, keywords in TOPIC_CLUSTERS.items():
                    for kw in keywords:
                        if kw in title:
                            counts[cluster] += weight
                            break
            except Exception:
                continue
    return counts


def _get_covered_topics() -> set:
    """Load covered topics from learnings.json to avoid repeats."""
    try:
        from harness.tools.learnings import get_covered_topics
        return set(get_covered_topics(days=30))
    except Exception:
        return set()


def _assign_cluster(suggestion: str) -> str:
    """Assign a topic cluster to a suggestion string."""
    s = suggestion.lower()
    for cluster, keywords in TOPIC_CLUSTERS.items():
        if any(kw in s for kw in keywords):
            return cluster
    return "dog fun"  # default


def _suggestion_to_topic(suggestion: str) -> str:
    """Clean up a suggestion into a short topic phrase."""
    # Remove "dog facts" boilerplate
    topic = re.sub(r'\bdog facts\b', '', suggestion, flags=re.I).strip()
    topic = re.sub(r'\s+', ' ', topic).strip()
    return topic if topic else suggestion


def build_topic_queue(date: str = None) -> dict:
    """
    Build today's ranked topic queue and write to topics/YYYY-MM-DD.json.
    Returns the queue dict.
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    TOPICS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = TOPICS_DIR / f"{date}.json"

    # Already built today — return cached
    if out_file.exists():
        print(f"[trend] Topic queue already built for {date}")
        return json.loads(out_file.read_text())

    print(f"[trend] Building topic queue for {date}...")

    # Step 1: YouTube autocomplete for all seed terms
    all_suggestions = []
    for seed in DOG_SEED_TERMS:
        suggestions = _youtube_autocomplete(seed)
        for s in suggestions:
            if "dog" in s.lower() or "puppy" in s.lower():
                all_suggestions.append(s)

    print(f"[trend] Got {len(all_suggestions)} autocomplete suggestions")

    # Step 2: Competitor topic frequency
    competitor_counts = _get_competitor_topics()

    # Step 3: Covered topics to skip
    covered = _get_covered_topics()

    # Step 4: Score and rank topics
    suggestion_counts = Counter()
    for s in all_suggestions:
        normalized = s.lower().strip()
        suggestion_counts[normalized] += 1

    # Garbage filter — remove suggestions that are not real dog topics
    GARBAGE_TERMS = {
        "in hindi", "in english", "in tamil", "in telugu", "for kids",
        "shorts", "short", "2024", "2025", "2026", "top 10", "top 5",
        "compilation", "playlist", "subscribe", "channel",
    }

    def _is_garbage(suggestion: str) -> bool:
        s = suggestion.lower().strip()
        if len(s) < 8:
            return True  # too short to be a real topic
        if not any(w in s for w in ["dog", "puppy", "canine", "pup"]):
            return True  # must mention dogs
        if any(g in s for g in GARBAGE_TERMS):
            return True
        return False

    # Build ranked topic list
    topics = []
    seen_clusters = set()

    for suggestion, freq in suggestion_counts.most_common(50):
        if _is_garbage(suggestion):
            continue

        cluster = _assign_cluster(suggestion)
        topic_phrase = _suggestion_to_topic(suggestion)

        # Skip if too similar to covered topics
        skip = any(
            covered_t.lower() in topic_phrase.lower() or topic_phrase.lower() in covered_t.lower()
            for covered_t in covered
        )
        if skip:
            continue

        # Boost score if competitor data also shows this cluster trending
        competitor_boost = competitor_counts.get(cluster, 0)
        score = (freq * 10) + competitor_boost

        topics.append({
            "rank": 0,  # set after sort
            "topic": topic_phrase or suggestion,
            "raw_suggestion": suggestion,
            "topic_cluster": cluster,
            "score": score,
            "autocomplete_freq": freq,
            "competitor_boost": competitor_boost,
            "source": "autocomplete",
        })

    # Sort by score
    topics.sort(key=lambda t: t["score"], reverse=True)
    for i, t in enumerate(topics):
        t["rank"] = i + 1

    # If we got nothing (no competitor data yet, no suggestions), use fallback topics
    if not topics:
        print("[trend] No suggestions found — using fallback topics")
        fallback = [
            ("dogs can detect cancer", "dog health"),
            ("why dogs tilt their head", "dog behavior"),
            ("oldest dog breeds in history", "dog breeds"),
            ("how dogs read human emotions", "dog science"),
            ("dog nose print unique fingerprint", "dog science"),
        ]
        topics = [
            {
                "rank": i + 1,
                "topic": topic,
                "raw_suggestion": topic,
                "topic_cluster": cluster,
                "score": 50 - i * 5,
                "autocomplete_freq": 0,
                "competitor_boost": 0,
                "source": "fallback",
            }
            for i, (topic, cluster) in enumerate(fallback)
            if topic not in covered
        ]

    queue = {
        "date": date,
        "generated_at": datetime.now().isoformat(),
        "topics": topics[:20],  # top 20
        "used": None,
    }

    atomic_write(out_file, queue)
    print(f"[trend] Written {len(topics)} topics to {out_file.name}")
    return queue


def pick_best_topic(queue: dict) -> dict | None:
    """
    Pick the highest-ranked unused topic from the queue.
    Returns topic dict or None if queue is empty.
    """
    for topic in queue.get("topics", []):
        if not topic.get("used"):
            return topic
    return None


def mark_topic_used(date: str, topic: dict) -> None:
    """Mark a topic as used in today's queue file."""
    out_file = TOPICS_DIR / f"{date}.json"
    if not out_file.exists():
        return
    queue = json.loads(out_file.read_text())
    for t in queue.get("topics", []):
        if t.get("raw_suggestion") == topic.get("raw_suggestion"):
            t["used"] = True
    queue["used"] = topic.get("topic")
    atomic_write(out_file, queue)
