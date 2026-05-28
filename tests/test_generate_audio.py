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
