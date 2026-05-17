import fcntl
import json
import os
import threading
import time
from pathlib import Path

import pytest

from harness.storage import atomic_write, atomic_read, lock_state, STATE_PATH


@pytest.fixture
def tmp_json(tmp_path):
    return tmp_path / "test.json"


def test_atomic_write_creates_file(tmp_json):
    atomic_write(tmp_json, {"key": "value"})
    assert tmp_json.exists()


def test_atomic_write_content_is_correct(tmp_json):
    atomic_write(tmp_json, {"score": 42, "name": "rex"})
    data = json.loads(tmp_json.read_text())
    assert data["score"] == 42
    assert data["name"] == "rex"


def test_atomic_write_is_pretty_printed(tmp_json):
    atomic_write(tmp_json, {"a": 1})
    content = tmp_json.read_text()
    assert "\n" in content  # pretty-printed, not one line


def test_atomic_write_no_tmp_file_left(tmp_json):
    atomic_write(tmp_json, {"x": 1})
    tmp_file = tmp_json.with_suffix(".tmp")
    assert not tmp_file.exists()


def test_atomic_read_returns_dict(tmp_json):
    atomic_write(tmp_json, {"hello": "world"})
    data = atomic_read(tmp_json)
    assert data == {"hello": "world"}


def test_atomic_read_missing_file_raises(tmp_json):
    with pytest.raises(FileNotFoundError):
        atomic_read(tmp_json)


def test_atomic_write_overwrites_existing(tmp_json):
    atomic_write(tmp_json, {"v": 1})
    atomic_write(tmp_json, {"v": 2})
    data = atomic_read(tmp_json)
    assert data["v"] == 2


def test_concurrent_writes_do_not_corrupt(tmp_json):
    """Two threads writing simultaneously should not corrupt the file."""
    errors = []

    def writer(value):
        try:
            for _ in range(20):
                atomic_write(tmp_json, {"value": value})
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=writer, args=(1,))
    t2 = threading.Thread(target=writer, args=(2,))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert not errors
    data = atomic_read(tmp_json)
    assert data["value"] in (1, 2)  # one writer wins, file is valid JSON


def test_lock_state_is_context_manager(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.storage.STATE_PATH", tmp_path / "state.json")
    atomic_write(tmp_path / "state.json", {"locked": False})
    with lock_state() as state:
        assert isinstance(state, dict)
