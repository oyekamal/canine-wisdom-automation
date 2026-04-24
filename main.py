#!/usr/bin/env python3
"""
Canine Wisdom by King — YouTube Shorts Automation Pipeline
Master runner that orchestrates all four steps.
"""

import sys
from datetime import datetime
from pathlib import Path
from config import load_config
from utils import init_logger, log, clear_outputs_dir, move_outputs_to_archive
from generate_script import generate_script
from generate_audio import generate_audio
from build_video import build_video
from upload_youtube import upload_youtube


def main():
    """Run the complete pipeline from script generation to YouTube upload."""

    # Initialize logger with timestamp (format: YYYY-MM-DD_HH-MM-SS)
    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    init_logger(run_id)

    try:
        # ====================================================================
        # VALIDATION PHASE
        # ====================================================================

        log("🚀 Canine Wisdom — VIRAL SHORTS Pipeline")
        log("Validating configuration...")

        # Validate configuration (loads environment and paths)
        config = load_config()
        log("✅ Configuration valid")

        # Clear outputs from previous run
        log("Clearing previous outputs...")
        clear_outputs_dir()
        log("✅ Outputs directory cleared")

        # ====================================================================
        # EXECUTION PHASE - Four-Step Pipeline
        # ====================================================================

        # Step 1: Generate script
        log("")
        metadata = generate_script()

        # Step 2: Generate audio
        log("")
        audio_duration = generate_audio()

        # Step 3: Build video
        log("")
        video_path = build_video()

        # Step 4: Upload to YouTube
        log("")
        video_url = upload_youtube()

        # ====================================================================
        # ARCHIVAL & CLEANUP PHASE
        # ====================================================================

        log("")
        move_outputs_to_archive(run_id)

        # ====================================================================
        # SUCCESS
        # ====================================================================

        log("")
        log("🎉 Your Short is LIVE! Go check your channel!")
        log(f"📺 Watch here: {video_url}")

        return 0

    except KeyboardInterrupt:
        log("❌ Pipeline interrupted by user")
        return 1

    except Exception as e:
        log(f"❌ Pipeline failed: {str(e)}", level="error")
        log(f"📋 Check run_logs/ for details")
        return 1


if __name__ == "__main__":
    sys.exit(main())
