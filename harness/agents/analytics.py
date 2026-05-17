"""
YouTube Analytics Agent.

Daily: pull analytics for all tracked videos, append snapshots.
Weekly: rebuild learnings.json from week's performance data.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

from harness.storage import atomic_write, DATA_DIR
from harness.tools.learnings import rebuild_from_week
from upload_youtube import get_analytics_service

# NOTE: DATA_DIR is imported so tests can patch `harness.agents.analytics.DATA_DIR`.
# All path helpers below read DATA_DIR at call time so patching takes effect.


def _performance_dir() -> Path:
    return DATA_DIR / "performance"


def _index_path() -> Path:
    return _performance_dir() / "index.json"


def track_video(video_id: str, metadata: dict) -> None:
    """
    Register a newly uploaded video for analytics tracking.
    Creates performance/{video_id}.json and adds to index.json.
    Idempotent — calling twice for the same video_id is safe.
    """
    perf_dir = _performance_dir()
    perf_dir.mkdir(parents=True, exist_ok=True)
    perf_file = perf_dir / f"{video_id}.json"
    index_path = _index_path()

    if not perf_file.exists():
        record = {
            "video_id": video_id,
            "title": metadata.get("title", ""),
            "format": metadata.get("format", "short"),
            "topic": metadata.get("topic", ""),
            "topic_cluster": metadata.get("topic_cluster", ""),
            "uploaded_at": datetime.now().isoformat(),
            "hook_pattern_used": metadata.get("hook_pattern_used", ""),
            "title_formula_used": metadata.get("title_formula_used", ""),
            "eval_scores": metadata.get("eval_scores", {}),
            "snapshots": [],
        }
        atomic_write(perf_file, record)

    # Register in index (idempotent)
    index = json.loads(index_path.read_text()) if index_path.exists() else {"videos": []}
    if not any(v["video_id"] == video_id for v in index.get("videos", [])):
        index.setdefault("videos", []).append({
            "video_id": video_id,
            "format": metadata.get("format", "short"),
            "uploaded_at": datetime.now().isoformat(),
        })
        index["total_videos_tracked"] = len(index["videos"])
        atomic_write(index_path, index)


def _get_video_ids_to_track() -> list:
    """Return all video_ids registered in index.json."""
    index_path = _index_path()
    if not index_path.exists():
        return []
    index = json.loads(index_path.read_text())
    return [v["video_id"] for v in index.get("videos", [])]


def _parse_analytics_row(row: list, headers: list) -> dict:
    """Map a YouTube Analytics API row to a named dict."""
    col_map = {h["name"]: i for i, h in enumerate(headers)}
    return {
        "views": int(row[col_map["views"]]),
        "watch_time_minutes": float(row[col_map["estimatedMinutesWatched"]]),
        "avg_view_duration_sec": float(row[col_map["averageViewDuration"]]),
        "likes": int(row[col_map["likes"]]),
        "comments": int(row[col_map["comments"]]),
        "subscribers_gained": int(row[col_map["subscribersGained"]]),
    }


def pull_daily_snapshots() -> dict:
    """
    Pull analytics for all tracked videos and append today's snapshot.
    Skips videos that already have a snapshot for today.
    """
    video_ids = _get_video_ids_to_track()
    if not video_ids:
        return {"pulled": 0}

    analytics = get_analytics_service()
    today = datetime.now().strftime("%Y-%m-%d")
    pulled = 0
    perf_dir = _performance_dir()

    for vid_id in video_ids:
        perf_file = perf_dir / f"{vid_id}.json"
        if not perf_file.exists():
            continue

        perf = json.loads(perf_file.read_text())

        if any(s["date"] == today for s in perf.get("snapshots", [])):
            continue

        try:
            resp = analytics.reports().query(
                ids="channel==MINE",
                startDate=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
                endDate=today,
                metrics="views,estimatedMinutesWatched,averageViewDuration,subscribersGained,likes,comments",
                filters=f"video=={vid_id}",
            ).execute()

            rows = resp.get("rows", [])
            headers = resp.get("columnHeaders", [])
            if not rows:
                continue

            snapshot = {"date": today, **_parse_analytics_row(rows[0], headers)}
            perf.setdefault("snapshots", []).append(snapshot)
            atomic_write(perf_file, perf)
            pulled += 1

        except Exception as exc:
            print(f"[analytics] snapshot pull failed for {vid_id}: {exc}")
            continue

    return {"pulled": pulled}


def rebuild_learnings_from_week() -> None:
    """
    Full weekly rebuild: aggregate all videos posted in last 7 days,
    compute averages, call learnings.rebuild_from_week().
    """
    video_ids = _get_video_ids_to_track()
    cutoff = datetime.now() - timedelta(days=7)
    week_data = []
    perf_dir = _performance_dir()

    for vid_id in video_ids:
        perf_file = perf_dir / f"{vid_id}.json"
        if not perf_file.exists():
            continue
        perf = json.loads(perf_file.read_text())

        uploaded_str = perf.get("uploaded_at", "")
        try:
            uploaded = datetime.fromisoformat(uploaded_str)
        except Exception:
            continue
        if uploaded < cutoff:
            continue

        snapshots = perf.get("snapshots", [])
        if not snapshots:
            continue

        latest = snapshots[-1]
        week_data.append({
            "hook_pattern_used": perf.get("hook_pattern_used", ""),
            "title_formula_used": perf.get("title_formula_used", ""),
            "avg_ctr_latest": latest.get("ctr", 0),
            "avg_view_duration_sec_latest": latest.get("avg_view_duration_sec", 0),
            "topic": perf.get("topic", ""),
            "topic_cluster": perf.get("topic_cluster", ""),
            "avg_views_latest": latest.get("views", 0),
        })

    if week_data:
        rebuild_from_week(week_data)
