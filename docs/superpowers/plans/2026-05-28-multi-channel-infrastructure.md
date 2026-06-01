# Multi-Channel Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the single-channel harness into a generic multi-channel platform where each channel is a self-contained directory with its own config, credentials, state, and prompt — and the orchestrator accepts a `--channel` argument to run any of them.

**Architecture:** Each channel lives under `channels/<channel-slug>/` with its own `settings.json`, `token.json`, `client_secrets.json`, `prompt.txt`, and `data/` directory. A `ChannelConfig` dataclass loads all channel-specific values. The orchestrator accepts `--channel <slug>` and passes a `ChannelConfig` object through every stage. All existing Canine Wisdom behaviour is preserved exactly — it just moves into `channels/canine-wisdom/`.

**Tech Stack:** Python 3, dataclasses, argparse, existing harness stack (no new dependencies)

---

## Why two plans, not one

The spec covers multi-channel infrastructure AND a full horror channel content pipeline (Reddit harvest, story scoring, Claude rewrite). These are independent. Building horror content modules on a single-channel harness means rewriting them again later. This plan (A) does infrastructure only. Plan B (horror channel) builds on top of it.

---

## Current state — what is hardcoded today

| Thing | Hardcoded location | Must become |
|---|---|---|
| Voice ID | `config.py:122` env default | `channels/<slug>/settings.json` |
| Niche / prompt | `generate_script.py:88` | `channels/<slug>/prompt.txt` |
| Topic clusters | `generate_script.py:119` | `channels/<slug>/settings.json` |
| YouTube settings | `youtube_settings.json` (root) | `channels/<slug>/settings.json` |
| OAuth credentials | `token.json`, `client_secrets.json` (root) | `channels/<slug>/token.json`, `channels/<slug>/client_secrets.json` |
| State + learnings | `harness/data/state.json`, `harness/data/learnings.json` | `channels/<slug>/data/state.json`, `channels/<slug>/data/learnings.json` |
| Category ID | `upload_youtube.py:289` hardcoded `"15"` | `channels/<slug>/settings.json` |
| Orchestrator entry | no args | `--channel <slug>` |

---

## File Map

| File | Action | What changes |
|---|---|---|
| `channels/canine-wisdom/settings.json` | Create | All canine-wisdom channel config extracted here |
| `channels/canine-wisdom/prompt.txt` | Create | Extracted from `generate_script.py` system prompt |
| `channels/canine-wisdom/data/` | Create | Symlink or copy of existing `harness/data/` content |
| `channels/canine-wisdom/client_secrets.json` | Create | Symlink to root `client_secrets.json` (real file stays in root) |
| `channels/canine-wisdom/token.json` | Create | Symlink to root `token.json` |
| `channel_config.py` | Create | `ChannelConfig` dataclass + `load_channel_config(slug)` |
| `config.py` | Modify | `load_config()` accepts optional `channel_config` param; reads voice_id from it |
| `generate_script.py` | Modify | Accept `channel_config`; load niche/clusters/prompt from it |
| `upload_youtube.py` | Modify | `get_youtube_service(channel_config)` and `upload_youtube(channel_config)`; load OAuth from channel dir |
| `harness/storage.py` | Modify | `DATA_DIR` and `STATE_PATH` become functions that accept channel slug |
| `harness/orchestrator.py` | Modify | Add `--channel` argparse; load `ChannelConfig`; pass through all stages |
| `tests/test_channel_config.py` | Create | Tests for `ChannelConfig` loading and validation |

---

### Task 1: Create `channel_config.py` — the ChannelConfig dataclass

**Files:**
- Create: `channel_config.py`
- Create: `tests/test_channel_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_channel_config.py`:

```python
import json
import pytest
from pathlib import Path
from channel_config import ChannelConfig, load_channel_config


def test_load_channel_config_returns_dataclass(tmp_path):
    """load_channel_config reads settings.json and returns a ChannelConfig."""
    ch_dir = tmp_path / "channels" / "test-channel"
    ch_dir.mkdir(parents=True)
    settings = {
        "channel_name": "Test Channel",
        "niche": "test niche",
        "voice_id": "abc123",
        "youtube_category_id": "22",
        "topic_clusters": ["topic a", "topic b"],
        "description_template": "{video_script}\n\n{hashtags}",
        "affiliate_links": {},
    }
    (ch_dir / "settings.json").write_text(json.dumps(settings))

    cfg = load_channel_config("test-channel", channels_root=tmp_path / "channels")

    assert cfg.channel_name == "Test Channel"
    assert cfg.niche == "test niche"
    assert cfg.voice_id == "abc123"
    assert cfg.youtube_category_id == "22"
    assert cfg.topic_clusters == ["topic a", "topic b"]
    assert cfg.channel_dir == ch_dir


def test_load_channel_config_raises_on_missing_channel(tmp_path):
    with pytest.raises(FileNotFoundError, match="Channel 'ghost' not found"):
        load_channel_config("ghost", channels_root=tmp_path / "channels")


def test_load_channel_config_raises_on_missing_required_field(tmp_path):
    ch_dir = tmp_path / "channels" / "bad-channel"
    ch_dir.mkdir(parents=True)
    (ch_dir / "settings.json").write_text(json.dumps({"channel_name": "Bad"}))
    with pytest.raises(KeyError):
        load_channel_config("bad-channel", channels_root=tmp_path / "channels")


def test_data_dir_is_inside_channel_dir(tmp_path):
    ch_dir = tmp_path / "channels" / "test-channel"
    ch_dir.mkdir(parents=True)
    settings = {
        "channel_name": "T", "niche": "n", "voice_id": "v",
        "youtube_category_id": "15", "topic_clusters": [],
        "description_template": "", "affiliate_links": {},
    }
    (ch_dir / "settings.json").write_text(json.dumps(settings))
    cfg = load_channel_config("test-channel", channels_root=tmp_path / "channels")
    assert cfg.data_dir == ch_dir / "data"
    assert cfg.state_path == ch_dir / "data" / "state.json"
```

- [ ] **Step 2: Run test to confirm it fails**

```
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation && source venv/bin/activate && python3 -m pytest tests/test_channel_config.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'channel_config'`

- [ ] **Step 3: Create `channel_config.py`**

```python
from dataclasses import dataclass, field
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
```

- [ ] **Step 4: Run tests — all 4 pass**

```
python3 -m pytest tests/test_channel_config.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add channel_config.py tests/test_channel_config.py
git commit -m "feat: ChannelConfig dataclass and load_channel_config()"
```

---

### Task 2: Create `channels/canine-wisdom/` directory with settings

**Files:**
- Create: `channels/canine-wisdom/settings.json`
- Create: `channels/canine-wisdom/prompt.txt`
- Create: `channels/canine-wisdom/data/` (directory, copy existing harness/data content)

- [ ] **Step 1: Create the channels directory structure**

```bash
mkdir -p channels/canine-wisdom/data
```

- [ ] **Step 2: Create `channels/canine-wisdom/settings.json`**

Read the current `youtube_settings.json` at root to get `description_template` and `affiliate_links`. Then write `channels/canine-wisdom/settings.json` with this exact content (incorporating those values):

```json
{
  "channel_name": "Canine Wisdom",
  "niche": "viral YouTube Shorts scriptwriter for a dog facts channel in 2026",
  "voice_id": "pNInz6obpgDQGcFmaJgB",
  "youtube_category_id": "15",
  "topic_clusters": [
    "dog health",
    "dog behavior",
    "dog breeds",
    "dog training",
    "dog history",
    "dog science",
    "dog fun"
  ],
  "description_template": "🐕 {video_title}\n\n{video_script}\n\n{affiliate_block}\n\n{hashtags}\n\n✨ Subscribe for daily dog facts and tips!",
  "affiliate_links": {
    "dog breeds": {
      "product": "Want to know your dog's breed mix? This DNA test reveals everything.",
      "url": "https://amzn.to/4d1CdKq"
    },
    "dog training": {
      "product": "Keep your dog mentally sharp with this puzzle toy trainers love.",
      "url": "https://amzn.to/4d14ulL"
    },
    "dog behavior": {
      "product": "Does your dog get anxious? This ThunderShirt calms them fast.",
      "url": "https://amzn.to/4whfoeI"
    },
    "dog health": {
      "product": "Support your dog's joints with this vet-recommended supplement.",
      "url": "https://amzn.to/4wjWweX"
    },
    "dog science": {
      "product": "Curious about your dog's breed? This DNA test reveals it all.",
      "url": "https://amzn.to/4d1CdKq"
    },
    "dog history": {
      "product": "Discover your dog's ancient breed origins with this DNA test.",
      "url": "https://amzn.to/4d1CdKq"
    },
    "dog fun": {
      "product": "Keep your dog busy and happy with this top-rated puzzle toy.",
      "url": "https://amzn.to/4d14ulL"
    },
    "dog anxiety": {
      "product": "Does your dog get anxious? This ThunderShirt calms them fast.",
      "url": "https://amzn.to/4whfoeI"
    },
    "dog calming": {
      "product": "Help your anxious dog relax with these vet-recommended calming chews.",
      "url": "https://amzn.to/4d2T15m"
    },
    "dog separation anxiety": {
      "product": "Watch your dog remotely and toss treats with the Furbo Dog Camera.",
      "url": "https://amzn.to/4u0AhZY"
    },
    "senior dog": {
      "product": "Give your senior dog the comfort they deserve with this orthopedic bed.",
      "url": "https://amzn.to/3OWy3Md"
    },
    "dog joint health": {
      "product": "Support aging joints with this vet-recommended supplement.",
      "url": "https://amzn.to/4wjWweX"
    },
    "dog nutrition": {
      "product": "Slow down fast eaters and improve digestion with this slow feeder bowl.",
      "url": "https://amzn.to/4dkXi2Z"
    },
    "dog safety": {
      "product": "Never lose your dog again — real-time GPS tracking with this top-rated tracker.",
      "url": "https://amzn.to/3QQZxU7"
    },
    "default": {
      "product": "Keep your dog mentally stimulated with this top-rated puzzle toy.",
      "url": "https://amzn.to/4d14ulL"
    }
  }
}
```

- [ ] **Step 3: Read `generate_script.py` and extract the system prompt into `channels/canine-wisdom/prompt.txt`**

Read `generate_script.py`. Find the system prompt string passed to Claude (the long string describing the scriptwriter persona, rules, JSON format). Extract it verbatim and write it to `channels/canine-wisdom/prompt.txt`. This file will be read at runtime instead of being hardcoded.

- [ ] **Step 4: Copy existing harness data into channel data dir**

```bash
cp -r harness/data/* channels/canine-wisdom/data/ 2>/dev/null || true
```

- [ ] **Step 5: Create symlinks for OAuth credentials**

```bash
# Keep actual files in root (where they already are), symlink into channel dir
ln -sf "$(pwd)/client_secrets.json" channels/canine-wisdom/client_secrets.json
ln -sf "$(pwd)/token.json" channels/canine-wisdom/token.json
```

- [ ] **Step 6: Verify settings load correctly**

```
python3 -c "
from channel_config import load_channel_config
cfg = load_channel_config('canine-wisdom')
print('channel_name:', cfg.channel_name)
print('voice_id:', cfg.voice_id)
print('data_dir:', cfg.data_dir)
print('state_path:', cfg.state_path)
print('prompt_path:', cfg.prompt_path)
print('✅ canine-wisdom config loads OK')
"
```

Expected: all values printed, no errors.

- [ ] **Step 7: Commit**

```bash
git add channels/
git commit -m "feat: channels/canine-wisdom — extracted settings, prompt, data dir"
```

---

### Task 3: Update `harness/storage.py` to accept channel data dir

**Files:**
- Modify: `harness/storage.py`
- Create: `tests/test_storage_channel.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_storage_channel.py`:

```python
import json
from pathlib import Path
from harness.storage import get_state_path, get_data_dir


def test_get_data_dir_returns_channel_dir(tmp_path):
    cfg_data_dir = tmp_path / "channels" / "test" / "data"
    cfg_data_dir.mkdir(parents=True)

    class FakeCfg:
        data_dir = cfg_data_dir

    result = get_data_dir(FakeCfg())
    assert result == cfg_data_dir


def test_get_state_path_returns_channel_state(tmp_path):
    cfg_data_dir = tmp_path / "channels" / "test" / "data"
    cfg_data_dir.mkdir(parents=True)

    class FakeCfg:
        data_dir = cfg_data_dir
        state_path = cfg_data_dir / "state.json"

    result = get_state_path(FakeCfg())
    assert result == cfg_data_dir / "state.json"


def test_get_data_dir_falls_back_to_global_when_no_cfg():
    from harness.storage import DATA_DIR
    result = get_data_dir(None)
    assert result == DATA_DIR
```

- [ ] **Step 2: Run to confirm failure**

```
python3 -m pytest tests/test_storage_channel.py -v 2>&1 | tail -10
```

Expected: ImportError — `get_state_path`, `get_data_dir` not found.

- [ ] **Step 3: Add `get_data_dir` and `get_state_path` functions to `harness/storage.py`**

Read `harness/storage.py` first. Then append at the bottom:

```python
def get_data_dir(channel_config) -> Path:
    """Return the data directory for the given channel, or global DATA_DIR if None."""
    if channel_config is not None:
        return channel_config.data_dir
    return DATA_DIR


def get_state_path(channel_config) -> Path:
    """Return the state.json path for the given channel, or global STATE_PATH if None."""
    if channel_config is not None:
        return channel_config.state_path
    return STATE_PATH
```

- [ ] **Step 4: Run tests**

```
python3 -m pytest tests/test_storage_channel.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add harness/storage.py tests/test_storage_channel.py
git commit -m "feat: storage.get_data_dir/get_state_path accept channel_config"
```

---

### Task 4: Update `generate_script.py` to accept `channel_config`

**Files:**
- Modify: `generate_script.py`

The goal: `generate_script(channel_config=None)` loads niche, topic clusters, and prompt from `channel_config` when provided; falls back to current hardcoded behaviour when `None` (so existing callers and tests don't break).

- [ ] **Step 1: Read `generate_script.py`** to find:
  - The system prompt string (the hardcoded niche description)
  - Where `topic_clusters` list is defined/used in the prompt
  - The function signature of `generate_script()`

- [ ] **Step 2: Write a test**

Add to `tests/test_generate_script.py` (or create it if it doesn't exist):

```python
import json
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_generate_script_accepts_channel_config_param():
    """generate_script must accept an optional channel_config keyword argument."""
    import inspect
    from generate_script import generate_script
    sig = inspect.signature(generate_script)
    assert "channel_config" in sig.parameters


def test_generate_script_uses_channel_niche_in_prompt():
    """When channel_config provided, its niche appears in the Claude prompt."""
    from generate_script import _build_prompt

    class FakeCfg:
        niche = "horror narration channel for sleepless nights"
        topic_clusters = ["horror", "paranormal"]
        prompt_path = Path("/nonexistent/prompt.txt")  # will fall back to niche
        affiliate_links = {}

    prompt = _build_prompt(FakeCfg())
    assert "horror narration channel" in prompt
    assert "horror" in prompt
```

Run to confirm failure:
```
python3 -m pytest tests/test_generate_script.py::test_generate_script_accepts_channel_config_param tests/test_generate_script.py::test_generate_script_uses_channel_niche_in_prompt -v 2>&1 | tail -10
```

Expected: both fail (no `channel_config` param, no `_build_prompt` function).

- [ ] **Step 3: Refactor `generate_script.py`**

Extract the system prompt construction into a `_build_prompt(channel_config=None)` function. The function:
- If `channel_config` is not None AND `channel_config.prompt_path.exists()`: read the prompt file and return it (with topic_clusters substituted in if needed).
- Otherwise: return the existing hardcoded prompt string unchanged.

Change the `generate_script()` function signature to:
```python
def generate_script(channel_config=None) -> dict:
```

Pass `channel_config` through to `_build_prompt()` for the system prompt.

The topic_clusters in the JSON response schema should come from `channel_config.topic_clusters` if provided, otherwise use the existing hardcoded list.

- [ ] **Step 4: Run tests**

```
python3 -m pytest tests/test_generate_script.py -v 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add generate_script.py tests/test_generate_script.py
git commit -m "feat: generate_script accepts channel_config — niche/clusters/prompt from channel"
```

---

### Task 5: Update `upload_youtube.py` to accept `channel_config`

**Files:**
- Modify: `upload_youtube.py`

Goal: `get_youtube_service(channel_config=None)` and `upload_youtube(channel_config=None)` load OAuth credentials from `channel_config.channel_dir` when provided; fall back to root directory when None.

- [ ] **Step 1: Write the test**

Add to `tests/test_upload_youtube.py` (or create):

```python
import inspect
from upload_youtube import get_youtube_service, upload_youtube


def test_get_youtube_service_accepts_channel_config():
    sig = inspect.signature(get_youtube_service)
    assert "channel_config" in sig.parameters


def test_upload_youtube_accepts_channel_config():
    sig = inspect.signature(upload_youtube)
    assert "channel_config" in sig.parameters
```

Run to confirm failure:
```
python3 -m pytest tests/test_upload_youtube.py::test_get_youtube_service_accepts_channel_config tests/test_upload_youtube.py::test_upload_youtube_accepts_channel_config -v 2>&1 | tail -10
```

- [ ] **Step 2: Update `get_youtube_service()` in `upload_youtube.py`**

Change signature:
```python
def get_youtube_service(channel_config=None):
```

Replace the hardcoded path lines:
```python
    base_dir = Path(__file__).parent
    token_file = base_dir / "token.json"
    client_secrets_file = base_dir / "client_secrets.json"
```
with:
```python
    base_dir = channel_config.channel_dir if channel_config is not None else Path(__file__).parent
    token_file = base_dir / "token.json"
    client_secrets_file = base_dir / "client_secrets.json"
```

- [ ] **Step 3: Update `upload_youtube()` in `upload_youtube.py`**

Change signature:
```python
def upload_youtube(channel_config=None) -> str:
```

Inside the function, find where `youtube_settings_file` is loaded:
```python
    youtube_settings_file = base_dir / "youtube_settings.json"
```
Replace with:
```python
    base_dir = channel_config.channel_dir if channel_config is not None else Path(__file__).parent
    youtube_settings_file = base_dir / "youtube_settings.json"
```

Also find where `get_youtube_service()` is called inside `do_upload()`:
```python
        youtube = get_youtube_service()
```
Replace with:
```python
        youtube = get_youtube_service(channel_config)
```

Also find `categoryId`:
```python
                "categoryId": "15"
```
Replace with:
```python
                "categoryId": channel_config.youtube_category_id if channel_config else "15"
```

If `channel_config` is provided, use `channel_config.description_template` and `channel_config.affiliate_links` instead of loading from `youtube_settings_file`. Add this block right after `base_dir` is set:

```python
    if channel_config is not None:
        yt_settings = {
            "description_template": channel_config.description_template,
            "affiliate_links": channel_config.affiliate_links,
        }
    elif youtube_settings_file.exists():
        with open(youtube_settings_file, "r") as f:
            yt_settings = json.load(f)
    else:
        yt_settings = {}
```

Remove the old `if youtube_settings_file.exists():` block and replace with just using `yt_settings` (already set above).

- [ ] **Step 4: Run tests**

```
python3 -m pytest tests/test_upload_youtube.py -v 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add upload_youtube.py tests/test_upload_youtube.py
git commit -m "feat: upload_youtube accepts channel_config — OAuth and settings from channel dir"
```

---

### Task 6: Update `harness/orchestrator.py` to accept `--channel` argument

**Files:**
- Modify: `harness/orchestrator.py`

- [ ] **Step 1: Write the test**

Add to `harness/tests/test_orchestrator_channel.py`:

```python
import sys
import pytest
from unittest.mock import patch, MagicMock


def test_orchestrator_accepts_channel_arg():
    """run_pipeline must accept a channel_config keyword argument."""
    import inspect
    from harness.orchestrator import run_pipeline
    sig = inspect.signature(run_pipeline)
    assert "channel_config" in sig.parameters


def test_orchestrator_defaults_to_canine_wisdom(monkeypatch):
    """With no --channel arg, orchestrator loads canine-wisdom channel."""
    from harness.orchestrator import _load_channel_from_args
    with patch("sys.argv", ["orchestrator"]):
        cfg = _load_channel_from_args()
    assert cfg.slug == "canine-wisdom"
```

Run to confirm failure:
```
python3 -m pytest harness/tests/test_orchestrator_channel.py -v 2>&1 | tail -10
```

- [ ] **Step 2: Add argparse and `_load_channel_from_args()` to `harness/orchestrator.py`**

Add at the top with other imports:
```python
import argparse
from channel_config import load_channel_config
```

Add this function before `run_pipeline()`:
```python
def _load_channel_from_args():
    """Parse --channel slug from CLI args and return its ChannelConfig."""
    parser = argparse.ArgumentParser(description="Canine Wisdom Harness")
    parser.add_argument(
        "--channel", default="canine-wisdom",
        help="Channel slug to run (must exist under channels/)"
    )
    args, _ = parser.parse_known_args()
    return load_channel_config(args.channel)
```

- [ ] **Step 3: Update `run_pipeline()` signature**

Change:
```python
def run_pipeline() -> dict:
```
to:
```python
def run_pipeline(channel_config=None) -> dict:
```

At the very top of `run_pipeline()`, add:
```python
    if channel_config is None:
        channel_config = _load_channel_from_args()
```

- [ ] **Step 4: Thread `channel_config` through all calls inside `run_pipeline()`**

Find every call that needs it and add `channel_config=channel_config`:

**Storage calls** — replace `atomic_read(STATE_PATH)` and `atomic_write(STATE_PATH, ...)` with channel-aware paths:
```python
# At top of run_pipeline, after channel_config is set:
from harness.storage import get_state_path
_state_path = get_state_path(channel_config)
```
Then replace all `STATE_PATH` references inside `run_pipeline()` with `_state_path`.

**generate_script call:**
```python
metadata = generate_script(channel_config=channel_config)
```

**upload_youtube call:**
```python
video_url = upload_youtube(channel_config=channel_config)
```

**pick_format call** — pass recent_runs from channel state (already done via `_state_path`).

- [ ] **Step 5: Update `__main__` block**

Replace:
```python
if __name__ == "__main__":
    result = run_pipeline()
```
with:
```python
if __name__ == "__main__":
    _cfg = _load_channel_from_args()
    result = run_pipeline(channel_config=_cfg)
```

- [ ] **Step 6: Run tests**

```
python3 -m pytest harness/tests/test_orchestrator_channel.py tests/test_channel_config.py -v 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add harness/orchestrator.py harness/tests/test_orchestrator_channel.py
git commit -m "feat: orchestrator accepts --channel arg, threads ChannelConfig through pipeline"
```

---

### Task 7: Smoke test — run canine-wisdom channel via new flag

- [ ] **Step 1: Verify canine-wisdom channel config loads**

```
python3 -c "
from channel_config import load_channel_config
cfg = load_channel_config('canine-wisdom')
print('slug:', cfg.slug)
print('channel_name:', cfg.channel_name)
print('voice_id:', cfg.voice_id)
print('state_path:', cfg.state_path)
print('token exists:', (cfg.channel_dir / 'token.json').exists())
print('✅ OK')
"
```

Expected: all fields printed, token exists = True.

- [ ] **Step 2: Run the pipeline with explicit channel flag**

```
source venv/bin/activate && python3 -m harness.orchestrator --channel canine-wisdom 2>&1
```

Watch for:
- No errors loading channel config
- `🎬 Format selected:` log line still appears
- Video uploaded successfully
- `🎉 Short is LIVE` in output

- [ ] **Step 3: Run full test suite**

```
python3 -m pytest tests/ harness/tests/ -q 2>&1 | tail -15
```

Expected: same pass/fail count as before (7 pre-existing failures, rest pass).

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: canine-wisdom channel verified via --channel flag"
```

---

## Self-Review

**Spec coverage:**
- ✅ Multi-channel: each channel under `channels/<slug>/` — Tasks 1–2
- ✅ Separate OAuth per channel — Task 5
- ✅ Separate settings (voice, niche, template, affiliate links) per channel — Tasks 1–2
- ✅ Separate state/data per channel — Tasks 2–3
- ✅ Separate prompt per channel — Task 2 + Task 4
- ✅ Orchestrator accepts `--channel` flag — Task 6
- ✅ Canine Wisdom behaviour fully preserved — Task 7
- ✅ Adding a new channel = create `channels/<slug>/` dir only — no code changes needed
- ✅ Backward compatible: all functions default to `channel_config=None` → existing behaviour

**Placeholder scan:** None found — all code blocks are complete.

**Type consistency:**
- `channel_config` parameter name used consistently across all functions
- `ChannelConfig.data_dir` and `ChannelConfig.state_path` used consistently in storage functions
- `channel_config.channel_dir` used consistently in upload_youtube and get_youtube_service
