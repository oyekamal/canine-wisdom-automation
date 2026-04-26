#!/usr/bin/env python3
"""
Standalone test for ElevenLabs API - generates voiceover from script
Run: python test_elevenlabs_api.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import requests

def test_elevenlabs_api():
    """Test ElevenLabs API with a script"""

    # Load .env
    load_dotenv()
    api_key = os.getenv("ELEVENLABS_API_KEY")
    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "pNInz6obpgDQGcFmaJgB")

    if not api_key:
        print("❌ ELEVENLABS_API_KEY not found in .env")
        return False

    print("🚀 Testing ElevenLabs API...")
    print(f"API Key: {api_key[:20]}...{api_key[-10:]}")
    print(f"Voice ID: {voice_id}")

    # Get script text
    script_file = Path("outputs/script.txt")
    if script_file.exists():
        script_text = script_file.read_text()
        print(f"\n📖 Using script from outputs/script.txt ({len(script_text)} chars)")
    else:
        # Use a sample script if file doesn't exist
        script_text = """Did you know? Dogs can see in color! Their vision is different from ours, but they definitely see the world in color, not black and white. Pretty amazing, right? Follow for daily dog facts!"""
        print(f"\n📖 Using sample script ({len(script_text)} chars)")

    print(f"Script: {script_text[:100]}...\n")

    try:
        # Construct URL
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        print(f"🔗 Calling: {url}")

        # Prepare headers
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json"
        }

        # Prepare request body
        data = {
            "text": script_text,
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.8,
                "style": 0.6,
                "use_speaker_boost": True
            }
        }

        print("📤 Sending request to ElevenLabs...")

        # Send request
        response = requests.post(url, headers=headers, json=data, timeout=30)

        print(f"📊 Status: {response.status_code}")

        if response.status_code != 200:
            error_msg = response.text
            if response.status_code == 401:
                print("❌ Authentication failed - check ELEVENLABS_API_KEY")
            elif response.status_code == 400:
                print(f"❌ Bad request: {error_msg}")
            else:
                print(f"❌ Error {response.status_code}: {error_msg}")
            return False

        # Save audio
        audio_data = response.content
        audio_size_kb = len(audio_data) / 1024
        audio_path = Path("outputs/voiceover.mp3")

        # Ensure outputs directory exists
        audio_path.parent.mkdir(exist_ok=True)

        audio_path.write_bytes(audio_data)
        print(f"\n✅ Audio generated: {audio_path}")
        print(f"📦 File size: {audio_size_kb:.1f} KB")

        # Estimate duration
        estimated_duration = audio_size_kb / 24  # 192kbps = 24 KB/sec
        print(f"⏱️  Estimated duration: {estimated_duration:.1f} seconds")

        print("\n✅ ALL TESTS PASSED - ElevenLabs API is working!")
        return True

    except requests.exceptions.Timeout:
        print("❌ Request timeout - ElevenLabs took too long to respond")
        return False

    except requests.exceptions.ConnectionError:
        print("❌ Connection error - check internet connection")
        return False

    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_elevenlabs_api()
    exit(0 if success else 1)
