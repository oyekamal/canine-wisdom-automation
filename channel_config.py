from dataclasses import dataclass
from pathlib import Path
import json

CHANNELS_ROOT = Path(__file__).parent / "channels"

REQUIRED_FIELDS = [
    "channel_name", "niche", "voice_id",
    "youtube_category_id", "topic_clusters",
    "description_template", "affiliate_links",
]


@dataclass
class ChannelConfig:
    slug: str
    channel_name: str
    niche: str
    voice_id: str
    youtube_category_id: str
    topic_clusters: list
    description_template: str
    affiliate_links: dict
    channel_dir: Path
    data_dir: Path
    state_path: Path
    prompt_path: Path
    footage_dir: Path
    music_dir: Path
    overlay_templates: dict
    anthropic_max_tokens: int


def load_channel_config(slug: str, channels_root: Path = CHANNELS_ROOT) -> ChannelConfig:
    channel_dir = channels_root / slug
    settings_file = channel_dir / "settings.json"

    if not channel_dir.exists():
        raise FileNotFoundError(f"Channel '{slug}' not found at {channel_dir}")

    settings = json.loads(settings_file.read_text(encoding="utf-8"))

    for field_name in REQUIRED_FIELDS:
        _ = settings[field_name]  # raises KeyError if missing

    data_dir = channel_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    footage_dir_str = settings.get("footage_dir", "dog_footage")
    footage_dir = (Path(footage_dir_str) if Path(footage_dir_str).is_absolute()
                   else Path(__file__).parent / footage_dir_str)

    music_dir_str = settings.get("music_dir", "assets/music")
    music_dir = (Path(music_dir_str) if Path(music_dir_str).is_absolute()
                 else Path(__file__).parent / music_dir_str)

    return ChannelConfig(
        slug=slug,
        channel_name=settings["channel_name"],
        niche=settings["niche"],
        voice_id=settings["voice_id"],
        youtube_category_id=settings["youtube_category_id"],
        topic_clusters=settings["topic_clusters"],
        description_template=settings["description_template"],
        affiliate_links=settings["affiliate_links"],
        channel_dir=channel_dir,
        data_dir=data_dir,
        state_path=data_dir / "state.json",
        prompt_path=channel_dir / "prompt.txt",
        footage_dir=footage_dir,
        music_dir=music_dir,
        overlay_templates={
            "hook": settings.get("overlay_hook_template", "hook"),
            "lower_third": settings.get("overlay_lower_third_template", "lower-third"),
        },
        anthropic_max_tokens=settings.get("anthropic_max_tokens", 500),
    )
