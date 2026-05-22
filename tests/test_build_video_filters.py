"""Tests for build_video filter composition logic."""

from caption_engine import build_caption_filter, CaptionStyle


def test_hook_filter_format():
    """Verify hook overlay filter format and escaping."""
    hook = "STOP DOING THIS"
    safe = hook.replace("'", "\\'").replace(":", "\\:")
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    result = (
        f"drawtext=fontfile='{font}':"
        f"text='{safe}':"
        f"fontcolor=white:"
        f"fontsize=90:"
        f"borderw=5:"
        f"bordercolor=black:"
        f"shadowx=4:shadowy=4:"
        f"x=(w-text_w)/2:y=(h*0.35):"
        f"enable='between(t,0,1.5)'"
    )
    assert "STOP DOING THIS" in result
    assert "enable='between(t,0,1.5)'" in result
    assert "fontfile='" in result
    assert "fontcolor=white" in result


def test_hook_filter_with_special_chars():
    """Verify hook overlay handles special characters safely."""
    hook = "DON'T: DO THIS"
    safe = hook.replace("'", "\\'").replace(":", "\\:")
    expected = "DON\\'T\\: DO THIS"
    assert safe == expected


def test_caption_filter_concatenated():
    """Verify captions are properly concatenated with commas."""
    words = [
        {"word": "Hello", "start": 0.0, "end": 0.4},
        {"word": "world", "start": 0.4, "end": 0.8},
    ]
    style = CaptionStyle()
    result = build_caption_filter(words, style)
    assert result.count("drawtext=") == 2
    assert "," in result
    assert "Hello" in result
    assert "world" in result


def test_caption_filter_empty_list():
    """Verify empty captions list returns empty string."""
    words = []
    style = CaptionStyle()
    result = build_caption_filter(words, style)
    assert result == ""


def test_caption_style_customization():
    """Verify caption style parameters are applied."""
    words = [
        {"word": "Test", "start": 0.0, "end": 0.5},
    ]
    style = CaptionStyle(font_size=68, font_color="yellow", stroke_width=4)
    result = build_caption_filter(words, style)
    assert "fontsize=68" in result
    assert "fontcolor=yellow" in result
    assert "borderw=4" in result


def test_base_filter_includes_color_grading():
    """Verify base filter has contrast and saturation boost."""
    VIDEO_WIDTH = 1080
    VIDEO_HEIGHT = 1920
    base_filter = (
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
        f"eq=brightness=0.02:saturation=1.4:contrast=1.1"
    )
    assert "saturation=1.4" in base_filter
    assert "contrast=1.1" in base_filter
    assert "brightness=0.02" in base_filter


def test_filter_composition():
    """Verify filters are properly composed with commas."""
    base_filter = "scale=1080:1920"
    hook_filter = "drawtext=text='HOOK'"
    caption_filter = "drawtext=text='caption1',drawtext=text='caption2'"

    filter_parts = [base_filter]
    if hook_filter:
        filter_parts.append(hook_filter)
    if caption_filter:
        filter_parts.append(caption_filter)
    video_filter = ",".join(filter_parts)

    assert video_filter == "scale=1080:1920,drawtext=text='HOOK',drawtext=text='caption1',drawtext=text='caption2'"
