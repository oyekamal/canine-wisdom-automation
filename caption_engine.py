"""
Caption engine: converts word timestamps to ffmpeg drawtext filter expressions.

Style: bold yellow text with black stroke, centered, lower-third, word-by-word reveal.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class CaptionStyle:
    font_path: str = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    font_color: str = "yellow"
    stroke_color: str = "black"
    stroke_width: int = 4
    font_size: int = 72
    x_expr: str = "(w-text_w)/2"
    y_expr: str = "(h*0.72)"
    shadow_x: int = 3
    shadow_y: int = 3


def words_to_drawtext(word_timestamps: List[dict], style: CaptionStyle) -> List[str]:
    """
    Convert word-level timestamps to a list of ffmpeg drawtext filter strings.

    Each string is one drawtext= expression enabled only during that word's time window.
    Caller joins them with commas into the ffmpeg -vf chain.
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
            f"enable='between(t,{start},{end})'"
        )
        filters.append(expr)

    return filters


def build_caption_filter(word_timestamps: List[dict], style: CaptionStyle = None) -> str:
    """
    Build a complete ffmpeg -vf compatible caption filter string.

    Returns comma-joined drawtext expressions, or empty string if no timestamps.
    """
    if style is None:
        style = CaptionStyle()
    filters = words_to_drawtext(word_timestamps, style)
    return ",".join(filters)
