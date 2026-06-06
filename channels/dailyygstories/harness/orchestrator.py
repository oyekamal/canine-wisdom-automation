"""
dailyygstories Channel Orchestrator — Full Pipeline

Run with: python -m channels.dailyygstories.harness.orchestrator
Or via low_cpu_runner: python scripts/low_cpu_runner.py --channel dailyygstories
"""
import importlib.util as ilu
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from channel_config import load_channel_config
from generate_audio import generate_audio
from build_video import build_video
from upload_youtube import upload_youtube
from utils import init_logger, log, clear_outputs_dir, move_outputs_to_archive
from harness.storage import atomic_write, atomic_read, get_state_path
from harness.agents.analytics import track_video
from config import VideoFormat

from channels.dailyygstories.harness.trend_horror import harvest_all
from channels.dailyygstories.harness.intelligent_scorer import pick_best_candidate
from channels.dailyygstories.harness.story_classifier import classify_story
from channels.dailyygstories.harness.asset_matcher import fetch_matched_footage


def _load_rewriter():
    p = Path(__file__).parents[3] / "channels" / "horror-narration" / "harness" / "story_rewriter.py"
    spec = ilu.spec_from_file_location("story_rewriter", p)
    m = ilu.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


_rewriter = _load_rewriter()


def _build_prompt_with_learnings(channel_config, top_story_types: list) -> str:
    learnings_path = channel_config.channel_dir / "data" / "learnings.json"

    try:
        data = json.loads(learnings_path.read_text())
        hooks = sorted(data.get("hook_patterns", []),
                       key=lambda p: p.get("avg_3sec_retention_proxy", 0), reverse=True)[:3]
        titles = sorted(data.get("title_formulas", []),
                        key=lambda f: f.get("avg_ctr", 0), reverse=True)[:3]
        covered = [t["topic"] for t in data.get("covered_topics", [])[-30:]]
    except Exception:
        hooks, titles, covered = [], [], []

    hooks_text = "\n".join(f'- "{h["pattern"]}"' for h in hooks) or "- No data yet"
    titles_text = "\n".join(f'- "{t["formula"]}"' for t in titles) or "- No data yet"
    covered_text = ", ".join(covered) or "none"
    story_types_text = "\n".join(
        f'- {st["story_type"]} (avg sub gain/1k: {st.get("avg_sub_gain_per_1k_views", 0):.1f})'
        for st in top_story_types
    ) or "- No data yet"

    raw = channel_config.prompt_path.read_text(encoding="utf-8")
    return (raw
            .replace("{hooks_text}", hooks_text)
            .replace("{titles_text}", titles_text)
            .replace("{covered_text}", covered_text)
            .replace("{top_story_types}", story_types_text))


def _process_pending_analytics(channel_config, state: dict):
    """Pull analytics for videos uploaded 48h+ ago and update story_type learnings."""
    from upload_youtube import get_analytics_service
    from channels.dailyygstories.harness.learnings_updater import update_story_type_performance
    from datetime import timedelta

    pending = state.get("pending_analytics", [])
    still_pending = []
    cutoff = datetime.now() - timedelta(hours=48)

    for item in pending:
        try:
            uploaded = datetime.fromisoformat(item["uploaded_at"])
        except Exception:
            continue

        if uploaded > cutoff:
            still_pending.append(item)
            continue

        try:
            analytics = get_analytics_service()
            resp = analytics.reports().query(
                ids="channel==MINE",
                startDate=uploaded.strftime("%Y-%m-%d"),
                endDate=datetime.now().strftime("%Y-%m-%d"),
                metrics="views,estimatedMinutesWatched,averageViewDuration,subscribersGained",
                filters=f"video=={item['video_id']}",
            ).execute()
            rows = resp.get("rows", [])
            headers = resp.get("columnHeaders", [])
            if rows:
                col_map = {h["name"]: i for i, h in enumerate(headers)}
                video_data = {
                    "views": int(rows[0][col_map["views"]]),
                    "avg_view_duration_sec": float(rows[0][col_map["averageViewDuration"]]),
                    "subscribers_gained": int(rows[0][col_map["subscribersGained"]]),
                }
                update_story_type_performance(
                    channel_config.channel_dir, item["story_type"], video_data
                )
        except Exception as e:
            log(f"⚠️  Analytics pull failed for {item['video_id']}: {e}", level="warning")
            still_pending.append(item)

    state["pending_analytics"] = still_pending


def run_dailyygstories_pipeline(channel_config=None, dry_run: bool = False) -> dict:
    if channel_config is None:
        channel_config = load_channel_config("dailyygstories")

    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    init_logger(run_id)
    log(f"👁️  dailyygstories Harness — starting [{channel_config.slug}]")
    clear_outputs_dir()

    state_path = get_state_path(channel_config)
    try:
        state = atomic_read(state_path)
    except FileNotFoundError:
        state = {}

    _process_pending_analytics(channel_config, state)

    used_ids = set(state.get("used_story_ids", []))

    # ── Load learnings ────────────────────────────────────────────────────────
    from harness.tools.learnings import get_top_story_types
    top_story_types = get_top_story_types(
        n=3,
        channel_learnings_path=channel_config.channel_dir / "data" / "learnings.json"
    )

    # ── Harvest all sources ───────────────────────────────────────────────────
    log("🕸️  Harvesting stories from all sources...")
    try:
        candidates = harvest_all(channel_config)
        log(f"📚 Total candidates: {len(candidates)}")
    except Exception as e:
        log(f"❌ Harvest failed: {e}", level="error")
        return {"success": False, "video_url": None, "reason": f"harvest failed: {e}"}

    if not candidates:
        return {"success": False, "video_url": None, "reason": "no candidates harvested"}

    # ── Classify + rewrite (try up to 5 candidates) ──────────────────────────
    prompt_text = _build_prompt_with_learnings(channel_config, top_story_types)
    script_data = None
    chosen = None
    skipped = set()

    for attempt in range(5):
        pre_candidate = pick_best_candidate(
            candidates, target="short", used_ids=used_ids | skipped,
            top_story_types=top_story_types
        )
        if pre_candidate is None:
            return {"success": False, "video_url": None, "reason": "no unused candidates"}

        classification = classify_story(pre_candidate)
        target = classification["format"]
        story_type = classification["story_type"]

        candidate = pick_best_candidate(
            candidates, target=target, used_ids=used_ids | skipped,
            top_story_types=top_story_types
        )
        if candidate is None:
            break

        log(f"📖 Attempt ({attempt+1}/5): '{candidate['title'][:55]}' type={story_type} fmt={target}")
        try:
            script_data = _rewriter.rewrite_story(candidate, target=target, prompt_text=prompt_text)
            script_data["story_type"] = story_type
            chosen = candidate
            break
        except (ValueError, RuntimeError) as e:
            log(f"⚠️  Rewrite failed for {candidate['id']}: {e}", level="warning")
            skipped.add(candidate["id"])

    if script_data is None:
        return {"success": False, "video_url": None, "reason": "all 5 candidates failed rewrite"}

    log(f"✍️  Script: {len(script_data['script'].split())} words, mood: {script_data.get('mood','?')}, type: {script_data.get('story_type','?')}")

    # ── Pick voice ────────────────────────────────────────────────────────────
    settings_raw = json.loads((channel_config.channel_dir / "settings.json").read_text())
    voices_config = settings_raw.get("voices", {})
    mood = script_data.get("mood", "dread")
    chosen_voice_id = _rewriter.pick_voice(mood, target=target, voices_config=voices_config)
    log(f"🎤 Voice: {chosen_voice_id} (mood: {mood})")

    # ── Write metadata.json ───────────────────────────────────────────────────
    fmt = VideoFormat.LONG if target == "long" else VideoFormat.SHORT
    metadata = {
        "title": script_data["title"],
        "script": script_data["script"],
        "hashtags": script_data.get("hashtags", ["horror", "scarystories", "dailyygstories"]),
        "topic_cluster": script_data.get("topic_cluster", "paranormal"),
        "hook_overlay": script_data.get("hook_overlay", ""),
        "source_attribution": script_data.get("source_attribution", ""),
        "story_type": script_data.get("story_type", "paranormal"),
        "format": target,
        "hook_pattern_used": script_data.get("hook_pattern_used", ""),
        "title_formula_used": script_data.get("title_formula_used", ""),
    }
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    (outputs_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Audio ─────────────────────────────────────────────────────────────────
    log("🎙️  Generating voiceover...")
    try:
        audio_duration, word_timestamps = generate_audio(
            script=script_data["script"], voice_id=chosen_voice_id
        )
    except Exception as e:
        log(f"❌ Audio failed: {e}", level="error")
        return {"success": False, "video_url": None, "reason": f"audio failed: {e}"}

    # ── Footage ───────────────────────────────────────────────────────────────
    clip_path = None
    story_type = script_data.get("story_type", "paranormal")
    log(f"🎥 Finding footage for story type: {story_type}")
    try:
        clip_path = fetch_matched_footage(
            script_data, story_type, channel_config.footage_dir, fmt=fmt
        )
        if clip_path:
            log(f"✅ Matched footage: {clip_path}")
    except Exception as e:
        log(f"⚠️  Asset matcher failed (non-blocking): {e}", level="warning")

    # ── Video build ───────────────────────────────────────────────────────────
    log("🎬 Building video...")
    try:
        video_path = build_video(
            audio_duration,
            clip_path=clip_path,
            word_timestamps=word_timestamps,
            hook_overlay=metadata["hook_overlay"],
            fmt=fmt,
            channel_config=channel_config,
            script_data=script_data,
            channel_slug=channel_config.slug,
        )
    except Exception as e:
        log(f"❌ Video build failed: {e}", level="error")
        move_outputs_to_archive(run_id)
        return {"success": False, "video_url": None, "reason": f"video build: {e}"}

    # ── Upload ────────────────────────────────────────────────────────────────
    if dry_run or os.environ.get("DAILYYGSTORIES_DRY_RUN"):
        log("🔕 DRY RUN — skipping upload")
        video_url = "https://youtube.com/DRY_RUN"
    else:
        try:
            video_url = upload_youtube(channel_config=channel_config)
            log(f"🎉 Live: {video_url}")
            video_id = video_url.rstrip("/").split("/")[-1]
            track_video(video_id, {**metadata, "format": target})
            state.setdefault("pending_analytics", []).append({
                "video_id": video_id,
                "story_type": story_type,
                "uploaded_at": datetime.now().isoformat(),
            })
        except Exception as e:
            log(f"❌ Upload failed: {e}", level="error")
            move_outputs_to_archive(run_id)
            return {"success": False, "video_url": None, "reason": f"upload: {e}"}

    # ── Save state ────────────────────────────────────────────────────────────
    used_ids.add(chosen["id"])
    state["used_story_ids"] = list(used_ids)
    recent = state.setdefault("recent_runs", [])
    recent.insert(0, {
        "topic_cluster": metadata["topic_cluster"],
        "format": target,
        "run_id": run_id,
        "story_type": story_type,
    })
    state["recent_runs"] = recent[:50]
    atomic_write(state_path, state)
    move_outputs_to_archive(run_id)
    return {"success": True, "video_url": video_url, "reason": None}


if __name__ == "__main__":
    result = run_dailyygstories_pipeline()
    if not result["success"]:
        log(f"❌ Pipeline failed: {result['reason']}", level="error")
        sys.exit(1)
    sys.exit(0)
