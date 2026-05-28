"""
Decides whether a pipeline run should produce a Short (vertical) or Long-form (landscape) video.

Rules (in priority order):
1. Topic cluster in LONG_FORM_CLUSTERS → LONG
2. Last 5 runs for this cluster were all SHORT → LONG (variety)
3. Otherwise → SHORT
"""
from config import VideoFormat

LONG_FORM_CLUSTERS = {
    "dog health",
    "dog training",
    "senior dog",
    "dog nutrition",
    "dog science",
}


def pick_format(topic_cluster: str, recent_runs: list) -> VideoFormat:
    """
    Args:
        topic_cluster: e.g. "dog fun", "dog health"
        recent_runs: list of dicts with keys "topic_cluster" and "format" ("short"|"long"),
                     ordered newest-first.
    Returns:
        VideoFormat.SHORT or VideoFormat.LONG
    """
    if topic_cluster in LONG_FORM_CLUSTERS:
        return VideoFormat.LONG

    cluster_runs = [r for r in recent_runs if r.get("topic_cluster") == topic_cluster]
    last_five = cluster_runs[:5]
    if len(last_five) >= 5 and all(r.get("format") == "short" for r in last_five):
        return VideoFormat.LONG

    return VideoFormat.SHORT
