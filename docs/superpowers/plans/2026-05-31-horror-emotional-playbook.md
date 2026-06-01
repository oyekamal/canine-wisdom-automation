# Horror Emotional Content Playbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Embed the Emotional Content Playbook's principles (arousal-over-valence, 4-beat structure, hook engineering, high-energy endings) into the horror channel's Claude prompt, story scorer, and story rewriter — so every generated horror video is structurally built for maximum sharing and emotional impact.

**Architecture:** Three touch-points are changed: (1) `prompt.txt` gets a new EMOTIONAL ARCHITECTURE section that enforces 4-beat structure and arousal-not-valence endings; (2) `story_scorer.py` gains an arousal-signal bonus that up-ranks stories with high-energy hooks; (3) `story_rewriter.py` gains a `_build_emotional_prompt` helper that injects per-story emotional context. No new files needed — all changes are in-place.

**Tech Stack:** Python 3, Claude `claude-sonnet-4-6`, existing horror harness at `channels/horror-narration/harness/`.

---

## Task 1: Upgrade `prompt.txt` — inject 4-beat structure + arousal rules

**Files:**
- Modify: `channels/horror-narration/prompt.txt`

This is a pure content edit — no code. We're adding an EMOTIONAL ARCHITECTURE section that teaches Claude the 4-beat structure (Hook → Build → Payoff → Ending/Loop) and the arousal rule (never end on sadness/contentment; always resolve upward into awe or dread-with-energy).

- [ ] **Step 1: Read the current prompt**

```bash
cat channels/horror-narration/prompt.txt
```

Expected: The system prompt you already know. Confirm the final line is the OUTPUT FORMAT block.

- [ ] **Step 2: Add the EMOTIONAL ARCHITECTURE section**

Insert the following block immediately before the line `OUTPUT FORMAT — respond with JSON only, no markdown:` in `channels/horror-narration/prompt.txt`:

```
EMOTIONAL ARCHITECTURE (4-BEAT STRUCTURE):
Every script must follow this shape regardless of length:

BEAT 1 — HOOK (first 1-3 sentences): The most wrong, specific, striking moment. Drop the reader INTO the wrongness. Use the delayed-answer technique: name a detail without naming the full situation. "Something was already on the other side of the door" not "I found something scary." Hook must work as a standalone sentence with all sound off.

BEAT 2 — BUILD (middle section): Hold the tension open. Establish the task or goal the narrator is trying to complete. Name an obstacle. Do NOT resolve the mystery yet. The reader's brain must still have an open loop.

BEAT 3 — PAYOFF: Deliver the feeling that was promised in Beat 1. Close the loop — but only partially. The horror is confirmed but never fully explained. Specific sensory detail carries this beat: a sound, a smell, a physical sensation.

BEAT 4 — ENDING (final 2-3 sentences): NEVER end on pure sadness or low-energy dread alone. Always resolve to a HIGH-AROUSAL emotional state: active dread ("it's still happening"), chilling awe ("I know what it is now and I can't unknow it"), or forward-moving wrongness ("I checked this morning — it was still there"). The ending must make the reader want to send the video to someone, not sit quietly in sadness. Loop back to the opening image when possible.

AROUSAL RULE: The difference between a video that gets shared and one that gets watched once is activation energy. Sadness and contentment are low-arousal — they relax people. Dread and awe are high-arousal — they energize people to act (share, comment, follow). Every beat should push the emotional state UP the energy axis, not down. A sad revelation must be followed by an active, unresolved threat. A quiet ending is only acceptable if it contains a deeply unsettling wrongness that the reader needs to show someone else.

```

- [ ] **Step 3: Verify the edit looks correct**

```bash
grep -n "EMOTIONAL ARCHITECTURE" channels/horror-narration/prompt.txt
grep -n "AROUSAL RULE" channels/horror-narration/prompt.txt
grep -n "OUTPUT FORMAT" channels/horror-narration/prompt.txt
```

Expected output: EMOTIONAL ARCHITECTURE and AROUSAL RULE appear BEFORE OUTPUT FORMAT.

- [ ] **Step 4: Commit**

```bash
git add channels/horror-narration/prompt.txt
git commit -m "feat(horror): add 4-beat emotional architecture + arousal rules to prompt"
```

---

## Task 2: Upgrade `story_scorer.py` — add arousal-signal scoring

**Files:**
- Modify: `channels/horror-narration/harness/story_scorer.py`
- Test: `channels/horror-narration/tests/test_story_scorer.py`

The current scorer rewards length fit, hook words, and upvotes. We add a 4th signal: **arousal potential** — stories with titles that contain high-activation-language words (action verbs, immediate physical threat, sensory triggers) score higher because they are more likely to produce shareable, high-arousal content.

- [ ] **Step 1: Write the failing test first**

Create/open `channels/horror-narration/tests/test_story_scorer.py` and add:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[4]))
sys.path.insert(0, str(Path(__file__).parents[1]))

from harness.story_scorer import score_story, _arousal_score


def _story(title, score=500, word_count=80):
    return {"id": "x1", "title": title, "score": score, "word_count": word_count}


def test_arousal_score_high_for_action_titles():
    """Titles with immediate threat/action words should score > 0.5"""
    s = _story("I followed the sound and found it still breathing")
    assert _arousal_score(s["title"]) > 0.5


def test_arousal_score_low_for_passive_titles():
    """Titles with passive, atmospheric language should score < 0.3"""
    s = _story("The old house had a strange feeling")
    assert _arousal_score(s["title"]) < 0.3


def test_arousal_contributes_to_total_score():
    """A high-arousal story should outscore an otherwise identical low-arousal story"""
    high = _story("I ran but it was already inside", score=500, word_count=80)
    low  = _story("The atmosphere seemed unsettling", score=500, word_count=80)
    assert score_story(high, "short", set()) > score_story(low, "short", set())


def test_used_id_still_zero():
    """Used stories score 0 regardless of arousal"""
    s = _story("I ran but it was already inside")
    assert score_story(s, "short", {"x1"}) == 0.0
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
python -m pytest channels/horror-narration/tests/test_story_scorer.py -v 2>&1 | head -30
```

Expected: ERRORS or ImportError on `_arousal_score` — the function doesn't exist yet.

- [ ] **Step 3: Add `_arousal_score` and wire it into `score_story`**

In `channels/horror-narration/harness/story_scorer.py`, add the AROUSAL_WORDS set and `_arousal_score` function, then update `score_story` to use it (reduce HOOK_WORDS weight from 4 to 3, add arousal at weight 2 — total stays ~10):

```python
SHORT_WORD_RANGE = (40, 120)
LONG_WORD_RANGE  = (600, 1800)

HOOK_WORDS = {
    "what", "why", "who", "how", "found", "heard", "saw", "inside",
    "behind", "under", "never", "disappeared", "wrong", "dark", "alone",
    "door", "basement", "woods", "road", "night", "watching", "missing",
    "followed", "stalked", "crawled", "screamed", "dead", "monster",
    "creature", "shadow", "whispered", "blood", "escaped", "trapped",
}

# High-arousal words: immediate action, physical sensation, urgency
AROUSAL_WORDS = {
    "ran", "running", "chased", "grabbed", "dragged", "pulled", "pushed",
    "broke", "shattered", "crashed", "slammed", "hit", "cut", "bleeding",
    "breathing", "screaming", "clawing", "crawling", "moving", "staring",
    "opened", "inside", "already", "still", "again", "following", "watching",
    "woke", "woken", "left", "gone", "taken", "escaped", "trapped", "locked",
}


def _length_score(word_count: int, target: str) -> float:
    lo, hi = SHORT_WORD_RANGE if target == "short" else LONG_WORD_RANGE
    if lo <= word_count <= hi:
        return 1.0
    dist = min(abs(word_count - lo), abs(word_count - hi))
    return max(0.0, 1.0 - dist / max(lo, 1))


def _hook_score(title: str) -> float:
    words = set(title.lower().split())
    return min(1.0, len(words & HOOK_WORDS) / 2)


def _arousal_score(title: str) -> float:
    """Score 0-1: how many high-activation words appear in the title."""
    words = set(title.lower().split())
    return min(1.0, len(words & AROUSAL_WORDS) / 2)


def _upvote_score(score: int) -> float:
    return min(1.0, math.log1p(score) / math.log1p(5000))


def score_story(story: dict, target: str, used_ids: set) -> float:
    if story["id"] in used_ids:
        return 0.0
    return round(
        _length_score(story["word_count"], target) * 3 +
        _hook_score(story["title"]) * 3 +
        _arousal_score(story["title"]) * 2 +
        _upvote_score(story["score"]) * 2,
        2
    )


def pick_best_story(stories: list, target: str, used_ids: set) -> dict | None:
    scored = sorted(
        ((score_story(s, target, used_ids), s) for s in stories),
        key=lambda x: x[0], reverse=True
    )
    if not scored or scored[0][0] == 0:
        return None
    return scored[0][1]
```

Note: `import math` is already at the top of the original file.

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
python -m pytest channels/horror-narration/tests/test_story_scorer.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add channels/horror-narration/harness/story_scorer.py channels/horror-narration/tests/test_story_scorer.py
git commit -m "feat(horror): add arousal-signal scoring to story_scorer"
```

---

## Task 3: Upgrade `story_rewriter.py` — inject emotional-beat context per story

**Files:**
- Modify: `channels/horror-narration/harness/story_rewriter.py`
- Test: `channels/horror-narration/tests/test_story_rewriter.py`

The current `_build_rewrite_prompt` sends Claude a flat rewrite request. We upgrade it to include per-story emotional guidance: a suggested hook angle (delayed-answer or sensory-lead), a recommended ending arousal state, and an explicit note on which beat the story's source material is strongest for. This steers Claude toward playbook-compliant output without rewriting the whole system prompt every call.

- [ ] **Step 1: Write the failing test first**

Create/open `channels/horror-narration/tests/test_story_rewriter.py` and add:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[4]))
sys.path.insert(0, str(Path(__file__).parents[1]))

from harness.story_rewriter import _build_rewrite_prompt, _detect_emotional_angle


def _story(title="Test", text="I found something in the basement.", subreddit="nosleep",
           author="anon", url="https://reddit.com/r/nosleep/x", word_count=80):
    return {"id": "t1", "title": title, "text": text,
            "subreddit": subreddit, "author": author, "url": url, "word_count": word_count}


def test_detect_emotional_angle_sensory():
    """Stories with sensory words trigger sensory-lead angle"""
    s = _story(text="I could hear it breathing. Then I smelled it — wrong, like copper.")
    angle = _detect_emotional_angle(s)
    assert angle == "sensory"


def test_detect_emotional_angle_action():
    """Stories with chase/run/escape words trigger action angle"""
    s = _story(text="I ran but it was already at the door. I couldn't get out.")
    angle = _detect_emotional_angle(s)
    assert angle == "action"


def test_detect_emotional_angle_default():
    """Stories with no strong signal fall back to delayed-answer"""
    s = _story(text="The house was old. Things happened there.")
    angle = _detect_emotional_angle(s)
    assert angle == "delayed-answer"


def test_rewrite_prompt_includes_emotional_guidance():
    """The rewrite prompt must include EMOTIONAL BEAT GUIDANCE section"""
    s = _story()
    prompt = _build_rewrite_prompt(s, "short")
    assert "EMOTIONAL BEAT GUIDANCE" in prompt


def test_rewrite_prompt_includes_arousal_ending_instruction():
    """The rewrite prompt must instruct Claude to end on high-arousal state"""
    s = _story()
    prompt = _build_rewrite_prompt(s, "short")
    assert "high-arousal" in prompt.lower() or "still happening" in prompt.lower()
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
python -m pytest channels/horror-narration/tests/test_story_rewriter.py -v 2>&1 | head -30
```

Expected: ImportError or AttributeError on `_detect_emotional_angle`.

- [ ] **Step 3: Add `_detect_emotional_angle` and upgrade `_build_rewrite_prompt`**

Replace the relevant section of `channels/horror-narration/harness/story_rewriter.py`:

```python
"""
Rewrite a Reddit horror story into an original narration script using Claude.
Includes voice selection based on story mood.
"""
import json
import os
import anthropic


VOICE_MAP = {
    # mood → (short_voice_key, long_voice_key)
    "dread":      ("short_creepy",       "long_form_narrator"),
    "eerie":      ("short_creepy",       "long_form_narrator"),
    "intense":    ("intense",            "intense"),
    "mysterious": ("paranormal_female",  "paranormal_female"),
}
DEFAULT_VOICE_KEYS = ("short_creepy", "long_form_narrator")

# Words that signal sensory-lead angle
_SENSORY_WORDS = {"heard", "smell", "smelled", "breath", "breathing", "cold", "warm",
                  "felt", "sound", "noise", "touch", "tasted", "saw", "light", "dark"}
# Words that signal action-lead angle
_ACTION_WORDS = {"ran", "running", "chased", "grabbed", "dragged", "escaped",
                 "trapped", "locked", "broke", "slammed", "hit", "couldn't"}


def _detect_emotional_angle(story: dict) -> str:
    """
    Detect the strongest emotional angle for this story's source material.
    Returns: "sensory" | "action" | "delayed-answer"
    """
    words = set(story["text"].lower().split())
    sensory_count = len(words & _SENSORY_WORDS)
    action_count = len(words & _ACTION_WORDS)
    if sensory_count >= action_count and sensory_count >= 2:
        return "sensory"
    if action_count >= 2:
        return "action"
    return "delayed-answer"


_ANGLE_GUIDANCE = {
    "sensory": (
        "The source story is SENSORY-RICH. Lead the hook with a specific physical sensation: "
        "a sound, smell, temperature, or texture. The sensory detail is the delayed-answer — "
        "name the sensation before naming the threat."
    ),
    "action": (
        "The source story is ACTION-DRIVEN. Lead with the moment of immediate danger or escape. "
        "Use the delayed-answer technique: describe the action before naming what caused it. "
        "'I ran' before 'I saw what was behind me.'"
    ),
    "delayed-answer": (
        "The source story has no dominant sensory or action signal. Use the delayed-answer hook: "
        "name an impossibility or wrongness without yet naming the full situation. "
        "'There's never been a second door in this hallway.' Let the reader ask why."
    ),
}


def pick_voice(mood: str, target: str, voices_config: dict) -> str:
    short_key, long_key = VOICE_MAP.get(mood, DEFAULT_VOICE_KEYS)
    key = short_key if target == "short" else long_key
    return voices_config.get(key, voices_config.get("long_form_narrator", ""))


def _build_rewrite_prompt(story: dict, target: str) -> str:
    word_target = "60-90 words" if target == "short" else "800-1400 words"
    angle = _detect_emotional_angle(story)
    angle_text = _ANGLE_GUIDANCE[angle]

    return (
        f"Rewrite the following Reddit story as an original horror narration script.\n"
        f"Target format: {target} ({word_target}).\n"
        f"Source: posted by u/{story['author']} on r/{story['subreddit']}\n"
        f"Original URL: {story['url']}\n\n"
        f"EMOTIONAL BEAT GUIDANCE for this story:\n"
        f"Hook angle: {angle_text}\n"
        f"Ending requirement: End on a HIGH-AROUSAL state. Do NOT end on sadness or calm dread alone. "
        f"The final image must be active and unresolved — something still happening, still present, "
        f"still watching. The reader must feel energized to send this to someone, not sit quietly.\n\n"
        f"--- STORY START ---\n{story['text']}\n--- STORY END ---\n\n"
        f"Respond with a JSON object only. No markdown. No explanation."
    )


def rewrite_story(story: dict, target: str, prompt_text: str) -> dict:
    """
    Send a story to Claude for rewriting.

    Returns dict with keys: script, title, hook_overlay, hashtags,
                            topic_cluster, mood, source_attribution, format

    Raises:
        ValueError: if Claude returns a policy error
    """
    import time
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY") or _load_api_key())
    user_content = _build_rewrite_prompt(story, target)

    for attempt in range(3):
        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=prompt_text,
                messages=[{"role": "user", "content": user_content}],
            )
            raw = message.content[0].text.strip()
            if not raw:
                raise json.JSONDecodeError("Empty response", "", 0)
            result = json.loads(raw)
            break
        except json.JSONDecodeError:
            if attempt < 2:
                time.sleep(3)
                continue
            raise RuntimeError(f"Claude returned empty/invalid JSON after 3 attempts for story {story['id']}")

    if result.get("error") == "policy":
        raise ValueError(f"Story declined by policy filter: {story['id']}")

    return result


def _load_api_key() -> str:
    from config import load_config
    return load_config()["anthropic_api_key"]
```

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
python -m pytest channels/horror-narration/tests/test_story_rewriter.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add channels/horror-narration/harness/story_rewriter.py channels/horror-narration/tests/test_story_rewriter.py
git commit -m "feat(horror): inject emotional-beat angle guidance into per-story rewrite prompt"
```

---

## Task 4: Dry-run smoke test — verify the full pipeline still runs

**Files:**
- No modifications — this is a run-only verification step.

- [ ] **Step 1: Set env vars and run a dry-run**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
export HORROR_DRY_RUN=1
python -m channels.horror-narration.harness.orchestrator 2>&1 | tail -30
```

Wait — the module path uses a hyphen. Use the direct file path instead:

```bash
HORROR_DRY_RUN=1 python channels/horror-narration/harness/orchestrator.py 2>&1 | tail -40
```

Expected: Pipeline runs through all steps, prints `🔕 DRY RUN — skipping YouTube upload`, and exits with `🎉 Live: https://youtube.com/shorts/DRY_RUN`.

- [ ] **Step 2: If it fails, check the error**

Common failure modes:
- Missing `ANTHROPIC_API_KEY` env var → `export ANTHROPIC_API_KEY=<key>`
- Missing `ELEVENLABS_API_KEY` → `export ELEVENLABS_API_KEY=<key>`
- Reddit API rate limit → re-run after a few seconds

- [ ] **Step 3: Run the full existing test suite to confirm no regressions**

```bash
python -m pytest channels/horror-narration/tests/ -v
```

Expected: All tests pass (including the 9 new ones from Tasks 2 and 3).

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -p
git commit -m "fix(horror): smoke test fixes for emotional playbook integration"
```

---

## Self-Review

**Spec coverage:**
- ✅ 4-beat structure (Hook/Build/Payoff/Ending) → Task 1 (prompt.txt)
- ✅ Arousal-over-valence rule → Task 1 (prompt) + Task 2 (scorer) + Task 3 (rewriter)
- ✅ High-arousal endings (never end on sadness/contentment) → Tasks 1 and 3
- ✅ Hook engineering (delayed-answer technique) → Tasks 1 and 3
- ✅ Sensory hook vs. action hook vs. delayed-answer → Task 3 `_detect_emotional_angle`
- ✅ Story selection biased toward shareable content → Task 2 `_arousal_score`
- ✅ This is HORROR-ONLY — no changes touch canine-wisdom channel
- ✅ Dry-run smoke test → Task 4

**Placeholder scan:** No TBDs, no "implement later", all code blocks are complete.

**Type consistency:** `_detect_emotional_angle` returns `str` literal, used as dict key in `_ANGLE_GUIDANCE` — keys match exactly. `score_story` signature unchanged, tests match.
