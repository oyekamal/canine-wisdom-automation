import inspect


def test_generate_audio_accepts_voice_id_param():
    from generate_audio import generate_audio
    sig = inspect.signature(generate_audio)
    assert "voice_id" in sig.parameters


def test_generate_audio_accepts_script_param():
    from generate_audio import generate_audio
    sig = inspect.signature(generate_audio)
    assert "script" in sig.parameters


def test_generate_audio_defaults_to_none():
    from generate_audio import generate_audio
    sig = inspect.signature(generate_audio)
    assert sig.parameters["voice_id"].default is None
    assert sig.parameters["script"].default is None


def test_generate_audio_supertonic_exists():
    """generate_audio_supertonic must exist and accept script and voice_id."""
    from generate_audio import generate_audio_supertonic
    sig = inspect.signature(generate_audio_supertonic)
    assert "script" in sig.parameters
    assert "voice_id" in sig.parameters


def test_map_elevenlabs_to_supertonic_male():
    """Known male ElevenLabs voice IDs map to M1 or M2."""
    from generate_audio import _map_voice_to_supertonic
    assert _map_voice_to_supertonic("pNInz6obpgDQGcFmaJgB") == "M1"
    assert _map_voice_to_supertonic("JBFqnCBsd6RMkjVDRZzb") == "M2"
    assert _map_voice_to_supertonic("N2lVS1w4EtoT3dr4eOWO") == "M1"
    assert _map_voice_to_supertonic("SOYHLrjzK2X1ezoPC6cr") == "M2"


def test_map_elevenlabs_to_supertonic_female():
    """Known female ElevenLabs voice IDs map to F1."""
    from generate_audio import _map_voice_to_supertonic
    assert _map_voice_to_supertonic("EXAVITQu4vr4xnSDxMaL") == "F1"


def test_map_elevenlabs_to_supertonic_unknown_defaults_m1():
    """Unknown voice IDs default to M1."""
    from generate_audio import _map_voice_to_supertonic
    assert _map_voice_to_supertonic("unknown-voice-xyz") == "M1"
