"""
Canine Wisdom Harness — Daily Orchestrator
Replaces main.py as the entry point. Wraps existing pipeline with eval gating.
"""
import sys
import uuid
from datetime import datetime
from pathlib import Path

from generate_audio import generate_audio
from generate_script import generate_script
from build_video import build_video
from upload_youtube import upload_youtube
from utils import init_logger, log, clear_outputs_dir, move_outputs_to_archive

from harness.agents.competitor import bootstrap_competitors_if_needed
from harness.agents.trend import build_topic_queue, pick_best_topic, mark_topic_used
from harness.tools.footage import fetch_footage_for_topic

from harness.evals.audio_eval import audio_eval
from harness.evals.description_eval import description_eval
from harness.evals.hook_eval import hook_eval
from harness.evals.script_eval import script_eval
from harness.evals.thumbnail_eval import thumbnail_eval
from harness.evals.title_eval import title_eval
from harness.evals.video_eval import video_eval
from harness.evals.base import save_eval_result
from harness.storage import atomic_write, atomic_read, DATA_DIR, STATE_PATH

MAX_LLM_RETRIES = 3


def _write_incident(trigger: str, what_failed: str, hypothesis: str, code_path: str) -> str:
    """Write incident report (JSON + MD) to data/incidents/. Returns incident ID."""
    incident_id = f"inc-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    timestamp = datetime.now().isoformat()

    record = {
        "id": incident_id,
        "timestamp": timestamp,
        "trigger": trigger,
        "what_failed": what_failed,
        "hypothesis": hypothesis,
        "code_path": code_path,
        "fix_branch": f"harness-auto-fix/{incident_id}",
        "fix_status": "open",
        "attempts": 0,
        "resolved_at": None,
    }

    incidents_dir = DATA_DIR / "incidents"
    incidents_dir.mkdir(parents=True, exist_ok=True)

    atomic_write(incidents_dir / f"{incident_id}.json", record)

    md_path = incidents_dir / f"{incident_id}.md"
    md_path.write_text(
        f"# Incident: {incident_id}\n\n"
        f"**Timestamp:** {timestamp}\n"
        f"**Trigger:** {trigger}\n"
        f"**What failed:** {what_failed}\n"
        f"**Hypothesis:** {hypothesis}\n"
        f"**Code path:** `{code_path}`\n"
        f"**Status:** open\n",
        encoding="utf-8",
    )

    log(f"📋 Incident written: {incident_id}")
    return incident_id


def _run_competitor_refresh() -> None:
    """Bootstrap channel discovery on first run, then refresh if stale."""
    try:
        bootstrap_competitors_if_needed()
    except Exception as e:
        log(f"⚠️  Competitor bootstrap failed (non-blocking): {e}", level="warning")

    try:
        state = atomic_read(STATE_PATH)
        channel_ids = state.get("competitor_channels", [])
        if not channel_ids:
            log("ℹ️  No competitor channels configured yet — skipping refresh")
            return
        from harness.agents.competitor import run_daily_refresh
        results = run_daily_refresh(channel_ids=channel_ids)
        log(f"📊 Competitor refresh: {results}")
    except Exception as e:
        log(f"⚠️  Competitor refresh failed (non-blocking): {e}", level="warning")


def _run_analytics_pull() -> None:
    """Pull daily analytics snapshots for all tracked videos. Silent on failure."""
    try:
        from harness.agents.analytics import pull_daily_snapshots
        result = pull_daily_snapshots()
        log(f"📈 Analytics pull: {result['pulled']} videos updated")
    except Exception as e:
        log(f"⚠️  Analytics pull failed (non-blocking): {e}", level="warning")


def run_pipeline() -> dict:
    """
    Run the full harness pipeline with eval gating.

    Returns:
        dict with keys: success (bool), video_url (str|None), reason (str|None)
    """
    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    today = datetime.now().strftime("%Y-%m-%d")
    init_logger(run_id)
    log("🚀 Canine Wisdom Harness — starting pipeline")

    clear_outputs_dir()

    try:
        # ── Step 1: Competitor refresh (discovery + staleness check) ──────────
        _run_competitor_refresh()

        # ── Step 2: Build topic queue for today ───────────────────────────────
        log("🔍 Building topic queue...")
        try:
            queue = build_topic_queue(date=today)
            topic_entry = pick_best_topic(queue)
            if topic_entry:
                topic = topic_entry["topic"]
                topic_cluster = topic_entry["topic_cluster"]
                log(f"📌 Topic selected: {topic} [{topic_cluster}]")
            else:
                topic = ""
                topic_cluster = "dog fun"
                log("⚠️  No topics in queue — generating freely")
        except Exception as e:
            log(f"⚠️  Topic queue failed (non-blocking): {e}", level="warning")
            topic = ""
            topic_cluster = "dog fun"
            topic_entry = None

        # ── Step 3: Download topic-matched footage ────────────────────────────
        log(f"🎥 Fetching footage for: {topic or 'general dog'}")
        clip_path = None
        try:
            clip_result = fetch_footage_for_topic(topic_cluster, topic or "dog")
            if clip_result:
                clip_path = str(clip_result)
                log(f"✅ Footage ready: {clip_result.name}")
            else:
                log("⚠️  No footage downloaded — using existing library")
        except Exception as e:
            log(f"⚠️  Footage fetch failed (non-blocking): {e}", level="warning")

        # ── Step 4: Script generation + LLM evals ────────────────────────────
        metadata = None
        hook_result = None
        script_result = None
        title_result = None

        for attempt in range(MAX_LLM_RETRIES):
            metadata = generate_script()
            script_text = metadata["script"]
            title = metadata["title"]

            hook_sentence = script_text.split(".")[0] + "."
            hook_result = hook_eval(hook_sentence)
            save_eval_result(hook_result, run_id)
            if not hook_result.passed:
                log(f"⚠️  hook_eval failed (attempt {attempt + 1}): {hook_result.reasoning}")
                if attempt == MAX_LLM_RETRIES - 1:
                    _write_incident("hook_eval", f"Score {hook_result.score:.1f} after {MAX_LLM_RETRIES} attempts",
                                    hook_result.reasoning, "generate_script.py:prompt")
                    move_outputs_to_archive(run_id)
                    return {"success": False, "video_url": None, "reason": "hook_eval failed after max retries"}
                continue

            script_result = script_eval(script_text, recent_topics=[])
            save_eval_result(script_result, run_id)
            if not script_result.passed:
                log(f"⚠️  script_eval failed (attempt {attempt + 1}): {script_result.reasoning}")
                if attempt == MAX_LLM_RETRIES - 1:
                    _write_incident("script_eval", f"Score {script_result.score:.1f} after {MAX_LLM_RETRIES} attempts",
                                    script_result.reasoning, "generate_script.py:prompt")
                    move_outputs_to_archive(run_id)
                    return {"success": False, "video_url": None, "reason": "script_eval failed after max retries"}
                continue

            title_result = title_eval(title)
            save_eval_result(title_result, run_id)
            if not title_result.passed:
                log(f"⚠️  title_eval failed (attempt {attempt + 1}): {title_result.reasoning}")
                if attempt == MAX_LLM_RETRIES - 1:
                    _write_incident("title_eval", f"Score {title_result.score:.1f} after {MAX_LLM_RETRIES} attempts",
                                    title_result.reasoning, "generate_script.py:prompt")
                    move_outputs_to_archive(run_id)
                    return {"success": False, "video_url": None, "reason": "title_eval failed after max retries"}
                continue

            break

        # ── Step 5: Description eval (non-blocking) ───────────────────────────
        description = metadata.get("description", " ".join(f"#{t}" for t in metadata.get("hashtags", [])))
        desc_result = description_eval(description)
        save_eval_result(desc_result, run_id)
        if not desc_result.passed:
            _write_incident("description_eval", f"Score {desc_result.score:.1f}",
                            desc_result.reasoning, "upload_youtube.py:description")
            log("⚠️  description_eval failed — continuing (non-blocking)")

        # ── Step 6: Thumbnail eval (placeholder) ─────────────────────────────
        thumb_result = thumbnail_eval(variants=[])
        save_eval_result(thumb_result, run_id)

        # ── Step 7: Audio generation + hard eval ─────────────────────────────
        audio_duration = generate_audio()
        audio_path = Path("outputs/voiceover.mp3")
        audio_result = audio_eval(audio_path)
        save_eval_result(audio_result, run_id)
        if not audio_result.passed:
            _write_incident("audio_eval", audio_result.reasoning, "Check ElevenLabs response",
                            "generate_audio.py")
            move_outputs_to_archive(run_id)
            return {"success": False, "video_url": None, "reason": f"audio_eval failed: {audio_result.reasoning}"}

        # ── Step 8: Video build + hard eval ──────────────────────────────────
        video_path = build_video(audio_duration, clip_path=clip_path)
        video_result = video_eval(Path(video_path))
        save_eval_result(video_result, run_id)
        if not video_result.passed:
            _write_incident("video_eval", video_result.reasoning, "Check ffmpeg filter chain",
                            "build_video.py")
            move_outputs_to_archive(run_id)
            return {"success": False, "video_url": None, "reason": f"video_eval failed: {video_result.reasoning}"}

        # ── Step 9: Upload ────────────────────────────────────────────────────
        video_url = upload_youtube()
        video_id = video_url.split("/")[-1]
        log(f"🎉 Short is LIVE: {video_url}")

        # ── Step 10: Post-upload tracking ─────────────────────────────────────
        try:
            from harness.agents.analytics import track_video
            track_video(video_id, {
                "title": metadata.get("title", ""),
                "format": "short",
                "topic": metadata.get("topic", topic),
                "topic_cluster": metadata.get("topic_cluster", topic_cluster),
                "hook_pattern_used": metadata.get("hook_pattern_used", ""),
                "title_formula_used": metadata.get("title_formula_used", ""),
                "eval_scores": {
                    "hook_eval": hook_result.score,
                    "script_eval": script_result.score,
                    "title_eval": title_result.score,
                },
            })
        except Exception as e:
            log(f"⚠️  track_video failed (non-blocking): {e}", level="warning")

        try:
            from harness.tools.learnings import add_covered_topic
            final_topic = metadata.get("topic", topic)
            if final_topic:
                add_covered_topic(final_topic, video_id)
        except Exception as e:
            log(f"⚠️  add_covered_topic failed (non-blocking): {e}", level="warning")

        # Mark topic as used in queue
        if topic_entry:
            try:
                mark_topic_used(today, topic_entry)
            except Exception as e:
                log(f"⚠️  mark_topic_used failed (non-blocking): {e}", level="warning")

        # ── Step 11: Analytics pull ────────────────────────────────────────────
        _run_analytics_pull()

        move_outputs_to_archive(run_id)
        return {"success": True, "video_url": video_url, "reason": None}

    except Exception as exc:
        _write_incident(
            trigger="unhandled_exception",
            what_failed=str(exc),
            hypothesis="Unexpected error in pipeline step",
            code_path="orchestrator.py",
        )
        try:
            move_outputs_to_archive(run_id)
        except Exception:
            pass
        return {"success": False, "video_url": None, "reason": f"unhandled exception: {exc}"}


if __name__ == "__main__":
    result = run_pipeline()
    if not result["success"]:
        log(f"❌ Pipeline failed: {result['reason']}", level="error")
        sys.exit(1)
    sys.exit(0)
