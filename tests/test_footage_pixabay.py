from unittest.mock import patch, MagicMock

from harness.tools.footage import TOPIC_SEARCH_MAP


def test_queries_match_todd_examples():
    """Queries must be phrase-level specific per client request."""
    all_queries = [q for queries in TOPIC_SEARCH_MAP.values() for q in queries]
    assert any("panting" in q for q in all_queries), "Missing anxiety+panting query"
    assert any("trick" in q or "learning" in q for q in all_queries), "Missing puppy learning tricks"
    assert any("veterinarian" in q or "vet" in q.lower() for q in all_queries), "Missing vet query"


def test_all_queries_at_least_two_words():
    for cluster, queries in TOPIC_SEARCH_MAP.items():
        for q in queries:
            assert len(q.split()) >= 2, f"Too short: '{q}' in {cluster}"


def test_no_generic_single_word_queries():
    bad = {"dog", "puppy", "vet", "training", "fun"}
    for cluster, queries in TOPIC_SEARCH_MAP.items():
        for q in queries:
            assert q.lower() not in bad, f"Generic query '{q}' in {cluster}"


def test_pixabay_key_returns_none_or_string():
    from harness.tools.footage import _load_pixabay_key
    result = _load_pixabay_key()
    assert result is None or isinstance(result, str)


def test_search_pixabay_returns_clip_dicts():
    from harness.tools.footage import _search_pixabay

    mock_response = {
        "hits": [
            {
                "id": 123456,
                "duration": 15,
                "pageURL": "https://pixabay.com/videos/dog-123456/",
                "videos": {
                    "large": {
                        "url": "https://cdn.pixabay.com/vimeo/123456/dog.mp4?download",
                        "width": 1080,
                        "height": 1920,
                    }
                },
            }
        ]
    }

    with patch("harness.tools.footage.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        results = _search_pixabay("dog anxiety panting", "fake_api_key")

    assert len(results) == 1
    assert results[0]["pexels_id"] == "pixabay_123456"
    assert results[0]["width"] == 1080
    assert results[0]["height"] == 1920
    assert results[0]["duration"] == 15
    assert "dog.mp4" in results[0]["download_url"]


def test_search_pixabay_skips_short_clips():
    from harness.tools.footage import _search_pixabay

    mock_response = {
        "hits": [
            {
                "id": 111,
                "duration": 3,
                "pageURL": "https://pixabay.com/videos/dog-111/",
                "videos": {"large": {"url": "https://cdn.pixabay.com/dog.mp4", "width": 720, "height": 1280}},
            }
        ]
    }

    with patch("harness.tools.footage.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        results = _search_pixabay("dog", "fake_key")

    assert results == []


def test_search_pixabay_returns_empty_on_error():
    from harness.tools.footage import _search_pixabay

    with patch("harness.tools.footage.requests.get", side_effect=Exception("timeout")):
        results = _search_pixabay("dog", "fake_key")

    assert results == []
