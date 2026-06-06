"""
Learnings-aware story scorer for dailyygstories.

Replaces the simple keyword bag-of-words scorer in horror-narration/harness/story_scorer.py.
Incorporates:
  - Length fit to target format
  - Horror signal word density (title + text)
  - Upvote/engagement signal
  - Trending source bonus (news/trends > reddit)
  - Learnings boost: story types that historically drove subscriber gain
"""
import math
import re

SHORT_WORD_RANGE = (60, 120)
LONG_WORD_RANGE = (700, 1800)

HORROR_WORDS = {
    "missing", "dead", "disappeared", "murder", "killed", "escaped", "trapped",
    "stalked", "followed", "watched", "shadow", "creature", "monster", "dark",
    "alone", "door", "basement", "woods", "night", "blood", "whispered", "screamed",
    "locked", "body", "cold", "breathing", "ran", "chased", "grabbed", "dragged",
}


def _length_score(word_count: int, target: str) -> float:
    lo, hi = SHORT_WORD_RANGE if target == "short" else LONG_WORD_RANGE
    if lo <= word_count <= hi:
        return 1.0
    dist = min(abs(word_count - lo), abs(word_count - hi))
    return max(0.0, 1.0 - dist / max(lo, 1))


def _horror_density(title: str, text: str) -> float:
    """Score 0-1 based on horror signal words in title (weighted 2x) + text sample."""
    title_words = set(re.sub(r"[^\w\s]", "", title.lower()).split())
    text_sample = set(re.sub(r"[^\w\s]", "", text[:500].lower()).split())
    title_hits = len(title_words & HORROR_WORDS) * 2
    text_hits = len(text_sample & HORROR_WORDS)
    return min(1.0, (title_hits + text_hits) / 8)


def _engagement_score(candidate: dict) -> float:
    raw = candidate.get("score", 0)
    if raw <= 0:
        return 0.0
    return min(1.0, math.log1p(raw) / math.log1p(5000))


def _source_bonus(candidate: dict) -> float:
    """News and trends are more likely to be timely/viral."""
    source = candidate.get("source", "reddit")
    return {"news": 0.3, "trends": 0.2, "reddit": 0.0}.get(source, 0.0)


def _learnings_boost(candidate: dict, top_story_types: list) -> float:
    """
    Boost if candidate's likely story type matches top performers.
    top_story_types: list of dicts with keys story_type, avg_sub_gain_per_1k_views
    """
    if not top_story_types:
        return 0.0
    title_lower = candidate.get("title", "").lower()
    source = candidate.get("source", "reddit")

    if source == "news":
        likely_type = "true_crime" if any(w in title_lower for w in ["murder", "missing", "killed", "crime"]) else "real_news_horror"
    elif "subreddit" in candidate and candidate.get("subreddit") in ("nosleep", "shortscarystories"):
        likely_type = "paranormal"
    else:
        likely_type = "paranormal"

    for i, st in enumerate(top_story_types):
        if st.get("story_type") == likely_type:
            return max(0.0, 0.3 - i * 0.1)
    return 0.0


def score_candidate(candidate: dict, target: str, used_ids: set, top_story_types: list) -> float:
    if candidate["id"] in used_ids:
        return 0.0
    length   = _length_score(candidate.get("word_count", 0), target) * 3.0
    horror   = _horror_density(candidate.get("title", ""), candidate.get("text", "")) * 3.0
    engage   = _engagement_score(candidate) * 2.0
    source   = _source_bonus(candidate) * 1.0
    learning = _learnings_boost(candidate, top_story_types) * 1.0
    return round(length + horror + engage + source + learning, 3)


def pick_best_candidate(candidates: list, target: str, used_ids: set, top_story_types: list) -> dict | None:
    scored = sorted(
        ((score_candidate(c, target, used_ids, top_story_types), c) for c in candidates),
        key=lambda x: x[0],
        reverse=True,
    )
    if not scored or scored[0][0] == 0.0:
        return None
    return scored[0][1]
