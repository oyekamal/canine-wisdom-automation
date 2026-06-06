"""
Update dailyygstories channel-specific learnings.json with video performance.

Called after analytics snapshot pull shows 48h+ data for a video.
Updates story_type_performance dict so intelligent_scorer can boost top types.
"""
import json
from datetime import datetime
from pathlib import Path


def update_story_type_performance(channel_dir: Path, story_type: str, video_data: dict):
    """
    video_data keys: views, subscribers_gained, avg_view_duration_sec
    Updates story_type_performance[story_type] with rolling average.
    """
    learnings_path = channel_dir / "data" / "learnings.json"
    data = json.loads(learnings_path.read_text(encoding="utf-8"))

    views = float(video_data.get("views", 0))
    subs_gained = float(video_data.get("subscribers_gained", 0))
    sub_gain_per_1k = (subs_gained / views * 1000) if views > 0 else 0.0
    retention = float(video_data.get("avg_view_duration_sec", 0))

    perf = data.setdefault("story_type_performance", {})
    if story_type in perf:
        old = perf[story_type]
        n = old.get("sample_size", 1)
        perf[story_type] = {
            "story_type": story_type,
            "avg_sub_gain_per_1k_views": (old["avg_sub_gain_per_1k_views"] * n + sub_gain_per_1k) / (n + 1),
            "avg_view_duration_sec": (old["avg_view_duration_sec"] * n + retention) / (n + 1),
            "sample_size": n + 1,
            "last_seen": datetime.now().strftime("%Y-%m-%d"),
        }
    else:
        perf[story_type] = {
            "story_type": story_type,
            "avg_sub_gain_per_1k_views": sub_gain_per_1k,
            "avg_view_duration_sec": retention,
            "sample_size": 1,
            "last_seen": datetime.now().strftime("%Y-%m-%d"),
        }

    data["updated_at"] = datetime.now().isoformat()
    learnings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[learnings_updater] Updated {story_type}: sub_gain/1k={sub_gain_per_1k:.2f}")
