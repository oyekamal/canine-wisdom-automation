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


def _make_post(id="abc", title="Something in the dark", text="word " * 100,
               author="testuser", score=1500, comments=120):
    return {
        "kind": "t3",
        "data": {
            "id": id,
            "title": title,
            "selftext": text,
            "author": author,
            "score": score,
            "num_comments": comments,
            "permalink": f"/r/nosleep/comments/{id}/title/",
        }
    }


def _make_reddit_response(posts):
    return {"data": {"children": posts}}


@pytest.fixture
def reddit_harvest():
    """Load the reddit_harvest module by file path."""
    module_path = Path(__file__).parent.parent / "harness" / "reddit_harvest.py"
    return _load_module(str(module_path), "reddit_harvest")


def test_harvest_subreddit_returns_story_dicts(reddit_harvest):
    posts = [_make_post()]
    fake_resp = MagicMock()
    fake_resp.json.return_value = _make_reddit_response(posts)
    fake_resp.status_code = 200

    with patch("requests.get", return_value=fake_resp):
        stories = reddit_harvest.harvest_subreddit("nosleep", limit=5, min_upvotes=100, min_comments=10)

    assert len(stories) == 1
    s = stories[0]
    assert s["id"] == "abc"
    assert s["title"] == "Something in the dark"
    assert s["author"] == "testuser"
    assert s["subreddit"] == "nosleep"
    assert s["score"] == 1500
    assert "word_count" in s
    assert "url" in s


def test_harvest_skips_deleted_author(reddit_harvest):
    post = _make_post()
    post["data"]["author"] = "[deleted]"
    fake_resp = MagicMock()
    fake_resp.json.return_value = _make_reddit_response([post])
    fake_resp.status_code = 200

    with patch("requests.get", return_value=fake_resp):
        stories = reddit_harvest.harvest_subreddit("nosleep", limit=5, min_upvotes=100, min_comments=10)
    assert stories == []


def test_harvest_skips_below_min_upvotes(reddit_harvest):
    post = _make_post(score=50)
    fake_resp = MagicMock()
    fake_resp.json.return_value = _make_reddit_response([post])
    fake_resp.status_code = 200

    with patch("requests.get", return_value=fake_resp):
        stories = reddit_harvest.harvest_subreddit("nosleep", limit=5, min_upvotes=500, min_comments=10)
    assert stories == []


def test_harvest_skips_opted_out_authors(reddit_harvest):
    post = _make_post(author="banned_user")
    fake_resp = MagicMock()
    fake_resp.json.return_value = _make_reddit_response([post])
    fake_resp.status_code = 200

    with patch("requests.get", return_value=fake_resp):
        stories = reddit_harvest.harvest_subreddit("nosleep", limit=5, min_upvotes=100, min_comments=10,
                                     opt_out_authors=["banned_user"])
    assert stories == []


def test_harvest_channel_combines_subreddits(reddit_harvest):
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from channel_config import load_channel_config

    cfg = load_channel_config("horror-narration")
    post = _make_post()
    fake_resp = MagicMock()
    fake_resp.json.return_value = _make_reddit_response([post])
    fake_resp.status_code = 200

    with patch("requests.get", return_value=fake_resp):
        stories = reddit_harvest.harvest_channel(cfg)

    # 5 subreddits (3 primary + 2 secondary), each returning 1 post (same id, deduped)
    assert len(stories) == 1
