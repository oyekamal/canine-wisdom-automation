import inspect


def test_get_youtube_service_accepts_channel_config():
    from upload_youtube import get_youtube_service
    sig = inspect.signature(get_youtube_service)
    assert "channel_config" in sig.parameters


def test_upload_youtube_accepts_channel_config():
    from upload_youtube import upload_youtube
    sig = inspect.signature(upload_youtube)
    assert "channel_config" in sig.parameters
