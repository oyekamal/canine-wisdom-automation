"""
Single read/write interface for harness/data/learnings.json.
All evals and agents import from here — never read learnings.json directly.
"""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from harness.storage import atomic_write

LEARNINGS_PATH = Path(__file__).parent.parent / "data" / "learnings.json"
LOCK_PATH = LEARNINGS_PATH.with_suffix(".lock")
CACHE_TTL_HOURS = 1

_cache: Optional[dict] = None
_cache_time: Optional[datetime] = None

CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}
CONFIDENCE_THRESHOLDS = [(0, 4, "low"), (5, 19, "medium"), (20, 9999, "high")]


def _confidence_for(sample_size: int) -> str:
    for lo, hi, level in CONFIDENCE_THRESHOLDS:
        if lo <= sample_size <= hi:
            return level
    return "low"


def _invalidate_cache() -> None:
    global _cache, _cache_time
    _cache = None
    _cache_time = None


def read_learnings() -> dict:
    """Return parsed learnings.json. Cached in memory for 1 hour."""
    global _cache, _cache_time
    if _cache is not None and _cache_time is not None:
        if datetime.now() - _cache_time < timedelta(hours=CACHE_TTL_HOURS):
            return _cache
    _cache = json.loads(LEARNINGS_PATH.read_text(encoding="utf-8"))
    _cache_time = datetime.now()
    return _cache


def _write_learnings(data: dict) -> None:
    """Atomically write learnings and invalidate cache."""
    data["updated_at"] = datetime.now().isoformat()
    atomic_write(LEARNINGS_PATH, data)
    _invalidate_cache()


def get_top_hook_patterns(min_confidence: str = "low", n: int = 3) -> list:
    """Return top n hook patterns sorted by avg_3sec_retention_proxy."""
    learnings = read_learnings()
    min_level = CONFIDENCE_ORDER.get(min_confidence, 0)
    eligible = [
        p for p in learnings.get("hook_patterns", [])
        if CONFIDENCE_ORDER.get(p.get("confidence", "low"), 0) >= min_level
    ]
    return sorted(eligible, key=lambda p: p.get("avg_3sec_retention_proxy", 0), reverse=True)[:n]


def get_top_title_formulas(min_confidence: str = "low", n: int = 3) -> list:
    """Return top n title formulas sorted by avg_ctr."""
    learnings = read_learnings()
    min_level = CONFIDENCE_ORDER.get(min_confidence, 0)
    eligible = [
        f for f in learnings.get("title_formulas", [])
        if CONFIDENCE_ORDER.get(f.get("confidence", "low"), 0) >= min_level
    ]
    return sorted(eligible, key=lambda f: f.get("avg_ctr", 0), reverse=True)[:n]


def get_covered_topics(days: int = 30) -> list:
    """Return topic strings posted in the last N days."""
    learnings = read_learnings()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    return [
        t["topic"] for t in learnings.get("covered_topics", [])
        if t.get("posted", "1970-01-01") >= cutoff
    ]


def add_covered_topic(topic: str, video_id: str) -> None:
    """Append a topic to covered_topics and persist."""
    data = json.loads(LEARNINGS_PATH.read_text(encoding="utf-8"))
    data.setdefault("covered_topics", []).append({
        "topic": topic,
        "posted": datetime.now().strftime("%Y-%m-%d"),
        "video_id": video_id,
    })
    _write_learnings(data)


def _extract_hook_template(hook_text: str) -> str:
    """Reduce a hook sentence to a reusable template by replacing specifics."""
    text = re.sub(r"\b(cancer|fear|smell|detect|lick|bite|bark|hear|see|feel)\b", "[fact]", hook_text, flags=re.I)
    text = re.sub(r"\b(golden retriever|labrador|husky|poodle|beagle|bulldog|corgi)\b", "[breed]", text, flags=re.I)
    return text.strip()


def update_from_competitor(channel_id: str, videos: list) -> None:
    """
    Extract hook patterns from competitor video list, merging into learnings.
    Never overwrites entries where source == 'own_analytics'.
    """
    data = json.loads(LEARNINGS_PATH.read_text(encoding="utf-8"))
    today = datetime.now().strftime("%Y-%m-%d")

    own_hooks = {
        p["pattern"] for p in data.get("hook_patterns", [])
        if p.get("source") == "own_analytics"
    }

    hook_counts: dict[str, list] = {}
    for v in videos:
        hook = v.get("hook", "")
        if not hook:
            continue
        template = _extract_hook_template(hook)
        if template not in own_hooks:
            hook_counts.setdefault(template, []).append(v.get("like_rate", 0))

    existing_hooks = {
        p["pattern"]: p for p in data.get("hook_patterns", [])
        if p.get("source") != "own_analytics"
    }

    for template, like_rates in hook_counts.items():
        count = len(like_rates)
        retention_proxy = sum(like_rates) / count if like_rates else 0.0
        if template in existing_hooks:
            old = existing_hooks[template]
            total = old["sample_size"] + count
            existing_hooks[template] = {
                **old,
                "avg_3sec_retention_proxy": (
                    (old["avg_3sec_retention_proxy"] * old["sample_size"] + retention_proxy * count) / total
                ),
                "sample_size": total,
                "confidence": _confidence_for(total),
                "last_seen": today,
            }
        else:
            existing_hooks[template] = {
                "pattern": template,
                "avg_3sec_retention_proxy": retention_proxy,
                "sample_size": count,
                "confidence": _confidence_for(count),
                "source": "competitor",
                "last_seen": today,
            }

    own_list = [p for p in data.get("hook_patterns", []) if p.get("source") == "own_analytics"]
    data["hook_patterns"] = own_list + list(existing_hooks.values())
    _write_learnings(data)


def update_from_analytics(video_id: str, video_data: dict) -> None:
    """
    Update hook_patterns and title_formulas from one video's analytics.
    Marks updated entries as source='own_analytics'.
    """
    data = json.loads(LEARNINGS_PATH.read_text(encoding="utf-8"))
    today = datetime.now().strftime("%Y-%m-%d")

    hook_pattern = video_data.get("hook_pattern_used", "")
    title_formula = video_data.get("title_formula_used", "")
    ctr = float(video_data.get("avg_ctr_latest", 0))
    retention_sec = float(video_data.get("avg_view_duration_sec_latest", 0))

    if hook_pattern:
        hooks = {p["pattern"]: p for p in data.get("hook_patterns", [])}
        if hook_pattern in hooks:
            old = hooks[hook_pattern]
            n = old["sample_size"] + 1
            hooks[hook_pattern] = {
                **old,
                "avg_3sec_retention_proxy": (old["avg_3sec_retention_proxy"] * old["sample_size"] + retention_sec / 60) / n,
                "sample_size": n,
                "confidence": _confidence_for(n),
                "source": "own_analytics",
                "last_seen": today,
            }
        else:
            hooks[hook_pattern] = {
                "pattern": hook_pattern,
                "avg_3sec_retention_proxy": retention_sec / 60,
                "sample_size": 1,
                "confidence": "low",
                "source": "own_analytics",
                "last_seen": today,
            }
        data["hook_patterns"] = list(hooks.values())

    if title_formula:
        formulas = {f["formula"]: f for f in data.get("title_formulas", [])}
        if title_formula in formulas:
            old = formulas[title_formula]
            n = old["sample_size"] + 1
            formulas[title_formula] = {
                **old,
                "avg_ctr": (old["avg_ctr"] * old["sample_size"] + ctr) / n,
                "sample_size": n,
                "confidence": _confidence_for(n),
                "source": "own_analytics",
            }
        else:
            formulas[title_formula] = {
                "formula": title_formula,
                "avg_ctr": ctr,
                "sample_size": 1,
                "confidence": "low",
                "source": "own_analytics",
            }
        data["title_formulas"] = list(formulas.values())

    _write_learnings(data)


def rebuild_from_week(all_performance: list) -> list:
    """
    Full weekly rebuild from a week's worth of performance dicts.
    Groups by hook_pattern_used and title_formula_used, recomputes averages,
    appends anti_patterns for chronically low CTR.
    """
    data = json.loads(LEARNINGS_PATH.read_text(encoding="utf-8"))
    today = datetime.now().strftime("%Y-%m-%d")

    hook_groups: dict[str, list] = {}
    for v in all_performance:
        hp = v.get("hook_pattern_used", "")
        if hp:
            hook_groups.setdefault(hp, []).append(v)

    # Load prior own_analytics hooks to preserve history across weeks
    prior_own_hooks = {
        h["pattern"]: h for h in data.get("hook_patterns", [])
        if h.get("source") == "own_analytics"
    }

    new_hooks = []
    for pattern, vids in hook_groups.items():
        retentions = [v.get("avg_view_duration_sec_latest", 0) for v in vids]
        n_new = len(vids)
        if pattern in prior_own_hooks:
            old = prior_own_hooks[pattern]
            n_total = old["sample_size"] + n_new
            new_retention = (old["avg_3sec_retention_proxy"] * old["sample_size"] + sum(retentions) / 60) / n_total
            new_hooks.append({
                **old,
                "avg_3sec_retention_proxy": new_retention,
                "sample_size": n_total,
                "confidence": _confidence_for(n_total),
                "last_seen": today,
            })
        else:
            new_hooks.append({
                "pattern": pattern,
                "avg_3sec_retention_proxy": sum(retentions) / n_new / 60,
                "sample_size": n_new,
                "confidence": _confidence_for(n_new),
                "source": "own_analytics",
                "last_seen": today,
            })

    # Preserve prior own_analytics hooks that had no videos this week
    rebuilt_patterns = {h["pattern"] for h in new_hooks}
    for pattern, h in prior_own_hooks.items():
        if pattern not in rebuilt_patterns:
            new_hooks.append(h)

    formula_groups: dict[str, list] = {}
    for v in all_performance:
        tf = v.get("title_formula_used", "")
        if tf:
            formula_groups.setdefault(tf, []).append(v)

    new_formulas = []
    anti_patterns = list(data.get("anti_patterns", []))
    existing_anti = {a["pattern"] for a in anti_patterns}

    for formula, vids in formula_groups.items():
        ctrs = [v.get("avg_ctr_latest", 0) for v in vids]
        avg_ctr = sum(ctrs) / len(ctrs)
        n = len(vids)
        new_formulas.append({
            "formula": formula,
            "avg_ctr": avg_ctr,
            "sample_size": n,
            "confidence": _confidence_for(n),
            "source": "own_analytics",
        })
        if avg_ctr < 0.04 and n >= 5 and formula not in existing_anti:
            anti_patterns.append({
                "pattern": formula,
                "reason": f"avg CTR {avg_ctr:.3f} across {n} videos",
                "source": "own_analytics",
                "added": today,
            })

    own_hook_patterns = {h["pattern"] for h in new_hooks}
    kept_competitor_hooks = [
        h for h in data.get("hook_patterns", [])
        if h.get("source") == "competitor" and h["pattern"] not in own_hook_patterns
    ]
    own_formula_patterns = {f["formula"] for f in new_formulas}
    kept_competitor_formulas = [
        f for f in data.get("title_formulas", [])
        if f.get("source") == "competitor" and f["formula"] not in own_formula_patterns
    ]

    data["hook_patterns"] = new_hooks + kept_competitor_hooks
    data["title_formulas"] = new_formulas + kept_competitor_formulas
    data["anti_patterns"] = anti_patterns
    result_hooks = data["hook_patterns"]
    _write_learnings(data)
    return result_hooks


def bootstrap_from_competitors(competitor_videos: list) -> None:
    """
    One-time bootstrap: populate learnings from competitor video data.
    Skips if any own_analytics entries already exist.
    """
    data = json.loads(LEARNINGS_PATH.read_text(encoding="utf-8"))

    has_own = any(
        p.get("source") == "own_analytics"
        for p in data.get("hook_patterns", []) + data.get("title_formulas", [])
    )
    if has_own:
        return

    update_from_competitor("__bootstrap__", competitor_videos)
