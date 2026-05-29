# overlay_library.py
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from overlay_renderer import render_overlay, OverlayConfig

OVERLAYS_DIR = Path(__file__).parent / "assets" / "overlays"


@dataclass
class OverlayRequest:
    channel_slug: str
    template_name: str
    placeholders: dict
    width: int
    height: int
    duration: float


def _content_hash(placeholders: dict) -> str:
    """Deterministic 12-char hash of placeholder content for cache keying."""
    canonical = json.dumps(placeholders, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def get_or_render_overlay(req: OverlayRequest) -> str:
    """
    Return path to a rendered WebM overlay for the given request.
    Renders and caches to assets/overlays/<channel>/<type>/<hash>.webm on first call;
    returns cached path on subsequent calls with identical content.
    """
    cache_key = _content_hash(req.placeholders)
    output_path = OVERLAYS_DIR / req.channel_slug / req.template_name / f"{cache_key}.webm"

    if output_path.exists():
        return str(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    config = OverlayConfig(
        channel_slug=req.channel_slug,
        template_name=req.template_name,
        placeholders=req.placeholders,
        width=req.width,
        height=req.height,
        duration=req.duration,
        output_path=str(output_path),
    )
    render_overlay(config)
    return str(output_path)
