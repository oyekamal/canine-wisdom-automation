#!/usr/bin/env python3
"""
Multi-channel YouTube Shorts automation pipeline.
Runs all active channels sequentially on each invocation.
"""

import sys
from datetime import datetime
from channel_config import load_channel_config
from utils import init_logger, log, clear_outputs_dir, move_outputs_to_archive
from generate_script import generate_script
from generate_audio import generate_audio
from build_video import build_video
from upload_youtube import upload_youtube

ACTIVE_CHANNELS = ["canine-wisdom", "horror-narration"]


def run_channel_pipeline(slug: str, run_id: str) -> None:
    """Run the full pipeline for a single channel slug."""
    log(f"\n{'='*60}")
    log(f"📺 Starting pipeline for channel: {slug}")
    log(f"{'='*60}")

    channel_config = load_channel_config(slug)

    clear_outputs_dir()

    # Step 1: Script
    log("")
    metadata = generate_script(channel_config=channel_config)

    # Step 2: Audio
    log("")
    audio_duration, word_timestamps = generate_audio(channel_config=channel_config)

    # Step 3: Video
    log("")
    video_path = build_video(
        audio_duration,
        word_timestamps=word_timestamps,
        script_data=metadata,
        channel_config=channel_config,
        channel_slug=slug,
    )

    # Step 4: Upload
    log("")
    try:
        video_url = upload_youtube(channel_config=channel_config)
        log("")
        log(f"🎉 [{slug}] Short is LIVE!")
        log(f"📺 Watch here: {video_url}")
    except FileNotFoundError:
        log(f"⏭️  [{slug}] YouTube upload skipped (credentials not found)")
        log(f"   Video ready at: outputs/final_video.mp4")

    log("")
    move_outputs_to_archive(f"{run_id}_{slug}")


def main() -> int:
    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    init_logger(run_id)

    log("🚀 Multi-Channel YouTube Shorts Pipeline")
    log(f"📋 Active channels: {', '.join(ACTIVE_CHANNELS)}")

    failed = []
    for slug in ACTIVE_CHANNELS:
        try:
            run_channel_pipeline(slug, run_id)
        except KeyboardInterrupt:
            log("❌ Pipeline interrupted by user")
            return 1
        except Exception as e:
            log(f"❌ [{slug}] Pipeline failed: {str(e)}", level="error")
            log(f"📋 Check run_logs/ for details")
            failed.append(slug)
            continue

    if failed:
        log(f"\n⚠️  Failed channels: {', '.join(failed)}")
        return 1

    log(f"\n✅ All {len(ACTIVE_CHANNELS)} channels complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
