"""
Unit tests for generate_script.py

Tests:
1. generate_script() returns correct dict structure
2. Script and metadata files are created in outputs/
3. JSON parsing error handling
4. Missing required fields error handling
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

from generate_script import generate_script


# ============================================================================
# Test 1: generate_script() returns correct dict structure
# ============================================================================

def test_generate_script_returns_correct_structure():
    """
    Test that generate_script() returns a dictionary with required keys.
    """
    mock_response_data = {
        "script": "Did you know? Dogs can hear frequencies...",
        "title": "This Dog Fact Will Blow Your Mind!",
        "hashtags": ["dogs", "facts", "shorts", "viral", "dogfacts",
                     "amazingfacts", "petlovers", "animalfacts", "trending", "youtube"]
    }

    with patch("generate_script.load_config") as mock_config, \
         patch("generate_script.Anthropic") as mock_anthropic, \
         patch("generate_script.log"):

        # Setup config mock
        mock_cfg = {
            "anthropic_api_key": "test-api-key",
            "outputs_dir": Path(tempfile.gettempdir()) / "test_outputs"
        }
        mock_cfg["outputs_dir"].mkdir(exist_ok=True)
        mock_config.return_value = mock_cfg

        # Setup Anthropic client mock
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Setup message response
        mock_message = Mock()
        mock_message.content = [Mock(text=json.dumps(mock_response_data))]
        mock_client.messages.create.return_value = mock_message

        # Call function
        result = generate_script()

        # Verify result structure
        assert isinstance(result, dict)
        assert "script" in result
        assert "title" in result
        assert "hashtags" in result
        assert result["script"] == mock_response_data["script"]
        assert result["title"] == mock_response_data["title"]
        assert result["hashtags"] == mock_response_data["hashtags"]


# ============================================================================
# Test 2: Script and metadata files are created
# ============================================================================

def test_generate_script_creates_files():
    """
    Test that generate_script() creates script.txt and metadata.json.
    """
    mock_response_data = {
        "script": "Dogs have an amazing sense of smell...",
        "title": "Puppy Power Unleashed!",
        "hashtags": ["puppy", "dogs", "cute", "viral", "shorts",
                     "facts", "amazing", "petlovers", "nature", "animals"]
    }

    with patch("generate_script.load_config") as mock_config, \
         patch("generate_script.Anthropic") as mock_anthropic, \
         patch("generate_script.log"):

        # Create temporary outputs directory
        with tempfile.TemporaryDirectory() as tmpdir:
            outputs_dir = Path(tmpdir)

            # Setup config mock
            mock_cfg = {
                "anthropic_api_key": "test-api-key",
                "outputs_dir": outputs_dir
            }
            mock_config.return_value = mock_cfg

            # Setup Anthropic client mock
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client

            # Setup message response
            mock_message = Mock()
            mock_message.content = [Mock(text=json.dumps(mock_response_data))]
            mock_client.messages.create.return_value = mock_message

            # Call function
            generate_script()

            # Verify files were created
            script_file = outputs_dir / "script.txt"
            metadata_file = outputs_dir / "metadata.json"

            assert script_file.exists(), f"script.txt not found at {script_file}"
            assert metadata_file.exists(), f"metadata.json not found at {metadata_file}"

            # Verify script.txt contents
            with open(script_file, "r", encoding="utf-8") as f:
                script_content = f.read()
            assert script_content == mock_response_data["script"]

            # Verify metadata.json contents
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata_content = json.load(f)
            assert metadata_content == mock_response_data


# ============================================================================
# Test 3: JSON parsing error handling
# ============================================================================

def test_generate_script_handles_invalid_json():
    """
    Test that generate_script() raises ValueError for invalid JSON.
    """
    with patch("generate_script.load_config") as mock_config, \
         patch("generate_script.Anthropic") as mock_anthropic, \
         patch("generate_script.log"), \
         patch("generate_script.retry_with_backoff") as mock_retry:

        # Setup config mock
        mock_cfg = {
            "anthropic_api_key": "test-api-key",
            "outputs_dir": Path(tempfile.gettempdir())
        }
        mock_config.return_value = mock_cfg

        # Setup retry to call the inner function directly
        def side_effect(func, *args, **kwargs):
            return func()

        mock_retry.side_effect = side_effect

        # Setup Anthropic client mock to return invalid JSON
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_message = Mock()
        mock_message.content = [Mock(text="This is not valid JSON {")]
        mock_client.messages.create.return_value = mock_message

        # Verify ValueError is raised
        with pytest.raises(ValueError) as exc_info:
            generate_script()

        assert "Invalid JSON response" in str(exc_info.value)


# ============================================================================
# Test 4: Missing required fields error handling
# ============================================================================

def test_generate_script_handles_missing_fields():
    """
    Test that generate_script() raises ValueError when required fields are missing.
    """
    # Missing 'title' field
    incomplete_response = {
        "script": "Some script here...",
        "hashtags": ["dog", "facts", "viral", "shorts", "animals",
                     "pets", "amazing", "trending", "youtube", "fun"]
    }

    with patch("generate_script.load_config") as mock_config, \
         patch("generate_script.Anthropic") as mock_anthropic, \
         patch("generate_script.log"), \
         patch("generate_script.retry_with_backoff") as mock_retry:

        # Setup config mock
        mock_cfg = {
            "anthropic_api_key": "test-api-key",
            "outputs_dir": Path(tempfile.gettempdir())
        }
        mock_config.return_value = mock_cfg

        # Setup retry to call the inner function directly
        def side_effect(func, *args, **kwargs):
            return func()

        mock_retry.side_effect = side_effect

        # Setup Anthropic client mock
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_message = Mock()
        mock_message.content = [Mock(text=json.dumps(incomplete_response))]
        mock_client.messages.create.return_value = mock_message

        # Verify ValueError is raised
        with pytest.raises(ValueError) as exc_info:
            generate_script()

        assert "Missing required fields" in str(exc_info.value)
        assert "title" in str(exc_info.value)


# ============================================================================
# Test 5: Invalid hashtags type error handling
# ============================================================================

def test_generate_script_handles_invalid_hashtags_type():
    """
    Test that generate_script() raises ValueError when hashtags is not a list.
    """
    invalid_response = {
        "script": "Some script here...",
        "title": "Amazing Dog Fact!",
        "hashtags": "should-be-a-list-not-string"
    }

    with patch("generate_script.load_config") as mock_config, \
         patch("generate_script.Anthropic") as mock_anthropic, \
         patch("generate_script.log"), \
         patch("generate_script.retry_with_backoff") as mock_retry:

        # Setup config mock
        mock_cfg = {
            "anthropic_api_key": "test-api-key",
            "outputs_dir": Path(tempfile.gettempdir())
        }
        mock_config.return_value = mock_cfg

        # Setup retry to call the inner function directly
        def side_effect(func, *args, **kwargs):
            return func()

        mock_retry.side_effect = side_effect

        # Setup Anthropic client mock
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_message = Mock()
        mock_message.content = [Mock(text=json.dumps(invalid_response))]
        mock_client.messages.create.return_value = mock_message

        # Verify ValueError is raised
        with pytest.raises(ValueError) as exc_info:
            generate_script()

        assert "hashtags must be a list" in str(exc_info.value)


# ============================================================================
# Test 6: Verify retry_with_backoff is called with correct parameters
# ============================================================================

def test_generate_script_uses_retry_with_backoff():
    """
    Test that generate_script() calls retry_with_backoff with correct parameters.
    """
    mock_response_data = {
        "script": "Dogs are amazing creatures...",
        "title": "Woah, Dogs Can Do WHAT?!",
        "hashtags": ["dogs", "facts", "viral", "shorts", "animals",
                     "pets", "science", "discovery", "amazing", "trending"]
    }

    with patch("generate_script.load_config") as mock_config, \
         patch("generate_script.Anthropic") as mock_anthropic, \
         patch("generate_script.log"), \
         patch("generate_script.retry_with_backoff") as mock_retry:

        # Setup config mock
        mock_cfg = {
            "anthropic_api_key": "test-api-key",
            "outputs_dir": Path(tempfile.gettempdir()) / "test_outputs"
        }
        mock_cfg["outputs_dir"].mkdir(exist_ok=True)
        mock_config.return_value = mock_cfg

        # Setup retry to return mock data
        mock_retry.return_value = mock_response_data

        # Setup Anthropic client mock (won't be called if retry_with_backoff is mocked)
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Call function
        generate_script()

        # Verify retry_with_backoff was called with correct parameters
        mock_retry.assert_called_once()
        call_args = mock_retry.call_args
        assert call_args[1]["max_retries"] == 1
        assert call_args[1]["step_name"] == "Claude API"


# ============================================================================
# Test 7: Complete end-to-end with mock client
# ============================================================================

def test_generate_script_complete_flow():
    """
    Test complete generate_script() flow with proper mocking.
    """
    mock_response_data = {
        "script": "Here's a wild fact about dogs that'll change how you see them forever! "
                  "Did you know that dogs can understand up to 250 words? "
                  "They're basically tiny furry geniuses! "
                  "Follow for daily dog facts!",
        "title": "Dogs Understand 250 Words?!",
        "hashtags": ["dogs", "facts", "mindblown", "shorts", "animals",
                     "pets", "learning", "intelligence", "amazing", "trending"]
    }

    with patch("generate_script.load_config") as mock_config, \
         patch("generate_script.Anthropic") as mock_anthropic, \
         patch("generate_script.log"):

        with tempfile.TemporaryDirectory() as tmpdir:
            outputs_dir = Path(tmpdir)

            # Setup config mock
            mock_cfg = {
                "anthropic_api_key": "test-api-key-12345",
                "outputs_dir": outputs_dir
            }
            mock_config.return_value = mock_cfg

            # Setup Anthropic client mock
            mock_client = MagicMock()
            mock_anthropic.return_value = mock_client

            # Setup message response
            mock_message = Mock()
            mock_message.content = [Mock(text=json.dumps(mock_response_data))]
            mock_client.messages.create.return_value = mock_message

            # Call function
            result = generate_script()

            # Verify result
            assert result == mock_response_data

            # Verify files exist and contain correct content
            script_file = outputs_dir / "script.txt"
            metadata_file = outputs_dir / "metadata.json"

            assert script_file.exists()
            assert metadata_file.exists()

            with open(script_file, "r") as f:
                assert f.read() == mock_response_data["script"]

            with open(metadata_file, "r") as f:
                assert json.load(f) == mock_response_data

            # Verify Anthropic client was created with correct API key
            mock_anthropic.assert_called_with(api_key="test-api-key-12345")

            # Verify messages.create was called with correct model
            call_args = mock_client.messages.create.call_args
            assert call_args[1]["model"] == "claude-opus-4-5"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
