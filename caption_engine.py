"""
Caption engine: generates ASS subtitle file for word-by-word captions
and builds ffmpeg filter strings for hook overlays.

ASS format handles per-word timing cleanly without ffmpeg -vf comma parsing issues.
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class CaptionStyle:
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_color: str = "white"
    stroke_color: str = "black"
    stroke_width: int = 6
    font_size: int = 88
    x_expr: str = "(w-text_w)/2"
    y_expr: str = "(h*0.72)"
    shadow_x: int = 4
    shadow_y: int = 4


def _seconds_to_ass_time(seconds: float) -> str:
    """Convert float seconds to ASS time format H:MM:SS.cs"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_color(color_name: str) -> str:
    """Convert color name to ASS BGR hex format (&H00BBGGRR)."""
    colors = {
        "yellow": "&H0000FFFF",
        "white": "&H00FFFFFF",
        "black": "&H00000000",
        "red": "&H000000FF",
        "blue": "&H00FF0000",
    }
    return colors.get(color_name.lower(), "&H00FFFFFF")


def write_word_ass(word_timestamps: List[dict], style: CaptionStyle,
                   video_width: int = 1080, video_height: int = 1920,
                   hook_overlay: str = None) -> Optional[str]:
    """
    Write an ASS subtitle file with one event per word plus an optional hook overlay.

    Returns path to the temp ASS file, or None if nothing to render.
    """
    if not word_timestamps and not hook_overlay:
        return None

    font_color_ass = _ass_color(style.font_color)
    stroke_color_ass = _ass_color(style.stroke_color)
    bottom_margin = int(video_height * 0.18)
    hook_top_margin = int(video_height * 0.35)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,Arial Black,{style.font_size},{font_color_ass},&H000000FF,{stroke_color_ass},&H00000000,-1,0,0,0,100,100,0,0,1,{style.stroke_width},{style.shadow_x},2,10,10,{bottom_margin},1
Style: Hook,Arial Black,100,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,5,8,10,10,{hook_top_margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [header.rstrip()]

    if hook_overlay:
        hook_text = hook_overlay.replace("{", "").replace("}", "").replace("\\", "")
        lines.append(f"Dialogue: 1,0:00:00.00,0:00:01.50,Hook,,0,0,0,,{hook_text}")

    for wt in word_timestamps:
        start_t = _seconds_to_ass_time(wt["start"])
        end_t = _seconds_to_ass_time(wt["end"])
        word = wt["word"].replace("{", "").replace("}", "").replace("\\", "")
        lines.append(f"Dialogue: 0,{start_t},{end_t},Word,,0,0,0,,{word}")

    tmp = tempfile.NamedTemporaryFile(suffix=".ass", delete=False, mode="w", encoding="utf-8")
    tmp.write("\n".join(lines))
    tmp.close()
    return tmp.name


def words_to_drawtext(word_timestamps: List[dict], style: CaptionStyle) -> List[str]:
    """
    Legacy: convert word timestamps to drawtext filter strings.
    Kept for test compatibility. Use write_word_ass + subtitles= filter in production.
    """
    if not word_timestamps:
        return []

    filters = []
    for wt in word_timestamps:
        word = wt["word"].replace("'", "\\'").replace(":", "\\:")
        start = wt["start"]
        end = wt["end"]

        expr = (
            f"drawtext="
            f"fontfile='{style.font_path}':"
            f"text='{word}':"
            f"fontcolor={style.font_color}:"
            f"fontsize={style.font_size}:"
            f"borderw={style.stroke_width}:"
            f"bordercolor={style.stroke_color}:"
            f"shadowx={style.shadow_x}:"
            f"shadowy={style.shadow_y}:"
            f"x={style.x_expr}:"
            f"y={style.y_expr}:"
            f"enable='gte(t\\,{start})*lte(t\\,{end})'"
        )
        filters.append(expr)

    return filters


def build_caption_filter(word_timestamps: List[dict], style: CaptionStyle = None) -> str:
    """
    Build an ffmpeg filter string for word-by-word captions (legacy drawtext approach).
    For production, use write_word_ass() + subtitles= filter instead.
    """
    if style is None:
        style = CaptionStyle()
    filters = words_to_drawtext(word_timestamps, style)
    return ",".join(filters)
