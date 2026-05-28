"""
Score and rank harvested Reddit stories for suitability as video content.

Scoring (0–10 total):
- Length fit  (3 pts): word_count match to target format
- Hook strength (4 pts): horror/dread words in title
- Upvote signal (3 pts): log-scaled score
"""
import math

SHORT_WORD_RANGE = (40, 120)
LONG_WORD_RANGE  = (600, 1800)

HOOK_WORDS = {
    "what", "why", "who", "how", "found", "heard", "saw", "inside",
    "behind", "under", "never", "disappeared", "wrong", "dark", "alone",
    "door", "basement", "woods", "road", "night", "watching", "missing",
    "followed", "stalked", "crawled", "screamed", "dead", "monster",
    "creature", "shadow", "whispered", "blood", "escaped", "trapped",
}


def _length_score(word_count: int, target: str) -> float:
    lo, hi = SHORT_WORD_RANGE if target == "short" else LONG_WORD_RANGE
    if lo <= word_count <= hi:
        return 1.0
    dist = min(abs(word_count - lo), abs(word_count - hi))
    return max(0.0, 1.0 - dist / max(lo, 1))


def _hook_score(title: str) -> float:
    words = set(title.lower().split())
    return min(1.0, len(words & HOOK_WORDS) / 2)


def _upvote_score(score: int) -> float:
    return min(1.0, math.log1p(score) / math.log1p(5000))


def score_story(story: dict, target: str, used_ids: set) -> float:
    if story["id"] in used_ids:
        return 0.0
    return round(
        _length_score(story["word_count"], target) * 3 +
        _hook_score(story["title"]) * 4 +
        _upvote_score(story["score"]) * 3,
        2
    )


def pick_best_story(stories: list, target: str, used_ids: set) -> dict | None:
    scored = sorted(
        ((score_story(s, target, used_ids), s) for s in stories),
        key=lambda x: x[0], reverse=True
    )
    if not scored or scored[0][0] == 0:
        return None
    return scored[0][1]
