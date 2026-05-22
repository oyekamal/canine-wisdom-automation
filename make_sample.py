#!/usr/bin/env python3
"""
One-shot sample video generator for client style approval.

Runs the full pipeline (script -> audio -> video) but skips YouTube upload.
Output: outputs/sample_<date>.mp4

Usage:
    python make_sample.py
"""

import shutil
import sys
from datetime import datetime
from config import load_config
from utils import init_logger, log, clear_outputs_dir
from generate_script import generate_script
from generate_audio import generate_audio
from build_video import build_video


def main():
    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    init_logger(run_id)

    log("🎬 SAMPLE VIDEO GENERATOR — new 2026 style")
    log("=" * 50)

    try:
        load_config()
        clear_outputs_dir()

        log("")
        metadata = generate_script()
        log(f"📋 Script ({len(metadata['script'].split())} words): {metadata['script'][:80]}...")
        log(f"🎯 Hook overlay: {metadata.get('hook_overlay', 'N/A')}")

        log("")
        audio_duration, word_timestamps = generate_audio()
        log(f"🎙️ Audio: {audio_duration:.1f}s, {len(word_timestamps)} words with timestamps")

        log("")
        video_path = build_video(
            audio_duration,
            word_timestamps=word_timestamps,
            hook_overlay=metadata.get("hook_overlay"),
        )

        sample_name = f"outputs/sample_{datetime.now().strftime('%Y-%m-%d')}.mp4"
        shutil.copy(video_path, sample_name)

        log("")
        log("=" * 50)
        log(f"✅ SAMPLE READY: {sample_name}")
        log("📺 Open this file to review the new style before enabling daily publishing.")
        log(f"📝 Title: {metadata['title']}")
        log(f"⏱️  Duration: {audio_duration:.1f}s")

        return 0

    except Exception as e:
        log(f"❌ Sample generation failed: {e}", level="error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
