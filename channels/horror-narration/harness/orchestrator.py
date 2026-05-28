"""
Horror-Narration Channel Orchestrator
Run with: python -m harness.orchestrator --channel horror-narration
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Ensure repo root is importable
sys.path.insert(0, str(Path(__file__).parents[3]))

from channel_config import load_channel_config
from generate_audio import generate_audio
from build_video import build_video
from upload_youtube import upload_youtube
from utils import init_logger, log, clear_outputs_dir, move_outputs_to_archive
from harness.storage import atomic_write, atomic_read, get_state_path
from harness.evals.audio_eval import audio_eval
from harness.evals.video_eval import video_eval
from harness.evals.base import save_eval_result
from harness.agents.format_picker import pick_format
from harness.tools.footage import fetch_footage_for_topic
from config import VideoFormat

import importlib.util as _ilu

def _load(name, rel):
    p = Path(__file__).parent / rel
    spec = _ilu.spec_from_file_location(name, p)
    m = _ilu.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

_harvest_mod = _load("reddit_harvest", "reddit_harvest.py")
_scorer_mod  = _load("story_scorer",   "story_scorer.py")
_rewriter_mod = _load("story_rewriter", "story_rewriter.py")

harvest_channel = _harvest_mod.harvest_channel
pick_best_story = _scorer_mod.pick_best_story
rewrite_story   = _rewriter_mod.rewrite_story
pick_voice      = _rewriter_mod.pick_voice


def run_horror_pipeline(channel_config=None) -> dict:
    if channel_config is None:
        channel_config = load_channel_config("horror-narration")

    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    init_logger(run_id)
    log(f"🕯️  Horror Narration Harness — starting [{channel_config.slug}]")
    clear_outputs_dir()

    state_path = get_state_path(channel_config)
    try:
        state = atomic_read(state_path)
    except FileNotFoundError:
        state = {}

    used_ids = set(state.get("used_story_ids", []))
    recent_runs = state.get("recent_runs", [])

    # ── Format decision ───────────────────────────────────────────────────────
    fmt = pick_format("nosleep", recent_runs)
    target = "long" if fmt == VideoFormat.LONG else "short"
    log(f"🎬 Format: {fmt.value} / target: {target}")

    # ── Harvest stories ───────────────────────────────────────────────────────
    log("🕸️  Harvesting Reddit stories...")
    try:
        stories = harvest_channel(channel_config)
        log(f"📚 Harvested {len(stories)} stories")
    except Exception as e:
        log(f"❌ Harvest failed: {e}", level="error")
        return {"success": False, "video_url": None, "reason": f"harvest failed: {e}"}

    if not stories:
        return {"success": False, "video_url": None, "reason": "no stories harvested"}

    # ── Pick best story + rewrite with Claude (try up to 5 stories) ──────────
    prompt_text = channel_config.prompt_path.read_text(encoding="utf-8")
    script_data = None
    story = None
    skipped_ids = set()

    for attempt in range(5):
        candidate = pick_best_story(stories, target=target, used_ids=used_ids | skipped_ids)
        if candidate is None:
            return {"success": False, "video_url": None, "reason": "no unused stories available"}
        log(f"📖 Trying ({attempt+1}/5): '{candidate['title'][:55]}' by u/{candidate['author']}")
        try:
            script_data = rewrite_story(candidate, target=target, prompt_text=prompt_text)
            story = candidate
            break
        except ValueError as e:
            log(f"⚠️  Policy declined story {candidate['id']} — trying next", level="warning")
            skipped_ids.add(candidate["id"])
        except RuntimeError as e:
            log(f"⚠️  API error on story {candidate['id']} — trying next", level="warning")
            skipped_ids.add(candidate["id"])

    if script_data is None:
        return {"success": False, "video_url": None, "reason": "all 5 story candidates failed rewrite"}
    log(f"✍️  Script: {len(script_data['script'].split())} words, mood: {script_data.get('mood', '?')}")

    # ── Pick voice based on mood ──────────────────────────────────────────────
    import json as _json
    settings_raw = _json.loads((channel_config.channel_dir / "settings.json").read_text())
    voices_config = settings_raw.get("voices", {})
    mood = script_data.get("mood", "dread")
    chosen_voice_id = pick_voice(mood, target=target, voices_config=voices_config)
    log(f"🎤 Voice selected: {chosen_voice_id} (mood: {mood})")

    # ── Write metadata.json for upload_youtube ────────────────────────────────
    metadata = {
        "title": script_data["title"],
        "script": script_data["script"],
        "hashtags": script_data.get("hashtags", ["horror", "scarystories"]),
        "topic_cluster": script_data.get("topic_cluster", "nosleep"),
        "hook_overlay": script_data.get("hook_overlay", ""),
        "source_attribution": script_data.get("source_attribution", ""),
    }
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)
    (outputs_dir / "metadata.json").write_text(
        _json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Audio generation ──────────────────────────────────────────────────────
    log("🎙️  Generating voiceover...")
    try:
        audio_duration, word_timestamps = generate_audio(
            script=script_data["script"],
            voice_id=chosen_voice_id,
        )
    except Exception as e:
        log(f"❌ Audio failed: {e}", level="error")
        return {"success": False, "video_url": None, "reason": f"audio failed: {e}"}

    audio_path = Path("outputs/voiceover.mp3")
    audio_result = audio_eval(audio_path)
    save_eval_result(audio_result, run_id)
    if not audio_result.passed:
        move_outputs_to_archive(run_id)
        return {"success": False, "video_url": None, "reason": "audio_eval failed"}

    # ── Fetch story-matched footage ───────────────────────────────────────────
    topic_cluster = metadata["topic_cluster"]
    clip_path = None
    log(f"🎥 Fetching footage for topic: {topic_cluster}")
    try:
        clip_result = fetch_footage_for_topic(topic_cluster, topic_cluster, fmt=fmt,
                                               save_dir=channel_config.footage_dir)
        if clip_result:
            clip_path = str(clip_result)
            log(f"✅ Footage ready: {clip_result.name}")
        else:
            log("⚠️  No footage downloaded — using existing library")
    except Exception as e:
        log(f"⚠️  Footage fetch failed (non-blocking): {e}", level="warning")

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
        )
    except Exception as e:
        log(f"❌ Video build failed: {e}", level="error")
        move_outputs_to_archive(run_id)
        return {"success": False, "video_url": None, "reason": f"video build failed: {e}"}

    video_result = video_eval(Path(video_path), fmt=fmt)
    save_eval_result(video_result, run_id)
    if not video_result.passed:
        move_outputs_to_archive(run_id)
        return {"success": False, "video_url": None, "reason": f"video_eval failed: {video_result.reasoning}"}

    # ── Upload (skip if HORROR_DRY_RUN=1) ────────────────────────────────────
    import os as _os
    if _os.environ.get("HORROR_DRY_RUN"):
        log("🔕 DRY RUN — skipping YouTube upload")
        video_url = "https://youtube.com/shorts/DRY_RUN"
    else:
        try:
            video_url = upload_youtube(channel_config=channel_config)
        except Exception as e:
            log(f"❌ Upload failed: {e}", level="error")
            move_outputs_to_archive(run_id)
            return {"success": False, "video_url": None, "reason": f"upload failed: {e}"}

    log(f"🎉 Live: {video_url}")

    # ── Save state ────────────────────────────────────────────────────────────
    used_ids.add(story["id"])
    state["used_story_ids"] = list(used_ids)
    recent = state.setdefault("recent_runs", [])
    recent.insert(0, {
        "topic_cluster": metadata["topic_cluster"],
        "format": fmt.value,
        "run_id": run_id,
    })
    state["recent_runs"] = recent[:50]
    atomic_write(state_path, state)

    move_outputs_to_archive(run_id)
    return {"success": True, "video_url": video_url, "reason": None}


if __name__ == "__main__":
    result = run_horror_pipeline()
    if not result["success"]:
        log(f"❌ Pipeline failed: {result['reason']}", level="error")
        sys.exit(1)
    sys.exit(0)
