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

from harness.evals.audio_eval import audio_eval
from harness.evals.channel_eval import channel_eval
from harness.evals.description_eval import description_eval
from harness.evals.hook_eval import hook_eval
from harness.evals.script_eval import script_eval
from harness.evals.thumbnail_eval import thumbnail_eval
from harness.evals.title_eval import title_eval
from harness.evals.video_eval import video_eval
from harness.evals.base import save_eval_result
from harness.storage import atomic_write, DATA_DIR

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


def run_pipeline() -> dict:
    """
    Run the full harness pipeline with eval gating.

    Returns:
        dict with keys: success (bool), video_url (str|None), reason (str|None)
    """
    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    init_logger(run_id)
    log("🚀 Canine Wisdom Harness — starting pipeline")

    clear_outputs_dir()
    metadata = None

    # ── Script generation + LLM evals (retry loop) ───────────────────────────
    for attempt in range(MAX_LLM_RETRIES):
        metadata = generate_script()
        script_text = metadata["script"]
        title = metadata["title"]

        # Hook eval — first sentence only
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

        # Script eval
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

        # Title eval
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

        break  # all script LLM evals passed

    # ── Description eval (non-blocking) ──────────────────────────────────────
    description = metadata.get("description", " ".join(f"#{t}" for t in metadata.get("hashtags", [])))
    desc_result = description_eval(description)
    save_eval_result(desc_result, run_id)
    if not desc_result.passed:
        _write_incident("description_eval", f"Score {desc_result.score:.1f}",
                        desc_result.reasoning, "upload_youtube.py:description")
        log("⚠️  description_eval failed — continuing (non-blocking)")

    # ── Thumbnail eval (placeholder) ──────────────────────────────────────────
    thumb_result = thumbnail_eval(variants=[])
    save_eval_result(thumb_result, run_id)

    # ── Audio generation + hard eval ─────────────────────────────────────────
    audio_duration = generate_audio()
    audio_path = Path("outputs/voiceover.mp3")
    audio_result = audio_eval(audio_path)
    save_eval_result(audio_result, run_id)
    if not audio_result.passed:
        _write_incident("audio_eval", audio_result.reasoning, "Check ElevenLabs response",
                        "generate_audio.py")
        move_outputs_to_archive(run_id)
        return {"success": False, "video_url": None, "reason": f"audio_eval failed: {audio_result.reasoning}"}

    # ── Video build + hard eval ───────────────────────────────────────────────
    video_path = build_video(audio_duration)
    video_result = video_eval(Path(video_path))
    save_eval_result(video_result, run_id)
    if not video_result.passed:
        _write_incident("video_eval", video_result.reasoning, "Check ffmpeg filter chain",
                        "build_video.py")
        move_outputs_to_archive(run_id)
        return {"success": False, "video_url": None, "reason": f"video_eval failed: {video_result.reasoning}"}

    # ── Upload ────────────────────────────────────────────────────────────────
    video_url = upload_youtube()
    log(f"🎉 Short is LIVE: {video_url}")

    move_outputs_to_archive(run_id)
    return {"success": True, "video_url": video_url, "reason": None}


if __name__ == "__main__":
    result = run_pipeline()
    if not result["success"]:
        log(f"❌ Pipeline failed: {result['reason']}", level="error")
        sys.exit(1)
    sys.exit(0)
