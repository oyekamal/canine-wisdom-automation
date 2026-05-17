import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.agents.competitor import bootstrap_competitors_if_needed


@pytest.fixture(autouse=True)
def patch_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.agents.competitor.DATA_DIR", tmp_path)
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({
        "competitor_channels": [],
        "config": {},
        "current_kpis": {},
        "last_run": None,
        "last_weekly_eval": None,
    }))
    # STATE_PATH is imported lazily inside bootstrap_competitors_if_needed,
    # so patch it on the storage module directly.
    import harness.storage as hs
    monkeypatch.setattr(hs, "STATE_PATH", state_path)
    yield tmp_path, state_path


def test_bootstrap_runs_discovery_when_no_channels(patch_dirs):
    tmp_path, state_path = patch_dirs
    mock_youtube = MagicMock()
    mock_channels = [
        {"channel_id": "UC001", "channel_name": "DogFacts", "subscriber_count": 100000,
         "ranking_score": 85.0, "discovered_at": "2026-05-17T09:00:00"},
    ]
    with patch("harness.agents.competitor.get_youtube_service", return_value=mock_youtube):
        with patch("harness.agents.competitor.discover_channels", return_value=mock_channels):
            ran = bootstrap_competitors_if_needed()

    assert ran is True
    state = json.loads(state_path.read_text())
    assert "UC001" in state["competitor_channels"]
    ch_file = tmp_path / "competitors" / "UC001" / "channel.json"
    assert ch_file.exists()


def test_bootstrap_skips_when_channels_already_configured(patch_dirs):
    tmp_path, state_path = patch_dirs
    state = json.loads(state_path.read_text())
    state["competitor_channels"] = ["UC001"]
    state_path.write_text(json.dumps(state))

    with patch("harness.agents.competitor.discover_channels") as mock_discover:
        ran = bootstrap_competitors_if_needed()
        mock_discover.assert_not_called()

    assert ran is False


def test_bootstrap_handles_discovery_failure_gracefully(patch_dirs):
    tmp_path, state_path = patch_dirs
    with patch("harness.agents.competitor.get_youtube_service", side_effect=Exception("auth fail")):
        ran = bootstrap_competitors_if_needed()

    assert ran is False
    state = json.loads(state_path.read_text())
    assert state["competitor_channels"] == []
