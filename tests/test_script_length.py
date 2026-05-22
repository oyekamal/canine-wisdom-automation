import pytest
from unittest.mock import patch, MagicMock
import json

SAMPLE_METADATA = {
    "script": "STOP doing this when your dog jumps on you. Every time you push them down, you're rewarding them with touch. Instead, turn your back completely and ignore them for 10 seconds. Dogs hate being ignored more than any punishment. Three days of this and the jumping stops for good. Follow for daily dog facts!",
    "title": "Why Your Dog Still Jumps On You",
    "hook_overlay": "STOP DOING THIS",
    "hashtags": ["dogs", "dogtraining", "dogfacts", "puppy", "dogowner", "dogshorts", "doglover", "dogmom", "dogdad", "doglife"],
    "topic": "jumping behavior fix",
    "topic_cluster": "dog training",
    "hook_pattern_used": "STOP doing [common mistake]",
    "title_formula_used": "Why Your Dog [common problem]"
}

def test_script_word_count_in_range():
    words = SAMPLE_METADATA["script"].split()
    assert 54 <= len(words) <= 76, f"Word count {len(words)} out of range 54-76"

def test_hook_overlay_is_caps():
    overlay = SAMPLE_METADATA["hook_overlay"]
    assert overlay == overlay.upper(), "hook_overlay must be all caps"

def test_hook_overlay_word_count():
    words = SAMPLE_METADATA["hook_overlay"].split()
    assert 3 <= len(words) <= 6, f"hook_overlay word count {len(words)} must be 3-6"
