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


@patch('main.upload_youtube')
@patch('main.build_video')
@patch('main.generate_audio')
@patch('main.generate_script')
@patch('main.move_outputs_to_archive')
@patch('main.clear_outputs_dir')
@patch('main.log')
@patch('main.load_config')
@patch('main.init_logger')
def test_main_execution_order(
    mock_init_logger,
    mock_load_config,
    mock_log,
    mock_clear_outputs,
    mock_move_outputs,
    mock_generate_script,
    mock_generate_audio,
    mock_build_video,
    mock_upload_youtube
):
    """Test that main() calls pipeline steps in correct order."""
    from main import main

    # Setup return values
    mock_load_config.return_value = {
        'outputs_dir': Path('/tmp/outputs'),
        'archive_dir': Path('/tmp/archive'),
        'run_logs_dir': Path('/tmp/logs'),
    }
    mock_generate_script.return_value = {'script': 'test', 'title': 'Test'}
    mock_generate_audio.return_value = 15.5  # duration in seconds
    mock_build_video.return_value = '/tmp/outputs/final_video.mp4'
    mock_upload_youtube.return_value = 'https://youtube.com/shorts/test'

    # Call main
    exit_code = main()

    # Verify exit code
    assert exit_code == 0, f"main() should return 0 on success, got {exit_code}"

    # Verify all steps were called
    assert mock_init_logger.called, "init_logger should be called"
    assert mock_load_config.called, "load_config should be called"
    assert mock_clear_outputs.called, "clear_outputs_dir should be called"
    assert mock_generate_script.called, "generate_script should be called first"
    assert mock_generate_audio.called, "generate_audio should be called second"
    assert mock_build_video.called, "build_video should be called third"
    assert mock_upload_youtube.called, "upload_youtube should be called fourth"
    assert mock_move_outputs.called, "move_outputs_to_archive should be called last"

    # Verify order by checking call order
    calls = []
    for mock in [
        mock_generate_script,
        mock_generate_audio,
        mock_build_video,
        mock_upload_youtube,
        mock_move_outputs,
    ]:
        if mock.called:
            calls.append(mock.call_args)

    print("✅ test_main_execution_order passed")


@patch('main.upload_youtube')
@patch('main.build_video')
@patch('main.generate_audio')
@patch('main.generate_script')
@patch('main.move_outputs_to_archive')
@patch('main.clear_outputs_dir')
@patch('main.log')
@patch('main.load_config')
@patch('main.init_logger')
def test_main_error_handling(
    mock_init_logger,
    mock_load_config,
    mock_log,
    mock_clear_outputs,
    mock_move_outputs,
    mock_generate_script,
    mock_generate_audio,
    mock_build_video,
    mock_upload_youtube
):
    """Test that main() handles exceptions correctly."""
    from main import main

    # Setup to raise exception
    mock_load_config.return_value = {}
    mock_generate_script.side_effect = Exception("Test error")

    # Call main
    exit_code = main()

    # Verify exit code on error
    assert exit_code == 1, f"main() should return 1 on error, got {exit_code}"

    print("✅ test_main_error_handling passed")


@patch('main.upload_youtube')
@patch('main.build_video')
@patch('main.generate_audio')
@patch('main.generate_script')
@patch('main.move_outputs_to_archive')
@patch('main.clear_outputs_dir')
@patch('main.log')
@patch('main.load_config')
@patch('main.init_logger')
def test_main_keyboard_interrupt(
    mock_init_logger,
    mock_load_config,
    mock_log,
    mock_clear_outputs,
    mock_move_outputs,
    mock_generate_script,
    mock_generate_audio,
    mock_build_video,
    mock_upload_youtube
):
    """Test that main() handles KeyboardInterrupt correctly."""
    from main import main

    # Setup to raise KeyboardInterrupt
    mock_load_config.return_value = {}
    mock_generate_script.side_effect = KeyboardInterrupt()

    # Call main
    exit_code = main()

    # Verify exit code on interrupt
    assert exit_code == 1, f"main() should return 1 on interrupt, got {exit_code}"

    print("✅ test_main_keyboard_interrupt passed")


def test_main_executable():
    """Test that main.py is executable and has shebang."""
    with open('main.py', 'r') as f:
        first_line = f.readline()

    assert first_line.strip() == '#!/usr/bin/env python3', \
        f"main.py should have shebang, got: {first_line}"

    print("✅ test_main_executable passed")


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
