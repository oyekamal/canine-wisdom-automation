# Canine Wisdom Harness — Session 1: Foundation + Evals

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the existing linear pipeline in an eval-gated harness that scores every artifact before upload and writes an incident report on any eval failure.

**Architecture:** A new `harness/` directory sits alongside the existing scripts. `harness/orchestrator.py` is the new daily entry point — it calls the existing pipeline functions and runs evals after each artifact is produced. `harness/storage.py` handles all JSON I/O atomically. `harness/evals/` contains 8 eval modules (5 LLM-judge, 3 deterministic). Existing scripts (`generate_script.py`, `build_video.py`, etc.) are not modified.

**Tech Stack:** Python 3.10+, anthropic SDK (already installed), ffprobe (already installed via ffmpeg), jsonschema, pytest

---

## File Map

| File | Status | Responsibility |
|------|--------|----------------|
| `harness/__init__.py` | Create | Package marker |
| `harness/storage.py` | Create | Atomic JSON read/write, file locking for state.json |
| `harness/orchestrator.py` | Create | Daily entry point — pipeline + evals + incident on failure |
| `harness/evals/__init__.py` | Create | Package marker |
| `harness/evals/base.py` | Create | `EvalResult` dataclass + shared `run_eval()` helper |
| `harness/evals/hook_eval.py` | Create | LLM judge: first-3-sec hook strength ≥7/10 |
| `harness/evals/script_eval.py` | Create | LLM judge: accuracy, novelty, pacing ≥7/10 |
| `harness/evals/title_eval.py` | Create | LLM judge: CTR-predictor vs generic titles ≥7/10 |
| `harness/evals/thumbnail_eval.py` | Create | Placeholder — returns 8.0/pass (thumbnail gen is Session 3) |
| `harness/evals/description_eval.py` | Create | LLM judge: SEO keyword coverage, CTA, length ≥7/10 |
| `harness/evals/audio_eval.py` | Create | Deterministic: loudness via ffprobe, length >10s, <90s |
| `harness/evals/video_eval.py` | Create | Deterministic: resolution 1080x1920, no zero-size file |
| `harness/evals/channel_eval.py` | Create | Placeholder — returns pass (analytics is Session 3) |
| `harness/data/.gitkeep` | Create | Ensure data dir is tracked |
| `harness/data/state.json` | Create | Initial global state |
| `harness/CHANGELOG.md` | Create | Initialized, auto-updated by healer later |
| `harness/README.md` | Create | How to run, extend, bound the self-healing loop |
| `harness/tests/__init__.py` | Create | Package marker |
| `harness/tests/test_storage.py` | Create | Atomic write, lock contention, schema validation |
| `harness/tests/test_evals.py` | Create | All 8 evals with fixture data |
| `harness/tests/test_orchestrator.py` | Create | Orchestrator integration test (mocked pipeline) |
| `requirements.txt` | Modify | Add jsonschema |

---

## Task 1: Project Scaffold + Storage Layer

**Files:**
- Create: `harness/__init__.py`
- Create: `harness/storage.py`
- Create: `harness/data/.gitkeep`
- Create: `harness/data/state.json`
- Create: `harness/tests/__init__.py`
- Create: `harness/tests/test_storage.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Create directory structure**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
mkdir -p harness/evals harness/tests harness/data harness/data/performance harness/data/competitors harness/data/topics harness/data/eval_runs harness/data/incidents harness/data/comments harness/data/thumbnails
touch harness/__init__.py harness/evals/__init__.py harness/tests/__init__.py harness/data/.gitkeep
```

- [ ] **Step 2: Add jsonschema to requirements.txt**

Open `requirements.txt` and add at the end:
```
jsonschema>=4.0.0
```

Install it:
```bash
pip install jsonschema
```

- [ ] **Step 3: Write the failing tests for storage.py**

Create `harness/tests/test_storage.py`:

```python
import fcntl
import json
import os
import threading
import time
from pathlib import Path

import pytest

from harness.storage import atomic_write, atomic_read, lock_state, STATE_PATH


@pytest.fixture
def tmp_json(tmp_path):
    return tmp_path / "test.json"


def test_atomic_write_creates_file(tmp_json):
    atomic_write(tmp_json, {"key": "value"})
    assert tmp_json.exists()


def test_atomic_write_content_is_correct(tmp_json):
    atomic_write(tmp_json, {"score": 42, "name": "rex"})
    data = json.loads(tmp_json.read_text())
    assert data["score"] == 42
    assert data["name"] == "rex"


def test_atomic_write_is_pretty_printed(tmp_json):
    atomic_write(tmp_json, {"a": 1})
    content = tmp_json.read_text()
    assert "\n" in content  # pretty-printed, not one line


def test_atomic_write_no_tmp_file_left(tmp_json):
    atomic_write(tmp_json, {"x": 1})
    tmp_file = tmp_json.with_suffix(".tmp")
    assert not tmp_file.exists()


def test_atomic_read_returns_dict(tmp_json):
    atomic_write(tmp_json, {"hello": "world"})
    data = atomic_read(tmp_json)
    assert data == {"hello": "world"}


def test_atomic_read_missing_file_raises(tmp_json):
    with pytest.raises(FileNotFoundError):
        atomic_read(tmp_json)


def test_atomic_write_overwrites_existing(tmp_json):
    atomic_write(tmp_json, {"v": 1})
    atomic_write(tmp_json, {"v": 2})
    data = atomic_read(tmp_json)
    assert data["v"] == 2


def test_concurrent_writes_do_not_corrupt(tmp_json):
    """Two threads writing simultaneously should not corrupt the file."""
    errors = []

    def writer(value):
        try:
            for _ in range(20):
                atomic_write(tmp_json, {"value": value})
        except Exception as e:
            errors.append(e)

    t1 = threading.Thread(target=writer, args=(1,))
    t2 = threading.Thread(target=writer, args=(2,))
    t1.start(); t2.start()
    t1.join(); t2.join()

    assert not errors
    data = atomic_read(tmp_json)
    assert data["value"] in (1, 2)  # one writer wins, file is valid JSON


def test_lock_state_is_context_manager(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.storage.STATE_PATH", tmp_path / "state.json")
    atomic_write(tmp_path / "state.json", {"locked": False})
    with lock_state() as state:
        assert isinstance(state, dict)
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
python -m pytest harness/tests/test_storage.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'harness.storage'`

- [ ] **Step 5: Implement storage.py**

Create `harness/storage.py`:

```python
import fcntl
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
STATE_PATH = DATA_DIR / "state.json"


def atomic_write(path: Path, data: Any) -> None:
    """Write JSON atomically: write to .tmp, fsync, rename."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    content = json.dumps(data, indent=2, sort_keys=True)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    tmp.rename(path)


def atomic_read(path: Path) -> Any:
    """Read JSON from path. Raises FileNotFoundError if missing."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def lock_state():
    """Context manager: acquire exclusive flock on state.json, yield parsed state."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        atomic_write(STATE_PATH, {})
    with open(STATE_PATH, "r+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            state = json.loads(f.read() or "{}")
            yield state
            f.seek(0)
            f.truncate()
            f.write(json.dumps(state, indent=2, sort_keys=True))
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest harness/tests/test_storage.py -v
```

Expected: all 9 tests PASS

- [ ] **Step 7: Create initial state.json**

Create `harness/data/state.json`:

```json
{
  "competitor_channels": [],
  "config": {
    "eval_pass_threshold": 7,
    "max_competitors": 5,
    "post_hour_local": 9,
    "thumbnail_api": null
  },
  "current_kpis": {
    "avg_ctr_7d": null,
    "avg_views_7d": null,
    "subscribers": null,
    "watch_time_minutes_7d": null
  },
  "last_run": null,
  "last_weekly_eval": null
}
```

- [ ] **Step 8: Commit**

```bash
git add harness/ requirements.txt
git commit -m "feat: harness scaffold + atomic storage layer"
```

---

## Task 2: Eval Base + LLM Judge Evals

**Files:**
- Create: `harness/evals/base.py`
- Create: `harness/evals/hook_eval.py`
- Create: `harness/evals/script_eval.py`
- Create: `harness/evals/title_eval.py`
- Create: `harness/evals/description_eval.py`
- Create: `harness/evals/thumbnail_eval.py`
- Create: `harness/evals/channel_eval.py`

- [ ] **Step 1: Write failing tests for evals base + LLM evals**

Create `harness/tests/test_evals.py` (initial section — LLM evals):

```python
import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from harness.evals.base import EvalResult, run_eval
from harness.evals.hook_eval import hook_eval
from harness.evals.script_eval import script_eval
from harness.evals.title_eval import title_eval
from harness.evals.description_eval import description_eval
from harness.evals.thumbnail_eval import thumbnail_eval
from harness.evals.channel_eval import channel_eval


# ── fixtures ──────────────────────────────────────────────────────────────────

GOOD_HOOK = "Did you know dogs can detect cancer before doctors can? Here's the proof."
WEAK_HOOK = "Today we will talk about some interesting dog facts that you may or may not know."

GOOD_SCRIPT = (
    "Did you know dogs can detect cancer before doctors can? "
    "Studies show trained dogs identify tumors with 97% accuracy. "
    "One Golden Retriever named Bear saved 12 lives in a single year. "
    "Follow for daily dog facts!"
)
BAD_SCRIPT = "Dogs are good. They are loyal. They like to play. Follow for daily dog facts!"

GOOD_TITLE = "Dogs Detect Cancer Before Doctors 🐕"
BAD_TITLE = "dog facts video number 47"

GOOD_DESCRIPTION = (
    "🐕 Dogs can smell cancer with 97% accuracy! Watch to discover how. "
    "#dogs #dogfacts #shorts #cancerdetection #animalsareamazing "
    "Follow for daily dog wisdom!"
)
BAD_DESCRIPTION = "dog video"


# ── helper: mock a Claude response with a given score ─────────────────────────

def make_claude_response(score: float, reasoning: str = "test reasoning"):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock()]
    mock_msg.content[0].text = json.dumps({"score": score, "reasoning": reasoning})
    return mock_msg


# ── EvalResult ────────────────────────────────────────────────────────────────

def test_eval_result_passed_when_score_above_threshold():
    r = EvalResult(eval_name="hook_eval", score=8.0, threshold=7.0, reasoning="good")
    assert r.passed is True


def test_eval_result_failed_when_score_below_threshold():
    r = EvalResult(eval_name="hook_eval", score=5.0, threshold=7.0, reasoning="weak")
    assert r.passed is False


def test_eval_result_passed_at_exact_threshold():
    r = EvalResult(eval_name="hook_eval", score=7.0, threshold=7.0, reasoning="ok")
    assert r.passed is True


# ── hook_eval ─────────────────────────────────────────────────────────────────

def test_hook_eval_passes_strong_hook():
    with patch("harness.evals.hook_eval.Anthropic") as MockAnthopic:
        MockAnthopic.return_value.messages.create.return_value = make_claude_response(8.5)
        result = hook_eval(GOOD_HOOK)
    assert result.passed is True
    assert result.score == 8.5
    assert result.eval_name == "hook_eval"


def test_hook_eval_fails_weak_hook():
    with patch("harness.evals.hook_eval.Anthropic") as MockAnthopic:
        MockAnthopic.return_value.messages.create.return_value = make_claude_response(4.0)
        result = hook_eval(WEAK_HOOK)
    assert result.passed is False


# ── script_eval ───────────────────────────────────────────────────────────────

def test_script_eval_passes_good_script():
    with patch("harness.evals.script_eval.Anthropic") as MockAnthopic:
        MockAnthopic.return_value.messages.create.return_value = make_claude_response(8.0)
        result = script_eval(GOOD_SCRIPT, recent_topics=[])
    assert result.passed is True


def test_script_eval_fails_bad_script():
    with patch("harness.evals.script_eval.Anthropic") as MockAnthopic:
        MockAnthopic.return_value.messages.create.return_value = make_claude_response(3.0)
        result = script_eval(BAD_SCRIPT, recent_topics=[])
    assert result.passed is False


def test_script_eval_includes_recent_topics_in_prompt():
    captured_prompt = {}
    def fake_create(**kwargs):
        captured_prompt["content"] = kwargs["messages"][0]["content"]
        return make_claude_response(8.0)
    with patch("harness.evals.script_eval.Anthropic") as MockAnthopic:
        MockAnthopic.return_value.messages.create.side_effect = fake_create
        script_eval(GOOD_SCRIPT, recent_topics=["dogs sleep", "dog paws"])
    assert "dogs sleep" in captured_prompt["content"]


# ── title_eval ────────────────────────────────────────────────────────────────

def test_title_eval_passes_good_title():
    with patch("harness.evals.title_eval.Anthropic") as MockAnthopic:
        MockAnthopic.return_value.messages.create.return_value = make_claude_response(7.5)
        result = title_eval(GOOD_TITLE)
    assert result.passed is True


def test_title_eval_fails_bad_title():
    with patch("harness.evals.title_eval.Anthropic") as MockAnthopic:
        MockAnthopic.return_value.messages.create.return_value = make_claude_response(2.0)
        result = title_eval(BAD_TITLE)
    assert result.passed is False


# ── description_eval ──────────────────────────────────────────────────────────

def test_description_eval_passes_good_description():
    with patch("harness.evals.description_eval.Anthropic") as MockAnthopic:
        MockAnthopic.return_value.messages.create.return_value = make_claude_response(8.0)
        result = description_eval(GOOD_DESCRIPTION)
    assert result.passed is True


def test_description_eval_fails_bad_description():
    with patch("harness.evals.description_eval.Anthropic") as MockAnthopic:
        MockAnthopic.return_value.messages.create.return_value = make_claude_response(1.0)
        result = description_eval(BAD_DESCRIPTION)
    assert result.passed is False


# ── thumbnail_eval (placeholder) ──────────────────────────────────────────────

def test_thumbnail_eval_always_passes():
    result = thumbnail_eval(variants=[])
    assert result.passed is True
    assert result.score == 8.0


# ── channel_eval (placeholder) ────────────────────────────────────────────────

def test_channel_eval_always_passes():
    result = channel_eval(current_kpis={}, prior_kpis={})
    assert result.passed is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest harness/tests/test_evals.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'harness.evals.base'`

- [ ] **Step 3: Implement base.py**

Create `harness/evals/base.py`:

```python
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from harness.storage import atomic_write, DATA_DIR


@dataclass
class EvalResult:
    eval_name: str
    score: float
    threshold: float
    reasoning: str
    passed: bool = field(init=False)

    def __post_init__(self):
        self.passed = self.score >= self.threshold


def save_eval_result(result: EvalResult, video_id: str) -> None:
    """Persist eval result to data/eval_runs/{date}/{video_id}/{eval_name}.json."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    out_dir = DATA_DIR / "eval_runs" / date_str / video_id
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "eval": result.eval_name,
        "video_id": video_id,
        "run_at": datetime.now().isoformat(),
        "score": result.score,
        "passed": result.passed,
        "threshold": result.threshold,
        "reasoning": result.reasoning,
    }
    atomic_write(out_dir / f"{result.eval_name}.json", record)


def _parse_llm_score(text: str, eval_name: str) -> tuple[float, str]:
    """Extract score and reasoning from Claude JSON response."""
    try:
        data = json.loads(text)
        return float(data["score"]), str(data.get("reasoning", ""))
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        raise ValueError(f"{eval_name}: failed to parse LLM response: {e}\nRaw: {text}")
```

- [ ] **Step 4: Implement hook_eval.py**

Create `harness/evals/hook_eval.py`:

```python
import os
from anthropic import Anthropic
from harness.evals.base import EvalResult, _parse_llm_score

THRESHOLD = 7.0
EVAL_NAME = "hook_eval"

PROMPT = """\
You are a YouTube Shorts expert evaluating the hook strength of a dog-facts video.
The hook is the FIRST sentence of the script — it must create instant curiosity or emotion.

Rate this hook from 0–10, where:
- 0–4: weak (generic, boring, no surprise)
- 5–6: average (mild interest but forgettable)
- 7–8: good (creates clear curiosity or emotion)
- 9–10: excellent (stops the scroll immediately)

Hook to evaluate:
{hook}

Respond ONLY with valid JSON, no markdown:
{{"score": <float 0-10>, "reasoning": "<one sentence>"}}"""


def hook_eval(hook_text: str) -> EvalResult:
    """Score the first-sentence hook. Threshold: 7/10."""
    client = Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": PROMPT.format(hook=hook_text)}],
    )
    score, reasoning = _parse_llm_score(msg.content[0].text, EVAL_NAME)
    return EvalResult(eval_name=EVAL_NAME, score=score, threshold=THRESHOLD, reasoning=reasoning)
```

- [ ] **Step 5: Implement script_eval.py**

Create `harness/evals/script_eval.py`:

```python
from anthropic import Anthropic
from harness.evals.base import EvalResult, _parse_llm_score
from typing import list as List

THRESHOLD = 7.0
EVAL_NAME = "script_eval"

PROMPT = """\
You are a YouTube Shorts expert evaluating a dog-facts script.

Score the script 0–10 across three dimensions, then give a single combined score:
- Factual accuracy (does it sound credible, not invented?)
- Novelty (is this topic fresh vs these recent topics: {recent_topics})
- Pacing (is it energetic, conversational, under 60 words?)

Script:
{script}

Respond ONLY with valid JSON, no markdown:
{{"score": <float 0-10>, "reasoning": "<one sentence covering all three>"}}"""


def script_eval(script_text: str, recent_topics: list) -> EvalResult:
    """Score full script for accuracy, novelty, and pacing. Threshold: 7/10."""
    client = Anthropic()
    topics_str = ", ".join(recent_topics) if recent_topics else "none"
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": PROMPT.format(
            script=script_text, recent_topics=topics_str
        )}],
    )
    score, reasoning = _parse_llm_score(msg.content[0].text, EVAL_NAME)
    return EvalResult(eval_name=EVAL_NAME, score=score, threshold=THRESHOLD, reasoning=reasoning)
```

- [ ] **Step 6: Implement title_eval.py**

Create `harness/evals/title_eval.py`:

```python
from anthropic import Anthropic
from harness.evals.base import EvalResult, _parse_llm_score

THRESHOLD = 7.0
EVAL_NAME = "title_eval"

PROMPT = """\
You are a YouTube Shorts CTR expert evaluating a video title for a dog-facts channel.

Score the title 0–10 where:
- 0–4: generic, no click-bait, too long or vague
- 5–6: okay but forgettable
- 7–8: creates curiosity, under 60 chars, emotionally engaging
- 9–10: scroll-stopper, uses numbers/surprise/emotion perfectly

Title: {title}

Respond ONLY with valid JSON, no markdown:
{{"score": <float 0-10>, "reasoning": "<one sentence>"}}"""


def title_eval(title: str) -> EvalResult:
    """Score the video title for CTR potential. Threshold: 7/10."""
    client = Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": PROMPT.format(title=title)}],
    )
    score, reasoning = _parse_llm_score(msg.content[0].text, EVAL_NAME)
    return EvalResult(eval_name=EVAL_NAME, score=score, threshold=THRESHOLD, reasoning=reasoning)
```

- [ ] **Step 7: Implement description_eval.py**

Create `harness/evals/description_eval.py`:

```python
from anthropic import Anthropic
from harness.evals.base import EvalResult, _parse_llm_score

THRESHOLD = 7.0
EVAL_NAME = "description_eval"

PROMPT = """\
You are a YouTube SEO expert evaluating a Shorts video description.

Score 0–10 based on:
- Keyword coverage (does it include relevant dog-facts keywords?)
- CTA presence (does it ask viewers to follow/subscribe?)
- Length (50–300 chars is ideal for Shorts)
- Hashtag quality (≥5 relevant hashtags?)

Description:
{description}

Respond ONLY with valid JSON, no markdown:
{{"score": <float 0-10>, "reasoning": "<one sentence>"}}"""


def description_eval(description: str) -> EvalResult:
    """Score the video description for SEO quality. Threshold: 7/10."""
    client = Anthropic()
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": PROMPT.format(description=description)}],
    )
    score, reasoning = _parse_llm_score(msg.content[0].text, EVAL_NAME)
    return EvalResult(eval_name=EVAL_NAME, score=score, threshold=THRESHOLD, reasoning=reasoning)
```

- [ ] **Step 8: Implement placeholder evals**

Create `harness/evals/thumbnail_eval.py`:

```python
from harness.evals.base import EvalResult

EVAL_NAME = "thumbnail_eval"


def thumbnail_eval(variants: list) -> EvalResult:
    """Placeholder — thumbnail generation is Session 3. Always passes."""
    return EvalResult(
        eval_name=EVAL_NAME,
        score=8.0,
        threshold=7.0,
        reasoning="Placeholder: thumbnail eval not yet implemented",
    )
```

Create `harness/evals/channel_eval.py`:

```python
from harness.evals.base import EvalResult

EVAL_NAME = "channel_eval"


def channel_eval(current_kpis: dict, prior_kpis: dict) -> EvalResult:
    """Placeholder — analytics tracking is Session 3. Always passes."""
    return EvalResult(
        eval_name=EVAL_NAME,
        score=8.0,
        threshold=7.0,
        reasoning="Placeholder: channel eval not yet implemented",
    )
```

- [ ] **Step 9: Run LLM eval tests (mocked)**

```bash
python -m pytest harness/tests/test_evals.py -v -k "not audio and not video"
```

Expected: all LLM eval tests PASS (all mocked — no real API calls)

- [ ] **Step 10: Commit**

```bash
git add harness/evals/
git commit -m "feat: eval base + LLM judge evals (hook, script, title, description) + placeholders"
```

---

## Task 3: Deterministic Evals (Audio + Video)

**Files:**
- Create: `harness/evals/audio_eval.py`
- Create: `harness/evals/video_eval.py`
- Modify: `harness/tests/test_evals.py` (append audio/video tests)

- [ ] **Step 1: Append audio + video tests to test_evals.py**

Append to `harness/tests/test_evals.py`:

```python
# ── audio_eval ────────────────────────────────────────────────────────────────

from harness.evals.audio_eval import audio_eval
from harness.evals.video_eval import video_eval


def test_audio_eval_passes_valid_mp3(tmp_path):
    """Create a fake mp3 that ffprobe would accept — we mock ffprobe."""
    audio_file = tmp_path / "voiceover.mp3"
    audio_file.write_bytes(b"\x00" * 1000)

    with patch("harness.evals.audio_eval.subprocess.run") as mock_run:
        # Mock ffprobe duration response
        mock_run.return_value = MagicMock(returncode=0, stdout="45.3\n", stderr="")
        result = audio_eval(audio_file)
    assert result.passed is True
    assert result.score == 10.0


def test_audio_eval_fails_too_short(tmp_path):
    audio_file = tmp_path / "voiceover.mp3"
    audio_file.write_bytes(b"\x00" * 100)

    with patch("harness.evals.audio_eval.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="5.0\n", stderr="")
        result = audio_eval(audio_file)
    assert result.passed is False


def test_audio_eval_fails_too_long(tmp_path):
    audio_file = tmp_path / "voiceover.mp3"
    audio_file.write_bytes(b"\x00" * 100)

    with patch("harness.evals.audio_eval.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="95.0\n", stderr="")
        result = audio_eval(audio_file)
    assert result.passed is False


def test_audio_eval_fails_missing_file(tmp_path):
    result = audio_eval(tmp_path / "nonexistent.mp3")
    assert result.passed is False


# ── video_eval ────────────────────────────────────────────────────────────────

def test_video_eval_passes_valid_1080x1920(tmp_path):
    video_file = tmp_path / "final_video.mp4"
    video_file.write_bytes(b"\x00" * 1000)

    with patch("harness.evals.video_eval.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"streams": [{"width": 1080, "height": 1920}]}\n',
            stderr=""
        )
        result = video_eval(video_file)
    assert result.passed is True
    assert result.score == 10.0


def test_video_eval_fails_wrong_resolution(tmp_path):
    video_file = tmp_path / "final_video.mp4"
    video_file.write_bytes(b"\x00" * 1000)

    with patch("harness.evals.video_eval.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"streams": [{"width": 1920, "height": 1080}]}\n',
            stderr=""
        )
        result = video_eval(video_file)
    assert result.passed is False


def test_video_eval_fails_missing_file(tmp_path):
    result = video_eval(tmp_path / "nonexistent.mp4")
    assert result.passed is False


def test_video_eval_fails_zero_size_file(tmp_path):
    video_file = tmp_path / "final_video.mp4"
    video_file.write_bytes(b"")
    result = video_eval(video_file)
    assert result.passed is False
```

- [ ] **Step 2: Run to verify new tests fail**

```bash
python -m pytest harness/tests/test_evals.py::test_audio_eval_passes_valid_mp3 -v
```

Expected: `ModuleNotFoundError: No module named 'harness.evals.audio_eval'`

- [ ] **Step 3: Implement audio_eval.py**

Create `harness/evals/audio_eval.py`:

```python
import subprocess
from pathlib import Path

from harness.evals.base import EvalResult

EVAL_NAME = "audio_eval"
MIN_DURATION = 10.0   # seconds
MAX_DURATION = 90.0   # seconds — Shorts limit is 60s, give headroom


def audio_eval(audio_path: Path) -> EvalResult:
    """
    Deterministic check: file exists, duration 10–90s.
    Uses ffprobe to read actual duration.
    """
    audio_path = Path(audio_path)

    if not audio_path.exists():
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning=f"Audio file not found: {audio_path}"
        )

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(audio_path)],
            capture_output=True, text=True, timeout=15
        )
        duration = float(result.stdout.strip())
    except Exception as e:
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning=f"ffprobe failed: {e}"
        )

    if duration < MIN_DURATION:
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning=f"Audio too short: {duration:.1f}s (min {MIN_DURATION}s)"
        )

    if duration > MAX_DURATION:
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning=f"Audio too long: {duration:.1f}s (max {MAX_DURATION}s)"
        )

    return EvalResult(
        eval_name=EVAL_NAME, score=10.0, threshold=1.0,
        reasoning=f"Audio OK: {duration:.1f}s"
    )
```

- [ ] **Step 4: Implement video_eval.py**

Create `harness/evals/video_eval.py`:

```python
import json
import subprocess
from pathlib import Path

from harness.evals.base import EvalResult

EVAL_NAME = "video_eval"
EXPECTED_WIDTH = 1080
EXPECTED_HEIGHT = 1920


def video_eval(video_path: Path) -> EvalResult:
    """
    Deterministic check: file exists, non-zero size, resolution 1080x1920.
    Uses ffprobe to read stream metadata.
    """
    video_path = Path(video_path)

    if not video_path.exists():
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning=f"Video file not found: {video_path}"
        )

    if video_path.stat().st_size == 0:
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning="Video file is empty (0 bytes)"
        )

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "json", str(video_path)],
            capture_output=True, text=True, timeout=15
        )
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
    except Exception as e:
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning=f"ffprobe failed: {e}"
        )

    if width != EXPECTED_WIDTH or height != EXPECTED_HEIGHT:
        return EvalResult(
            eval_name=EVAL_NAME, score=0.0, threshold=1.0,
            reasoning=f"Wrong resolution: {width}x{height} (expected {EXPECTED_WIDTH}x{EXPECTED_HEIGHT})"
        )

    return EvalResult(
        eval_name=EVAL_NAME, score=10.0, threshold=1.0,
        reasoning=f"Video OK: {width}x{height}"
    )
```

- [ ] **Step 5: Run all eval tests**

```bash
python -m pytest harness/tests/test_evals.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add harness/evals/audio_eval.py harness/evals/video_eval.py harness/tests/test_evals.py
git commit -m "feat: deterministic audio + video evals"
```

---

## Task 4: Orchestrator

**Files:**
- Create: `harness/orchestrator.py`
- Create: `harness/tests/test_orchestrator.py`

The orchestrator wraps the existing pipeline. It calls the existing functions, runs evals after each artifact, retries LLM evals up to 3× (regenerating the artifact each time), and writes an incident JSON + halts on hard failures (audio/video evals).

- [ ] **Step 1: Write failing orchestrator tests**

Create `harness/tests/test_orchestrator.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from harness.orchestrator import run_pipeline, _write_incident


# ── _write_incident ───────────────────────────────────────────────────────────

def test_write_incident_creates_json_file(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.orchestrator.DATA_DIR", tmp_path)
    (tmp_path / "incidents").mkdir()
    incident_id = _write_incident(
        trigger="hook_eval",
        what_failed="Score 4.0 < threshold 7.0",
        hypothesis="Hook is too generic",
        code_path="generate_script.py:prompt",
    )
    incident_files = list((tmp_path / "incidents").glob("*.json"))
    assert len(incident_files) == 1
    data = json.loads(incident_files[0].read_text())
    assert data["trigger"] == "hook_eval"
    assert data["what_failed"] == "Score 4.0 < threshold 7.0"
    assert "id" in data
    assert "timestamp" in data


def test_write_incident_creates_md_file(tmp_path, monkeypatch):
    monkeypatch.setattr("harness.orchestrator.DATA_DIR", tmp_path)
    (tmp_path / "incidents").mkdir()
    _write_incident(
        trigger="audio_eval",
        what_failed="Audio too short: 5s",
        hypothesis="ElevenLabs returned clipped audio",
        code_path="generate_audio.py",
    )
    md_files = list((tmp_path / "incidents").glob("*.md"))
    assert len(md_files) == 1
    content = md_files[0].read_text()
    assert "audio_eval" in content
    assert "Audio too short" in content


# ── run_pipeline ──────────────────────────────────────────────────────────────

def _make_eval_result(passed: bool, score: float = 8.0, name: str = "hook_eval"):
    from harness.evals.base import EvalResult
    r = EvalResult.__new__(EvalResult)
    r.eval_name = name
    r.score = score
    r.threshold = 7.0
    r.reasoning = "mocked"
    r.passed = passed
    return r


@patch("harness.orchestrator.video_eval")
@patch("harness.orchestrator.audio_eval")
@patch("harness.orchestrator.description_eval")
@patch("harness.orchestrator.thumbnail_eval")
@patch("harness.orchestrator.title_eval")
@patch("harness.orchestrator.script_eval")
@patch("harness.orchestrator.hook_eval")
@patch("harness.orchestrator.build_video", return_value="outputs/final_video.mp4")
@patch("harness.orchestrator.generate_audio", return_value=45.0)
@patch("harness.orchestrator.generate_script", return_value={"script": "Dogs rule.", "title": "Dog Facts", "hashtags": ["dogs"]})
@patch("harness.orchestrator.upload_youtube", return_value="https://youtube.com/shorts/abc123")
def test_run_pipeline_succeeds_when_all_evals_pass(
    mock_upload, mock_script, mock_audio, mock_video_build,
    mock_hook, mock_script_eval, mock_title, mock_thumb, mock_desc, mock_audio_eval, mock_video_eval,
    tmp_path, monkeypatch
):
    monkeypatch.setattr("harness.orchestrator.DATA_DIR", tmp_path)
    (tmp_path / "incidents").mkdir()
    (tmp_path / "eval_runs").mkdir()

    for mock in [mock_hook, mock_script_eval, mock_title, mock_thumb, mock_desc]:
        mock.return_value = _make_eval_result(passed=True)
    mock_audio_eval.return_value = _make_eval_result(passed=True, name="audio_eval")
    mock_video_eval.return_value = _make_eval_result(passed=True, name="video_eval")

    result = run_pipeline()
    assert result["success"] is True
    assert result["video_url"] == "https://youtube.com/shorts/abc123"


@patch("harness.orchestrator.video_eval")
@patch("harness.orchestrator.audio_eval")
@patch("harness.orchestrator.description_eval")
@patch("harness.orchestrator.thumbnail_eval")
@patch("harness.orchestrator.title_eval")
@patch("harness.orchestrator.script_eval")
@patch("harness.orchestrator.hook_eval")
@patch("harness.orchestrator.build_video", return_value="outputs/final_video.mp4")
@patch("harness.orchestrator.generate_audio", return_value=45.0)
@patch("harness.orchestrator.generate_script", return_value={"script": "Dogs rule.", "title": "Dog Facts", "hashtags": ["dogs"]})
@patch("harness.orchestrator.upload_youtube", return_value="https://youtube.com/shorts/abc123")
def test_run_pipeline_retries_script_on_hook_fail(
    mock_upload, mock_script, mock_audio, mock_video_build,
    mock_hook, mock_script_eval, mock_title, mock_thumb, mock_desc, mock_audio_eval, mock_video_eval,
    tmp_path, monkeypatch
):
    monkeypatch.setattr("harness.orchestrator.DATA_DIR", tmp_path)
    (tmp_path / "incidents").mkdir()

    # hook fails twice, passes third time
    mock_hook.side_effect = [
        _make_eval_result(passed=False, score=4.0),
        _make_eval_result(passed=False, score=5.0),
        _make_eval_result(passed=True, score=8.0),
    ]
    for mock in [mock_script_eval, mock_title, mock_thumb, mock_desc]:
        mock.return_value = _make_eval_result(passed=True)
    mock_audio_eval.return_value = _make_eval_result(passed=True, name="audio_eval")
    mock_video_eval.return_value = _make_eval_result(passed=True, name="video_eval")

    result = run_pipeline()
    assert result["success"] is True
    assert mock_script.call_count == 3  # regenerated twice


@patch("harness.orchestrator.video_eval")
@patch("harness.orchestrator.audio_eval")
@patch("harness.orchestrator.description_eval")
@patch("harness.orchestrator.thumbnail_eval")
@patch("harness.orchestrator.title_eval")
@patch("harness.orchestrator.script_eval")
@patch("harness.orchestrator.hook_eval")
@patch("harness.orchestrator.build_video", return_value="outputs/final_video.mp4")
@patch("harness.orchestrator.generate_audio", return_value=45.0)
@patch("harness.orchestrator.generate_script", return_value={"script": "Dogs rule.", "title": "Dog Facts", "hashtags": ["dogs"]})
@patch("harness.orchestrator.upload_youtube", return_value="https://youtube.com/shorts/abc123")
def test_run_pipeline_writes_incident_and_fails_after_3_hook_failures(
    mock_upload, mock_script, mock_audio, mock_video_build,
    mock_hook, mock_script_eval, mock_title, mock_thumb, mock_desc, mock_audio_eval, mock_video_eval,
    tmp_path, monkeypatch
):
    monkeypatch.setattr("harness.orchestrator.DATA_DIR", tmp_path)
    (tmp_path / "incidents").mkdir()

    mock_hook.return_value = _make_eval_result(passed=False, score=3.0)
    for mock in [mock_script_eval, mock_title, mock_thumb, mock_desc]:
        mock.return_value = _make_eval_result(passed=True)
    mock_audio_eval.return_value = _make_eval_result(passed=True, name="audio_eval")
    mock_video_eval.return_value = _make_eval_result(passed=True, name="video_eval")

    result = run_pipeline()
    assert result["success"] is False
    assert "hook_eval" in result["reason"]
    incident_files = list((tmp_path / "incidents").glob("*.json"))
    assert len(incident_files) == 1


@patch("harness.orchestrator.video_eval")
@patch("harness.orchestrator.audio_eval")
@patch("harness.orchestrator.description_eval")
@patch("harness.orchestrator.thumbnail_eval")
@patch("harness.orchestrator.title_eval")
@patch("harness.orchestrator.script_eval")
@patch("harness.orchestrator.hook_eval")
@patch("harness.orchestrator.build_video", return_value="outputs/final_video.mp4")
@patch("harness.orchestrator.generate_audio", return_value=45.0)
@patch("harness.orchestrator.generate_script", return_value={"script": "Dogs rule.", "title": "Dog Facts", "hashtags": ["dogs"]})
@patch("harness.orchestrator.upload_youtube", return_value="https://youtube.com/shorts/abc123")
def test_run_pipeline_halts_on_hard_audio_fail(
    mock_upload, mock_script, mock_audio, mock_video_build,
    mock_hook, mock_script_eval, mock_title, mock_thumb, mock_desc, mock_audio_eval, mock_video_eval,
    tmp_path, monkeypatch
):
    monkeypatch.setattr("harness.orchestrator.DATA_DIR", tmp_path)
    (tmp_path / "incidents").mkdir()

    for mock in [mock_hook, mock_script_eval, mock_title, mock_thumb, mock_desc]:
        mock.return_value = _make_eval_result(passed=True)
    mock_audio_eval.return_value = _make_eval_result(passed=False, score=0.0, name="audio_eval")
    mock_video_eval.return_value = _make_eval_result(passed=True, name="video_eval")

    result = run_pipeline()
    assert result["success"] is False
    assert "audio_eval" in result["reason"]
    mock_upload.assert_not_called()
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python -m pytest harness/tests/test_orchestrator.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'harness.orchestrator'`

- [ ] **Step 3: Implement orchestrator.py**

Create `harness/orchestrator.py`:

```python
"""
Canine Wisdom Harness — Daily Orchestrator
Replaces main.py as the entry point. Wraps existing pipeline with eval gating.
"""
import sys
import uuid
from datetime import datetime
from pathlib import Path

from generate_audio import generate_audio
from generate_script import generate_script
from build_video import build_video
from upload_youtube import upload_youtube
from utils import init_logger, log, clear_outputs_dir, move_outputs_to_archive

from harness.evals.audio_eval import audio_eval
from harness.evals.channel_eval import channel_eval
from harness.evals.description_eval import description_eval
from harness.evals.hook_eval import hook_eval
from harness.evals.script_eval import script_eval
from harness.evals.thumbnail_eval import thumbnail_eval
from harness.evals.title_eval import title_eval
from harness.evals.video_eval import video_eval
from harness.evals.base import save_eval_result
from harness.storage import atomic_write, DATA_DIR

MAX_LLM_RETRIES = 3


def _write_incident(trigger: str, what_failed: str, hypothesis: str, code_path: str) -> str:
    """Write incident report (JSON + MD) to data/incidents/. Returns incident ID."""
    incident_id = f"inc-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    timestamp = datetime.now().isoformat()

    record = {
        "id": incident_id,
        "timestamp": timestamp,
        "trigger": trigger,
        "what_failed": what_failed,
        "hypothesis": hypothesis,
        "code_path": code_path,
        "fix_branch": f"harness-auto-fix/{incident_id}",
        "fix_status": "open",
        "attempts": 0,
        "resolved_at": None,
    }

    incidents_dir = DATA_DIR / "incidents"
    incidents_dir.mkdir(parents=True, exist_ok=True)

    atomic_write(incidents_dir / f"{incident_id}.json", record)

    md_path = incidents_dir / f"{incident_id}.md"
    md_path.write_text(
        f"# Incident: {incident_id}\n\n"
        f"**Timestamp:** {timestamp}\n"
        f"**Trigger:** {trigger}\n"
        f"**What failed:** {what_failed}\n"
        f"**Hypothesis:** {hypothesis}\n"
        f"**Code path:** `{code_path}`\n"
        f"**Status:** open\n",
        encoding="utf-8",
    )

    log(f"📋 Incident written: {incident_id}")
    return incident_id


def _run_llm_eval_with_retry(eval_fn, eval_name: str, code_path: str, *args, **kwargs):
    """
    Run an LLM eval up to MAX_LLM_RETRIES times.
    Returns (passed: bool, result: EvalResult).
    Writes an incident and returns (False, last_result) if all attempts fail.
    """
    last_result = None
    for attempt in range(MAX_LLM_RETRIES):
        result = eval_fn(*args, **kwargs)
        last_result = result
        if result.passed:
            return True, result
        log(f"⚠️  {eval_name} failed (attempt {attempt + 1}/{MAX_LLM_RETRIES}): score={result.score:.1f} — {result.reasoning}")
        if attempt < MAX_LLM_RETRIES - 1:
            log(f"🔄 Regenerating and retrying {eval_name}...")

    _write_incident(
        trigger=eval_name,
        what_failed=f"Score {last_result.score:.1f} < threshold {last_result.threshold:.1f} after {MAX_LLM_RETRIES} attempts",
        hypothesis=last_result.reasoning,
        code_path=code_path,
    )
    return False, last_result


def run_pipeline() -> dict:
    """
    Run the full harness pipeline with eval gating.

    Returns:
        dict with keys: success (bool), video_url (str|None), reason (str|None)
    """
    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    init_logger(run_id)
    log("🚀 Canine Wisdom Harness — starting pipeline")

    clear_outputs_dir()
    metadata = None
    audio_duration = None

    # ── Script generation + LLM evals ────────────────────────────────────────
    for attempt in range(MAX_LLM_RETRIES):
        metadata = generate_script()
        script_text = metadata["script"]
        title = metadata["title"]

        # Hook eval
        hook_sentence = script_text.split(".")[0] + "."
        hook_result = hook_eval(hook_sentence)
        save_eval_result(hook_result, run_id)
        if not hook_result.passed:
            log(f"⚠️  hook_eval failed (attempt {attempt + 1}): {hook_result.reasoning}")
            if attempt == MAX_LLM_RETRIES - 1:
                _write_incident("hook_eval", f"Score {hook_result.score:.1f} after {MAX_LLM_RETRIES} attempts",
                                hook_result.reasoning, "generate_script.py:prompt")
                move_outputs_to_archive(run_id)
                return {"success": False, "video_url": None, "reason": "hook_eval failed after max retries"}
            continue

        # Script eval
        script_result = script_eval(script_text, recent_topics=[])
        save_eval_result(script_result, run_id)
        if not script_result.passed:
            log(f"⚠️  script_eval failed (attempt {attempt + 1}): {script_result.reasoning}")
            if attempt == MAX_LLM_RETRIES - 1:
                _write_incident("script_eval", f"Score {script_result.score:.1f} after {MAX_LLM_RETRIES} attempts",
                                script_result.reasoning, "generate_script.py:prompt")
                move_outputs_to_archive(run_id)
                return {"success": False, "video_url": None, "reason": "script_eval failed after max retries"}
            continue

        # Title eval
        title_result = title_eval(title)
        save_eval_result(title_result, run_id)
        if not title_result.passed:
            log(f"⚠️  title_eval failed (attempt {attempt + 1}): {title_result.reasoning}")
            if attempt == MAX_LLM_RETRIES - 1:
                _write_incident("title_eval", f"Score {title_result.score:.1f} after {MAX_LLM_RETRIES} attempts",
                                title_result.reasoning, "generate_script.py:prompt")
                move_outputs_to_archive(run_id)
                return {"success": False, "video_url": None, "reason": "title_eval failed after max retries"}
            continue

        break  # all LLM evals passed

    # ── Description eval ──────────────────────────────────────────────────────
    description = metadata.get("description", " ".join(f"#{t}" for t in metadata.get("hashtags", [])))
    desc_result = description_eval(description)
    save_eval_result(desc_result, run_id)
    if not desc_result.passed:
        _write_incident("description_eval", f"Score {desc_result.score:.1f}",
                        desc_result.reasoning, "upload_youtube.py:description")
        log(f"⚠️  description_eval failed — continuing (non-blocking for now)")

    # ── Thumbnail eval (placeholder) ──────────────────────────────────────────
    thumb_result = thumbnail_eval(variants=[])
    save_eval_result(thumb_result, run_id)

    # ── Audio generation + hard eval ─────────────────────────────────────────
    audio_duration = generate_audio()
    audio_path = Path("outputs/voiceover.mp3")
    audio_result = audio_eval(audio_path)
    save_eval_result(audio_result, run_id)
    if not audio_result.passed:
        _write_incident("audio_eval", audio_result.reasoning, "Check ElevenLabs response",
                        "generate_audio.py")
        move_outputs_to_archive(run_id)
        return {"success": False, "video_url": None, "reason": f"audio_eval failed: {audio_result.reasoning}"}

    # ── Video build + hard eval ───────────────────────────────────────────────
    video_path = build_video(audio_duration)
    video_result = video_eval(Path(video_path))
    save_eval_result(video_result, run_id)
    if not video_result.passed:
        _write_incident("video_eval", video_result.reasoning, "Check ffmpeg filter chain",
                        "build_video.py")
        move_outputs_to_archive(run_id)
        return {"success": False, "video_url": None, "reason": f"video_eval failed: {video_result.reasoning}"}

    # ── Upload ────────────────────────────────────────────────────────────────
    video_url = upload_youtube()
    log(f"🎉 Short is LIVE: {video_url}")

    move_outputs_to_archive(run_id)
    return {"success": True, "video_url": video_url, "reason": None}


if __name__ == "__main__":
    result = run_pipeline()
    if not result["success"]:
        log(f"❌ Pipeline failed: {result['reason']}", level="error")
        sys.exit(1)
    sys.exit(0)
```

- [ ] **Step 4: Run orchestrator tests**

```bash
python -m pytest harness/tests/test_orchestrator.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest harness/tests/ -v
```

Expected: all tests PASS (storage + evals + orchestrator)

- [ ] **Step 6: Commit**

```bash
git add harness/orchestrator.py harness/tests/test_orchestrator.py
git commit -m "feat: harness orchestrator with eval gating + incident writing"
```

---

## Task 5: Docs + Cron Entry Point

**Files:**
- Create: `harness/CHANGELOG.md`
- Create: `harness/README.md`
- Modify: `README.md` (root)

- [ ] **Step 1: Create CHANGELOG.md**

Create `harness/CHANGELOG.md`:

```markdown
# Harness CHANGELOG

Auto-updated by `harness/agents/healer.py` when self-healing changes are applied.

---

## [Session 1] 2026-05-17

### Added
- `harness/storage.py` — atomic JSON read/write with file locking
- `harness/evals/` — 8 eval modules (hook, script, title, description, thumbnail, audio, video, channel)
- `harness/orchestrator.py` — eval-gated pipeline replacing main.py
- `harness/data/` — JSON state storage structure
```

- [ ] **Step 2: Create harness/README.md**

Create `harness/README.md`:

```markdown
# Canine Wisdom Harness

Autonomous layer around the existing YouTube Shorts pipeline. Adds eval gating,
competitor intelligence, trend research, comment replies, and self-healing.

## Running

**Daily run (replaces main.py):**
```bash
python -m harness.orchestrator
```

**Cron (9am daily):**
```
0 9 * * * cd /path/to/canine-wisdom-automation && python -m harness.orchestrator >> run_logs/cron.log 2>&1
```

## How evals work

Every artifact is scored before upload:

| Eval | Type | Threshold | On fail |
|------|------|-----------|---------|
| hook_eval | LLM judge | ≥7/10 | Regenerate (3× max) |
| script_eval | LLM judge | ≥7/10 | Regenerate (3× max) |
| title_eval | LLM judge | ≥7/10 | Regenerate (3× max) |
| thumbnail_eval | LLM judge | best of N | Pick best (Session 3) |
| description_eval | LLM judge | ≥7/10 | Log + continue |
| audio_eval | Deterministic | pass/fail | Halt pipeline |
| video_eval | Deterministic | pass/fail | Halt pipeline |
| channel_eval | Weekly | trending up | Trigger healer |

## Incident reports

Written to `harness/data/incidents/{timestamp}-{id}.json` and `.md` when evals fail.
The self-healing agent (Session 4) reads these and proposes code patches.

## Self-healing bounds

The healer is allowed to:
- Install pip packages and update `requirements.txt`
- Add new files and edit existing ones
- Create git branches and commit

The healer is NOT allowed to:
- Rotate or expose API keys
- Delete `archive/` or `run_logs/`
- Push to remote without user approval
- Spend money on paid APIs without surfacing a cost estimate first

## Data directory

```
harness/data/
├── performance/     {video_id}.json + index.json
├── competitors/     {channel_id}.json
├── topics/          {YYYY-MM-DD}.json
├── eval_runs/       {date}/{video_id}/{eval_name}.json
├── incidents/       {timestamp}-{id}.json + .md
├── comments/        {video_id}.json
├── thumbnails/      {video_id}.json
└── state.json       global state (KPIs, config, last run)
```

## Extending

Add a new eval: create `harness/evals/my_eval.py` returning `EvalResult`, import it in
`orchestrator.py`, call `save_eval_result()` after running it.

Add a new agent: create `harness/agents/my_agent.py`, call it from the orchestrator
at the appropriate step.
```

- [ ] **Step 3: Update root README.md**

Open `README.md` (root) and prepend this block at the top:

```markdown
> **New entry point:** The harness orchestrator replaces `main.py`. Run with:
> ```bash
> python -m harness.orchestrator
> ```
> See [`harness/README.md`](harness/README.md) for full documentation.

---
```

- [ ] **Step 4: Final test run**

```bash
python -m pytest harness/tests/ -v --tb=short
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add harness/CHANGELOG.md harness/README.md README.md
git commit -m "docs: harness README, CHANGELOG, root entry point note"
```

---

## Self-Review

**Spec coverage check:**
- ✅ `storage.py` — atomic writes, file lock, pretty-print JSON
- ✅ All 8 evals — hook, script, title, thumbnail (placeholder), description, audio, video, channel (placeholder)
- ✅ `orchestrator.py` — wraps existing pipeline, runs evals, retries LLM evals 3×, writes incident on failure, halts on hard failures
- ✅ `harness/data/` structure — all subdirs created
- ✅ `state.json` — initial state written
- ✅ Tests for storage, all evals, orchestrator
- ✅ `CHANGELOG.md` initialized
- ✅ `README.md` with bounds, data schema, cron example
- ⏭️ Competitor agent — Session 2
- ⏭️ Trend agent — Session 2
- ⏭️ Thumbnail generation — Session 3
- ⏭️ Analytics — Session 3
- ⏭️ Comment agent — Session 4
- ⏭️ Self-healing agent — Session 4

**Type consistency:**
- `EvalResult` dataclass used consistently across all evals and orchestrator
- `save_eval_result(result, video_id)` — `video_id` is `run_id` string in orchestrator (acceptable: no real video ID until after upload; will be refactored in Session 3 when analytics tracking is added)
- `atomic_write(path, data)` / `atomic_read(path)` — consistent signatures throughout
- `DATA_DIR` imported from `harness.storage` in both `orchestrator.py` and `evals/base.py`

**No placeholders:** All code is complete. Thumbnail and channel evals are marked as placeholders by design (Session 3/4 work) and tests assert their placeholder behavior.
