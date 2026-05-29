# overlay_renderer.py
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

HYPERFRAMES_DIR = Path(__file__).parent / "hyperframes"
TEMPLATES_DIR = HYPERFRAMES_DIR / "templates"
PRELOAD_CJS = HYPERFRAMES_DIR / "preload-require.cjs"


@dataclass
class OverlayConfig:
    channel_slug: str
    template_name: str
    placeholders: dict
    width: int
    height: int
    duration: float
    output_path: str


def render_overlay(config: OverlayConfig) -> str:
    """
    Fill template placeholders, render via HyperFrames Node CLI,
    return path to output WebM. Raises RuntimeError on render failure.
    """
    template_path = TEMPLATES_DIR / config.channel_slug / f"{config.template_name}.html"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    html = template_path.read_text(encoding="utf-8")
    for placeholder, value in config.placeholders.items():
        html = html.replace(placeholder, str(value))

    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False, encoding="utf-8") as f:
        f.write(html)
        tmp_html = f.name

    try:
        exit_code = _call_node_renderer(
            template=tmp_html,
            output=config.output_path,
            width=config.width,
            height=config.height,
        )
        if exit_code != 0:
            raise RuntimeError(f"HyperFrames render failed (exit {exit_code}): {config.output_path}")
    finally:
        os.unlink(tmp_html)

    return config.output_path


def _call_node_renderer(template: str, output: str, width: int, height: int) -> int:
    render_js = HYPERFRAMES_DIR / "render.js"
    repo_root = Path(__file__).parent
    result = subprocess.run(
        ["node",
         f"--require={PRELOAD_CJS}",
         str(render_js),
         "--template", template,
         "--output", output,
         "--width", str(width),
         "--height", str(height)],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    return result.returncode
