import json
from pathlib import Path


def test_all_topic_clusters_have_real_links():
    settings = json.loads(Path("youtube_settings.json").read_text())
    links = settings["affiliate_links"]
    required = ["dog breeds", "dog training", "dog behavior",
                "dog health", "dog science", "dog history", "dog fun", "default"]
    for cluster in required:
        assert cluster in links, f"Missing cluster: {cluster}"
        assert "url" in links[cluster], f"Missing url for: {cluster}"
        assert "amzn.to" in links[cluster]["url"], f"Not Amazon URL for: {cluster}"
        assert "product" in links[cluster], f"Missing product text for: {cluster}"


def test_no_placeholder_links():
    content = Path("youtube_settings.json").read_text()
    assert "example.com" not in content
    assert "barkbox.com" not in content
    assert "[AFFILIATE_LINK" not in content
