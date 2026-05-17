import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.orchestrator import run_pipeline, _write_incident


# ── _write_incident ───────────────────────────────────────────────────────────

def test_write_incident_creates_json_file(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.orchestrator.DATA_DIR", tmp_path)
    (tmp_path / "incidents").mkdir()
    incident_id = _write_incident(
        trigger="hook_eval",
        what_failed="Score 4.0 < threshold 7.0",
        hypothesis="Hook is too generic",
        code_path="generate_script.py:prompt",
    )
    incident_files = list((tmp_path / "incidents").glob("*.json"))
    assert len(incident_files) == 1
    data = json.loads(incident_files[0].read_text())
    assert data["trigger"] == "hook_eval"
    assert data["what_failed"] == "Score 4.0 < threshold 7.0"
    assert "id" in data
    assert "timestamp" in data


def test_write_incident_creates_md_file(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.orchestrator.DATA_DIR", tmp_path)
    (tmp_path / "incidents").mkdir()
    _write_incident(
        trigger="audio_eval",
        what_failed="Audio too short: 5s",
        hypothesis="ElevenLabs returned clipped audio",
        code_path="generate_audio.py",
    )
    md_files = list((tmp_path / "incidents").glob("*.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text()
    assert "audio_eval" in content
    assert "Audio too short" in content


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_eval_result(passed: bool, score: float = 8.0, name: str = "hook_eval"):
    from harness.evals.base import EvalResult
    r = EvalResult.__new__(EvalResult)
    r.eval_name = name
    r.score = score
    r.threshold = 7.0
    r.reasoning = "mocked"
    r.passed = passed
    return r


# ── run_pipeline ──────────────────────────────────────────────────────────────

@patch("harness.orchestrator.video_eval")
@patch("harness.orchestrator.audio_eval")
@patch("harness.orchestrator.description_eval")
@patch("harness.orchestrator.thumbnail_eval")
@patch("harness.orchestrator.title_eval")
@patch("harness.orchestrator.script_eval")
@patch("harness.orchestrator.hook_eval")
@patch("harness.orchestrator.build_video", return_value="outputs/final_video.mp4")
@patch("harness.orchestrator.generate_audio", return_value=45.0)
@patch("harness.orchestrator.generate_script", return_value={"script": "Dogs rule.", "title": "Dog Facts", "hashtags": ["dogs"]})
@patch("harness.orchestrator.upload_youtube", return_value="https://youtube.com/shorts/abc123")
@patch("harness.orchestrator.move_outputs_to_archive")
@patch("harness.orchestrator.clear_outputs_dir")
@patch("harness.orchestrator.init_logger")
def test_run_pipeline_succeeds_when_all_evals_pass(
    mock_logger, mock_clear, mock_archive, mock_upload, mock_script, mock_audio, mock_video_build,
    mock_hook, mock_script_eval, mock_title, mock_thumb, mock_desc, mock_audio_eval, mock_video_eval,
    tmp_path, monkeypatch
):
    monkeypatch.setattr("harness.orchestrator.DATA_DIR", tmp_path)
    (tmp_path / "incidents").mkdir()
    (tmp_path / "eval_runs").mkdir()

    for mock in [mock_hook, mock_script_eval, mock_title, mock_thumb, mock_desc]:
        mock.return_value = _make_eval_result(passed=True)
    mock_audio_eval.return_value = _make_eval_result(passed=True, name="audio_eval")
    mock_video_eval.return_value = _make_eval_result(passed=True, name="video_eval")

    result = run_pipeline()
    assert result["success"] is True
    assert result["video_url"] == "https://youtube.com/shorts/abc123"


@patch("harness.orchestrator.video_eval")
@patch("harness.orchestrator.audio_eval")
@patch("harness.orchestrator.description_eval")
@patch("harness.orchestrator.thumbnail_eval")
@patch("harness.orchestrator.title_eval")
@patch("harness.orchestrator.script_eval")
@patch("harness.orchestrator.hook_eval")
@patch("harness.orchestrator.build_video", return_value="outputs/final_video.mp4")
@patch("harness.orchestrator.generate_audio", return_value=45.0)
@patch("harness.orchestrator.generate_script", return_value={"script": "Dogs rule.", "title": "Dog Facts", "hashtags": ["dogs"]})
@patch("harness.orchestrator.upload_youtube", return_value="https://youtube.com/shorts/abc123")
@patch("harness.orchestrator.move_outputs_to_archive")
@patch("harness.orchestrator.clear_outputs_dir")
@patch("harness.orchestrator.init_logger")
def test_run_pipeline_retries_script_on_hook_fail(
    mock_logger, mock_clear, mock_archive, mock_upload, mock_script, mock_audio, mock_video_build,
    mock_hook, mock_script_eval, mock_title, mock_thumb, mock_desc, mock_audio_eval, mock_video_eval,
    tmp_path, monkeypatch
):
    monkeypatch.setattr("harness.orchestrator.DATA_DIR", tmp_path)
    (tmp_path / "incidents").mkdir()

    mock_hook.side_effect = [
        _make_eval_result(passed=False, score=4.0),
        _make_eval_result(passed=False, score=5.0),
        _make_eval_result(passed=True, score=8.0),
    ]
    for mock in [mock_script_eval, mock_title, mock_thumb, mock_desc]:
        mock.return_value = _make_eval_result(passed=True)
    mock_audio_eval.return_value = _make_eval_result(passed=True, name="audio_eval")
    mock_video_eval.return_value = _make_eval_result(passed=True, name="video_eval")

    result = run_pipeline()
    assert result["success"] is True
    assert mock_script.call_count == 3


@patch("harness.orchestrator.video_eval")
@patch("harness.orchestrator.audio_eval")
@patch("harness.orchestrator.description_eval")
@patch("harness.orchestrator.thumbnail_eval")
@patch("harness.orchestrator.title_eval")
@patch("harness.orchestrator.script_eval")
@patch("harness.orchestrator.hook_eval")
@patch("harness.orchestrator.build_video", return_value="outputs/final_video.mp4")
@patch("harness.orchestrator.generate_audio", return_value=45.0)
@patch("harness.orchestrator.generate_script", return_value={"script": "Dogs rule.", "title": "Dog Facts", "hashtags": ["dogs"]})
@patch("harness.orchestrator.upload_youtube", return_value="https://youtube.com/shorts/abc123")
@patch("harness.orchestrator.move_outputs_to_archive")
@patch("harness.orchestrator.clear_outputs_dir")
@patch("harness.orchestrator.init_logger")
def test_run_pipeline_writes_incident_and_fails_after_3_hook_failures(
    mock_logger, mock_clear, mock_archive, mock_upload, mock_script, mock_audio, mock_video_build,
    mock_hook, mock_script_eval, mock_title, mock_thumb, mock_desc, mock_audio_eval, mock_video_eval,
    tmp_path, monkeypatch
):
    monkeypatch.setattr("harness.orchestrator.DATA_DIR", tmp_path)
    (tmp_path / "incidents").mkdir()

    mock_hook.return_value = _make_eval_result(passed=False, score=3.0)
    for mock in [mock_script_eval, mock_title, mock_thumb, mock_desc]:
        mock.return_value = _make_eval_result(passed=True)
    mock_audio_eval.return_value = _make_eval_result(passed=True, name="audio_eval")
    mock_video_eval.return_value = _make_eval_result(passed=True, name="video_eval")

    result = run_pipeline()
    assert result["success"] is False
    assert "hook_eval" in result["reason"]
    incident_files = list((tmp_path / "incidents").glob("*.json"))
    assert len(incident_files) == 1


@patch("harness.orchestrator.video_eval")
@patch("harness.orchestrator.audio_eval")
@patch("harness.orchestrator.description_eval")
@patch("harness.orchestrator.thumbnail_eval")
@patch("harness.orchestrator.title_eval")
@patch("harness.orchestrator.script_eval")
@patch("harness.orchestrator.hook_eval")
@patch("harness.orchestrator.build_video", return_value="outputs/final_video.mp4")
@patch("harness.orchestrator.generate_audio", return_value=45.0)
@patch("harness.orchestrator.generate_script", return_value={"script": "Dogs rule.", "title": "Dog Facts", "hashtags": ["dogs"]})
@patch("harness.orchestrator.upload_youtube", return_value="https://youtube.com/shorts/abc123")
@patch("harness.orchestrator.move_outputs_to_archive")
@patch("harness.orchestrator.clear_outputs_dir")
@patch("harness.orchestrator.init_logger")
def test_run_pipeline_halts_on_hard_audio_fail(
    mock_logger, mock_clear, mock_archive, mock_upload, mock_script, mock_audio, mock_video_build,
    mock_hook, mock_script_eval, mock_title, mock_thumb, mock_desc, mock_audio_eval, mock_video_eval,
    tmp_path, monkeypatch
):
    monkeypatch.setattr("harness.orchestrator.DATA_DIR", tmp_path)
    (tmp_path / "incidents").mkdir()

    for mock in [mock_hook, mock_script_eval, mock_title, mock_thumb, mock_desc]:
        mock.return_value = _make_eval_result(passed=True)
    mock_audio_eval.return_value = _make_eval_result(passed=False, score=0.0, name="audio_eval")
    mock_video_eval.return_value = _make_eval_result(passed=True, name="video_eval")

    result = run_pipeline()
    assert result["success"] is False
    assert "audio_eval" in result["reason"]
    mock_upload.assert_not_called()
