#!/usr/bin/env python3
"""
Standalone test for Claude API - generates a short dog fact script
Run: python test_claude_api.py
"""

import json
import os
from dotenv import load_dotenv
import anthropic

def test_claude_api():
    """Test Claude API with a simple dog fact script prompt"""

    # Load .env
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found in .env")
        return False

    print("🚀 Testing Claude API...")
    print(f"API Key: {api_key[:20]}...{api_key[-10:]}")

    try:
        # Create client
        client = anthropic.Anthropic(api_key=api_key)
        print("✅ Client created")

        # Send request
        print("\n📝 Sending prompt to Claude...")
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": """You are a viral YouTube Shorts scriptwriter specializing in dog facts.

Write a 45-second dog fact script that would go VIRAL on YouTube Shorts. Follow these rules:
1. Start with a HOOK as the first sentence (something surprising or emotional)
2. Keep language simple and conversational
3. Include an emotional angle that makes people care
4. End with exactly: "Follow for daily dog facts!"
5. Make it energetic and exciting

Return ONLY valid JSON (no markdown, no extra text) with these exact fields:
{
    "script": "Full 45-second script text here",
    "title": "Clickbait title under 60 chars",
    "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"]
}"""
                }
            ]
        )

        print("✅ Response received")

        # Parse response
        response_text = message.content[0].text
        print(f"\n📋 Raw Response:\n{response_text}\n")

        # Parse JSON
        try:
            result = json.loads(response_text)
            print("✅ JSON parsed successfully\n")

            # Display results
            print("=" * 60)
            print(f"TITLE: {result['title']}")
            print("=" * 60)
            print(f"\nSCRIPT:\n{result['script']}\n")
            print("=" * 60)
            print(f"HASHTAGS: {', '.join(result['hashtags'])}")
            print("=" * 60)

            # Verify required fields
            required = ["script", "title", "hashtags"]
            missing = [f for f in required if f not in result]
            if missing:
                print(f"\n❌ Missing fields: {missing}")
                return False

            print("\n✅ ALL TESTS PASSED - Claude API is working!")
            return True

        except json.JSONDecodeError as e:
            print(f"❌ JSON parse error: {e}")
            return False

    except anthropic.AuthenticationError:
        print("❌ Authentication failed - check ANTHROPIC_API_KEY")
        return False

    except anthropic.RateLimitError:
        print("❌ Rate limit exceeded - wait a moment and try again")
        return False

    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_claude_api()
    exit(0 if success else 1)
