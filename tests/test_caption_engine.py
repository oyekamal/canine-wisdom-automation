from caption_engine import words_to_drawtext, CaptionStyle

SAMPLE_WORDS = [
    {"word": "STOP", "start": 0.0, "end": 0.3},
    {"word": "doing", "start": 0.3, "end": 0.6},
    {"word": "this", "start": 0.6, "end": 0.9},
]


def test_drawtext_count_matches_words():
    style = CaptionStyle()
    filters = words_to_drawtext(SAMPLE_WORDS, style)
    assert len(filters) == 3


def test_drawtext_contains_word_text():
    style = CaptionStyle()
    filters = words_to_drawtext(SAMPLE_WORDS, style)
    assert "STOP" in filters[0]
    assert "doing" in filters[1]


def test_drawtext_has_enable_range():
    style = CaptionStyle()
    filters = words_to_drawtext(SAMPLE_WORDS, style)
    # Uses gte*lte to avoid comma-inside-quotes ffmpeg parsing bug
    assert "gte(t\\,0.0)*lte(t\\,0.3)" in filters[0]
    assert "gte(t\\,0.3)*lte(t\\,0.6)" in filters[1]


def test_drawtext_uses_bold_color():
    style = CaptionStyle(font_color="yellow")
    filters = words_to_drawtext(SAMPLE_WORDS, style)
    assert "fontcolor=yellow" in filters[0]


def test_empty_words_returns_empty():
    style = CaptionStyle()
    assert words_to_drawtext([], style) == []
