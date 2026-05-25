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


def test_pixabay_fallback_called_when_pexels_empty(tmp_path, monkeypatch):
    """When Pexels returns no clips, Pixabay should be tried."""
    from harness.tools import footage as footage_mod

    monkeypatch.setattr(footage_mod, "DOG_FOOTAGE_DIR", tmp_path)
    monkeypatch.setattr(footage_mod, "_search_pexels", lambda q, k, **kw: [])
    monkeypatch.setattr(footage_mod, "_load_pixabay_key", lambda: "fake_pixabay_key")
    monkeypatch.setattr(footage_mod, "_load_api_key", lambda: "fake_pexels_key")

    pixabay_called_with = []

    def fake_pixabay(query, key, **kw):
        pixabay_called_with.append(query)
        return []

    monkeypatch.setattr(footage_mod, "_search_pixabay", fake_pixabay)
    monkeypatch.setattr(footage_mod, "_yt_dlp_cc_fallback", lambda q: None)

    result = footage_mod.fetch_footage_for_topic("dog fun", "puppy playing fetch")
    assert len(pixabay_called_with) > 0, "Pixabay was never called despite Pexels returning nothing"
    assert result is None
