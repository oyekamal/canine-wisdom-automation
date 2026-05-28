from pathlib import Path
from harness.storage import get_state_path, get_data_dir


def test_get_data_dir_returns_channel_dir(tmp_path):
    cfg_data_dir = tmp_path / "channels" / "test" / "data"
    cfg_data_dir.mkdir(parents=True)

    class FakeCfg:
        data_dir = cfg_data_dir

    result = get_data_dir(FakeCfg())
    assert result == cfg_data_dir


def test_get_state_path_returns_channel_state(tmp_path):
    cfg_data_dir = tmp_path / "channels" / "test" / "data"
    cfg_data_dir.mkdir(parents=True)

    class FakeCfg:
        data_dir = cfg_data_dir
        state_path = cfg_data_dir / "state.json"

    result = get_state_path(FakeCfg())
    assert result == cfg_data_dir / "state.json"


def test_get_data_dir_falls_back_to_global_when_no_cfg():
    from harness.storage import DATA_DIR
    result = get_data_dir(None)
    assert result == DATA_DIR


def test_get_state_path_falls_back_to_global_when_no_cfg():
    from harness.storage import STATE_PATH
    result = get_state_path(None)
    assert result == STATE_PATH
