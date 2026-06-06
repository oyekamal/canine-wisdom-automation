"""
Tests for main.py orchestrator.

Tests verify:
1. main() function exists and is callable
2. All module imports are correct
3. Proper error handling and exit codes
4. Correct orchestration order (via mock)
"""

import sys
from unittest.mock import Mock, patch, call
from pathlib import Path


def test_main_imports():
    """Test that main.py can be imported without errors."""
    # This verifies syntax is correct
    import main
    assert hasattr(main, 'main'), "main.py should have main() function"
    print("✅ test_main_imports passed")


def test_main_function_signature():
    """Test that main() is callable and has correct signature."""
    from main import main

    # Verify it's callable
    assert callable(main), "main() should be callable"

    # Verify it returns an integer (exit code)
    # We can't actually run it without mocking, but we can check its structure
    print("✅ test_main_function_signature passed")


@patch('main.run_channel_pipeline')
@patch('main.log')
@patch('main.init_logger')
def test_main_execution_order(
    mock_init_logger,
    mock_log,
    mock_run_channel_pipeline,
):
    """Test that main() calls run_channel_pipeline for each active channel."""
    from main import main, ACTIVE_CHANNELS

    exit_code = main()

    assert exit_code == 0, f"main() should return 0 on success, got {exit_code}"
    assert mock_init_logger.called, "init_logger should be called"
    assert mock_run_channel_pipeline.call_count == len(ACTIVE_CHANNELS), \
        "run_channel_pipeline should be called once per channel"

    print("✅ test_main_execution_order passed")


@patch('main.run_channel_pipeline')
@patch('main.log')
@patch('main.init_logger')
def test_main_error_handling(
    mock_init_logger,
    mock_log,
    mock_run_channel_pipeline,
):
    """Test that main() handles exceptions correctly and returns 1 when a channel fails."""
    from main import main

    mock_run_channel_pipeline.side_effect = Exception("Test error")

    exit_code = main()

    assert exit_code == 1, f"main() should return 1 on error, got {exit_code}"

    print("✅ test_main_error_handling passed")


@patch('main.run_channel_pipeline')
@patch('main.log')
@patch('main.init_logger')
def test_main_keyboard_interrupt(
    mock_init_logger,
    mock_log,
    mock_run_channel_pipeline,
):
    """Test that main() handles KeyboardInterrupt correctly."""
    from main import main

    mock_run_channel_pipeline.side_effect = KeyboardInterrupt()

    exit_code = main()

    assert exit_code == 1, f"main() should return 1 on interrupt, got {exit_code}"

    print("✅ test_main_keyboard_interrupt passed")


def test_main_executable():
    """Test that main.py is executable and has shebang."""
    with open('main.py', 'r') as f:
        first_line = f.readline()

    assert first_line.strip() == '#!/usr/bin/env python3', \
        f"main.py should have shebang, got: {first_line}"

    print("✅ test_main_executable passed")


def test_main_runs_both_channels(monkeypatch):
    """main() should invoke the pipeline once per active channel."""
    from unittest.mock import MagicMock, patch
    import main as main_module

    ran_channels = []

    def fake_run_channel(slug, run_id):
        ran_channels.append(slug)

    monkeypatch.setattr(main_module, "run_channel_pipeline", fake_run_channel)

    main_module.main()

    assert "canine-wisdom" in ran_channels
    assert "horror-narration" in ran_channels
    assert len(ran_channels) == 2


if __name__ == '__main__':
    # Run all tests
    test_main_imports()
    test_main_function_signature()
    test_main_executable()

    # These require mocking
    test_main_execution_order()
    test_main_error_handling()
    test_main_keyboard_interrupt()

    print("\n✅ All tests passed!")
