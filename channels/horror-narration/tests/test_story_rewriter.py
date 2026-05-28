import json
import pytest
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock


def _load_module(module_path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def story_rewriter():
    """Load the story_rewriter module by file path."""
    module_path = Path(__file__).parent.parent / "harness" / "story_rewriter.py"
    return _load_module(str(module_path), "story_rewriter")


def _make_story():
    return {
        "id": "abc123", "title": "I found something in the woods",
        "text": "It started on a Tuesday. " * 50,
        "author": "author1", "subreddit": "nosleep", "score": 2000,
        "num_comments": 150, "url": "https://www.reddit.com/r/nosleep/abc123/",
        "word_count": 250,
    }


def test_rewrite_returns_required_fields(story_rewriter):
    fake_response = {
        "script": "The darkness had been following him for weeks.",
        "title": "What was following him home",
        "hook_overlay": "SOMETHING WAS FOLLOWING HIM",
        "hashtags": ["horror", "nosleep"],
        "topic_cluster": "nosleep",
        "mood": "dread",
        "source_attribution": "Inspired by u/author1 on r/nosleep",
        "format": "short",
    }
    with patch("anthropic.Anthropic") as mock_client:
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=json.dumps(fake_response))]
        mock_client.return_value.messages.create.return_value = mock_msg
        result = story_rewriter.rewrite_story(_make_story(), target="short", prompt_text="rewrite this")
    assert result["script"] == fake_response["script"]
    assert result["title"] == fake_response["title"]
    assert result["mood"] == "dread"
    assert result["source_attribution"] == fake_response["source_attribution"]


def test_rewrite_raises_on_policy_error(story_rewriter):
    with patch("anthropic.Anthropic") as mock_client:
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=json.dumps({"error": "policy"}))]
        mock_client.return_value.messages.create.return_value = mock_msg
        with pytest.raises(ValueError, match="policy"):
            story_rewriter.rewrite_story(_make_story(), target="short", prompt_text="rewrite")


def test_build_rewrite_prompt_includes_story_details(story_rewriter):
    story = _make_story()
    prompt = story_rewriter._build_rewrite_prompt(story, target="short")
    assert story["text"][:30] in prompt
    assert story["url"] in prompt
    assert story["author"] in prompt


def test_pick_voice_dread_returns_george(story_rewriter):
    voice_id = story_rewriter.pick_voice("dread", target="long", voices_config={
        "long_form_narrator": "JBFqnCBsd6RMkjVDRZzb",
        "short_creepy": "N2lVS1w4EtoT3dr4eOWO",
        "intense": "SOYHLrjzK2X1ezoPC6cr",
        "paranormal_female": "EXAVITQu4vr4xnSDxMaL",
    })
    assert voice_id == "JBFqnCBsd6RMkjVDRZzb"


def test_pick_voice_intense_returns_harry(story_rewriter):
    voice_id = story_rewriter.pick_voice("intense", target="short", voices_config={
        "long_form_narrator": "JBFqnCBsd6RMkjVDRZzb",
        "short_creepy": "N2lVS1w4EtoT3dr4eOWO",
        "intense": "SOYHLrjzK2X1ezoPC6cr",
        "paranormal_female": "EXAVITQu4vr4xnSDxMaL",
    })
    assert voice_id == "SOYHLrjzK2X1ezoPC6cr"


def test_pick_voice_eerie_short_returns_callum(story_rewriter):
    voice_id = story_rewriter.pick_voice("eerie", target="short", voices_config={
        "long_form_narrator": "JBFqnCBsd6RMkjVDRZzb",
        "short_creepy": "N2lVS1w4EtoT3dr4eOWO",
        "intense": "SOYHLrjzK2X1ezoPC6cr",
        "paranormal_female": "EXAVITQu4vr4xnSDxMaL",
    })
    assert voice_id == "N2lVS1w4EtoT3dr4eOWO"
