#!/usr/bin/env python3
"""
Diagnostic tool for video building issues
Checks video file sizes, duration, and ffmpeg compatibility
Run: python diagnose_video_issue.py
"""

import subprocess
from pathlib import Path
import json

def get_video_info(video_path):
    """Get info about video using ffprobe"""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_format",
            "-show_streams",
            "-of", "json",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except:
        return None

def check_dog_footage():
    """Check all video files in dog_footage/"""
    dog_dir = Path("dog_footage")

    if not dog_dir.exists():
        print("❌ dog_footage/ folder not found")
        return

    videos = list(dog_dir.glob("*.mp4")) + list(dog_dir.glob("*.mov"))

    if not videos:
        print("❌ No video files found in dog_footage/")
        return

    print(f"✅ Found {len(videos)} video file(s)\n")

    for video_path in videos:
        file_size_mb = video_path.stat().st_size / (1024 * 1024)
        print(f"📹 {video_path.name}")
        print(f"   📊 Size: {file_size_mb:.1f} MB")

        # Get video duration and resolution
        info = get_video_info(video_path)
        if info:
            # Find video stream
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    duration = float(info.get("format", {}).get("duration", 0))
                    width = stream.get("width")
                    height = stream.get("height")
                    print(f"   ⏱️  Duration: {duration:.1f} seconds")
                    print(f"   📐 Resolution: {width}x{height}")

                    # Warnings
                    if file_size_mb > 500:
                        print(f"   ⚠️  LARGE FILE! May cause memory issues during processing")
                    if duration < 60:
                        print(f"   ⚠️  Video is shorter than 60 seconds (may not loop well)")
                    break
        print()

def check_ffmpeg():
    """Check if ffmpeg is installed"""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✅ ffmpeg is installed: {version_line}")
            return True
    except:
        pass

    print("❌ ffmpeg not found. Install with:")
    print("   Mac: brew install ffmpeg")
    print("   Linux: sudo apt install ffmpeg")
    print("   Windows: download from ffmpeg.org")
    return False

def check_voiceover():
    """Check if voiceover.mp3 exists"""
    audio_path = Path("outputs/voiceover.mp3")
    if audio_path.exists():
        size_mb = audio_path.stat().st_size / (1024 * 1024)
        print(f"✅ outputs/voiceover.mp3 exists ({size_mb:.2f} MB)")
        return True
    else:
        print("❌ outputs/voiceover.mp3 not found - run Step 2 first")
        return False

def main():
    print("=" * 60)
    print("VIDEO BUILD DIAGNOSTICS")
    print("=" * 60)
    print()

    # Check ffmpeg
    print("1️⃣  CHECKING FFMPEG...")
    print("-" * 60)
    has_ffmpeg = check_ffmpeg()
    print()

    # Check voiceover
    print("2️⃣  CHECKING VOICEOVER...")
    print("-" * 60)
    has_audio = check_voiceover()
    print()

    # Check dog footage
    print("3️⃣  CHECKING DOG FOOTAGE...")
    print("-" * 60)
    check_dog_footage()

    print("=" * 60)
    print("\n💡 RECOMMENDATIONS:")
    print("-" * 60)

    if not has_ffmpeg:
        print("❌ Install ffmpeg before running video build")
        return

    if not has_audio:
        print("❌ Generate voiceover first (run: python test_elevenlabs_api.py)")
        return

    dog_dir = Path("dog_footage")
    videos = list(dog_dir.glob("*.mp4")) + list(dog_dir.glob("*.mov"))

    if not videos:
        print("❌ Add video files to dog_footage/ folder")
        return

    # Check for large files
    large_files = [v for v in videos if v.stat().st_size > 500 * 1024 * 1024]
    if large_files:
        print("\n⚠️  LARGE VIDEO FILES DETECTED")
        print("   Your video file(s) are over 500 MB")
        print("   This may cause:")
        print("   - High CPU usage during encoding")
        print("   - Laptop getting hot/shutting down")
        print("   - Long processing time (30+ minutes)")
        print("\n   SOLUTION:")
        print("   1. Compress video before using:")
        print("      ffmpeg -i input.mp4 -crf 28 -preset medium output.mp4")
        print("   2. Or resize to smaller resolution:")
        print("      ffmpeg -i input.mp4 -vf scale=540:960 output.mp4")
        print("   3. Or use shorter clips (30-60 seconds instead of minutes)")
        return

    # Ready to build
    print("\n✅ Everything looks good! You can now run:")
    print("   python build_video.py")
    print("\nOr test the full pipeline:")
    print("   python main.py")

if __name__ == "__main__":
    main()
