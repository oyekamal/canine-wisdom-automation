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
    )
