import json
from pathlib import Path


REQUIRED_CLUSTERS = [
    "dog breeds",
    "dog training",
    "dog behavior",
    "dog health",
    "dog science",
    "dog history",
    "dog fun",
    "dog anxiety",
    "dog separation anxiety",
    "senior dog",
    "dog nutrition",
    "dog safety",
    "default",
]


def test_all_topic_clusters_have_real_links():
    settings = json.loads(Path("youtube_settings.json").read_text())
    links = settings["affiliate_links"]
    for cluster in REQUIRED_CLUSTERS:
        assert cluster in links, f"Missing cluster: {cluster}"
        assert "url" in links[cluster], f"Missing url for: {cluster}"
        assert "amzn.to" in links[cluster]["url"], f"Not Amazon URL for: {cluster}"
        assert "product" in links[cluster], f"Missing product text for: {cluster}"


def test_no_placeholder_links():
    content = Path("youtube_settings.json").read_text()
    assert "example.com" not in content
    assert "barkbox.com" not in content
    assert "[AFFILIATE_LINK" not in content


def test_new_topic_clusters_have_links():
    """Verify client-supplied affiliate links are present for all new clusters."""
    settings = json.loads(Path("youtube_settings.json").read_text())
    links = settings["affiliate_links"]
    new_clusters = {
        "dog anxiety": "amzn.to/4whfoeI",         # ThunderShirt
        "dog separation anxiety": "amzn.to/4u0AhZY",  # Furbo camera
        "senior dog": "amzn.to/3OWy3Md",          # Orthopedic bed
        "dog nutrition": "amzn.to/4dkXi2Z",        # Slow feeder bowl
        "dog safety": "amzn.to/3QQZxU7",           # GPS tracker
    }
    for cluster, partial_url in new_clusters.items():
        assert cluster in links, f"Missing cluster: {cluster}"
        assert partial_url in links[cluster]["url"], (
            f"Wrong URL for '{cluster}': expected {partial_url}, "
            f"got {links[cluster]['url']}"
        )
