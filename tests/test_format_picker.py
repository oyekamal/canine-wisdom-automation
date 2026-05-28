import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import VideoFormat
from harness.agents.format_picker import pick_format, LONG_FORM_CLUSTERS


def test_long_form_cluster_returns_long():
    """Clusters in LONG_FORM_CLUSTERS should produce LONG format."""
    for cluster in LONG_FORM_CLUSTERS:
        result = pick_format(cluster, recent_runs=[])
        assert result == VideoFormat.LONG, f"Expected LONG for cluster '{cluster}', got {result}"


def test_short_cluster_returns_short():
    """Clusters not in LONG_FORM_CLUSTERS default to SHORT."""
    result = pick_format("dog fun", recent_runs=[])
    assert result == VideoFormat.SHORT


def test_all_short_recent_runs_triggers_long():
    """If last 5 runs for this cluster were all SHORT, return LONG for variety."""
    recent = [
        {"topic_cluster": "dog fun", "format": "short"},
        {"topic_cluster": "dog fun", "format": "short"},
        {"topic_cluster": "dog fun", "format": "short"},
        {"topic_cluster": "dog fun", "format": "short"},
        {"topic_cluster": "dog fun", "format": "short"},
    ]
    result = pick_format("dog fun", recent_runs=recent)
    assert result == VideoFormat.LONG


def test_mixed_recent_runs_returns_short():
    """If recent runs are mixed, return SHORT."""
    recent = [
        {"topic_cluster": "dog fun", "format": "short"},
        {"topic_cluster": "dog fun", "format": "long"},
        {"topic_cluster": "dog fun", "format": "short"},
    ]
    result = pick_format("dog fun", recent_runs=recent)
    assert result == VideoFormat.SHORT


def test_different_cluster_recent_runs_ignored():
    """Recent runs from other clusters don't affect this cluster's decision."""
    recent = [
        {"topic_cluster": "dog breeds", "format": "short"},
        {"topic_cluster": "dog breeds", "format": "short"},
        {"topic_cluster": "dog breeds", "format": "short"},
        {"topic_cluster": "dog breeds", "format": "short"},
        {"topic_cluster": "dog breeds", "format": "short"},
    ]
    result = pick_format("dog fun", recent_runs=recent)
    assert result == VideoFormat.SHORT


def test_unknown_cluster_returns_short():
    result = pick_format("something new", recent_runs=[])
    assert result == VideoFormat.SHORT
