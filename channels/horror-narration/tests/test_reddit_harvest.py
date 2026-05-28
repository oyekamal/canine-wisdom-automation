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


def test_harvest_skips_removed_text(reddit_harvest):
    post = _make_post(text="[removed]")
    fake_resp = MagicMock()
    fake_resp.json.return_value = _make_reddit_response([post])
    fake_resp.status_code = 200

    with patch("requests.get", return_value=fake_resp):
        stories = reddit_harvest.harvest_subreddit("nosleep", limit=5, min_upvotes=100, min_comments=10)
    assert stories == []


def test_extract_media_detects_image_post(reddit_harvest):
    """Posts from i.redd.it with post_hint=image are detected as images."""
    post = {
        "url": "https://i.redd.it/abc123.jpg",
        "domain": "i.redd.it",
        "post_hint": "image",
        "is_video": False,
    }
    result = reddit_harvest._detect_media(post)
    assert result is not None
    assert result["type"] == "image"
    assert result["url"] == "https://i.redd.it/abc123.jpg"


def test_extract_media_detects_imgur(reddit_harvest):
    """Imgur image domains are detected."""
    post = {
        "url": "https://i.imgur.com/xyz.jpg",
        "domain": "i.imgur.com",
        "post_hint": "image",
        "is_video": False,
    }
    result = reddit_harvest._detect_media(post)
    assert result is not None
    assert result["type"] == "image"


def test_extract_media_detects_reddit_video(reddit_harvest):
    """v.redd.it posts are detected as video."""
    post = {
        "url": "https://v.redd.it/abc123",
        "domain": "v.redd.it",
        "post_hint": "hosted:video",
        "is_video": True,
    }
    result = reddit_harvest._detect_media(post)
    assert result is not None
    assert result["type"] == "video"
    assert result["url"] == "https://v.redd.it/abc123"


def test_extract_media_returns_none_for_text_post(reddit_harvest):
    """Text-only posts return None."""
    post = {
        "url": "https://www.reddit.com/r/nosleep/comments/abc/title/",
        "domain": "self.nosleep",
        "post_hint": "self",
        "is_video": False,
    }
    result = reddit_harvest._detect_media(post)
    assert result is None


def test_extract_media_returns_none_for_external_link(reddit_harvest):
    """External links (not image/video domains) return None."""
    post = {
        "url": "https://www.youtube.com/watch?v=abc",
        "domain": "youtube.com",
        "post_hint": "rich:video",
        "is_video": False,
    }
    result = reddit_harvest._detect_media(post)
    assert result is None


def test_download_reddit_image_saves_file(reddit_harvest, tmp_path):
    """_download_reddit_image saves image bytes to disk."""
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.content = b"\xff\xd8\xff" + b"x" * 5000  # fake JPEG bytes

    with patch("requests.get", return_value=fake_resp):
        output = tmp_path / "test_image.jpg"
        result = reddit_harvest._download_reddit_image("https://i.redd.it/fake.jpg", output)

    assert result is True
    assert output.exists()
    assert output.stat().st_size > 0
