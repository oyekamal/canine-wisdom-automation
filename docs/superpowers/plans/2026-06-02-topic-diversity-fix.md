# Topic Diversity Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the canine-wisdom harness so every video covers a genuinely different, specific dog topic instead of generating near-identical "dog behavior/memory/yawning" scripts every run.

**Architecture:** Three coordinated fixes: (1) pass the selected topic phrase into `generate_script()` so Claude writes about the chosen topic; (2) pass real covered-topics into `script_eval()` so the eval can actually penalise repeats; (3) tighten the garbage filter in `trend.py` so the topic queue contains specific, unique topics instead of fragments like "and fun" or "video". No new files — all changes are in-place.

**Tech Stack:** Python 3, existing harness at `harness/`, `generate_script.py`, `harness/evals/script_eval.py`, `harness/agents/trend.py`.

**Root causes confirmed:**
- `harness/orchestrator.py:233` — `script_eval(script_text, recent_topics=[])` — always passes empty list
- `harness/orchestrator.py:206` — `generate_script(channel_config=channel_config)` — topic phrase never passed
- `generate_script.py:108` — `generate_script(channel_config=None)` — no `topic` parameter
- `harness/agents/trend.py` — garbage filter misses single-word junk and non-English suggestions

---

## Task 1: Pass topic into `generate_script()` and inject it into the Claude prompt

**Files:**
- Modify: `generate_script.py` (signature + prompt builder)
- Test: `tests/test_generate_script.py`

The topic selected from the queue (e.g. "dog nose print unique fingerprint") must reach the Claude prompt so Claude writes specifically about that topic, not whatever it feels like.

- [ ] **Step 1: Write the failing test**

Open `tests/test_generate_script.py` and add this test (keep existing tests):

```python
def test_build_prompt_includes_forced_topic():
    """When a topic is provided, the prompt must instruct Claude to write about it."""
    from generate_script import _build_prompt
    prompt = _build_prompt(channel_config=None, topic="dog nose print unique fingerprint")
    assert "dog nose print unique fingerprint" in prompt
    assert "WRITE ABOUT THIS SPECIFIC TOPIC" in prompt or "TOPIC:" in prompt
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
python3 -m pytest tests/test_generate_script.py::test_build_prompt_includes_forced_topic -v
```

Expected: FAIL — `_build_prompt` doesn't accept a `topic` argument yet.

- [ ] **Step 3: Update `_build_prompt` signature and inject topic**

In `generate_script.py`, change the `_build_prompt` signature from:
```python
def _build_prompt(channel_config=None) -> str:
```
to:
```python
def _build_prompt(channel_config=None, topic: str = "") -> str:
```

Then, inside `_build_prompt`, just before the `return` statement (whether it returns from the file-based path or the inline path), add the topic injection. For the **file-based path** (when `channel_config.prompt_path.exists()`), add after the `.replace()` chain:

```python
        result = raw.replace("{hooks_text}", hooks_text) \
                    .replace("{titles_text}", titles_text) \
                    .replace("{covered_text}", covered_text)
        if topic:
            result += f"\n\nTOPIC: You MUST write about this specific topic: \"{topic}\". Do not choose a different topic."
        return result
```

For the **inline fallback path**, find the `return f"""..."""` block and add at the end of that f-string, just before the closing `"""`:

```python
\n\nTOPIC: {"You MUST write about this specific topic: \\"" + topic + "\\". Do not choose a different topic." if topic else "Choose any specific dog topic not in the covered list above."}
```

- [ ] **Step 4: Update `generate_script()` to accept and pass `topic`**

Change the `generate_script` signature from:
```python
def generate_script(channel_config=None) -> dict:
```
to:
```python
def generate_script(channel_config=None, topic: str = "") -> dict:
```

Then find the `_build_prompt(channel_config=channel_config)` call inside `generate_script` and change it to:
```python
_build_prompt(channel_config=channel_config, topic=topic)
```

- [ ] **Step 5: Run the test to confirm it passes**

```bash
python3 -m pytest tests/test_generate_script.py::test_build_prompt_includes_forced_topic -v
```

Expected: PASS.

- [ ] **Step 6: Run the full test suite to check for regressions**

```bash
python3 -m pytest tests/test_generate_script.py -v 2>&1 | tail -15
```

Expected: all existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add generate_script.py tests/test_generate_script.py
git commit -m "feat(canine): pass selected topic into generate_script and Claude prompt"
```

---

## Task 2: Pass real covered topics into `script_eval()` in the orchestrator

**Files:**
- Modify: `harness/orchestrator.py` (one line fix)
- Test: `harness/tests/test_orchestrator_topic_passing.py` (new)

The orchestrator calls `script_eval(script_text, recent_topics=[])` with a hardcoded empty list. This means the eval never penalises repeated topics. Fix: pull covered topics from learnings and pass them.

- [ ] **Step 1: Write the failing test**

Create `harness/tests/test_orchestrator_topic_passing.py`:

```python
"""Verify the orchestrator passes covered topics into script_eval, not []."""
import ast
from pathlib import Path


def test_orchestrator_passes_covered_topics_to_script_eval():
    """
    Parse orchestrator.py and confirm script_eval is NOT called with recent_topics=[].
    This catches the regression where we hardcoded an empty list.
    """
    src = Path("harness/orchestrator.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Find calls to script_eval(...)
        func = node.func
        name = (func.id if isinstance(func, ast.Name) else
                func.attr if isinstance(func, ast.Attribute) else "")
        if name != "script_eval":
            continue
        # Check keyword args
        for kw in node.keywords:
            if kw.arg == "recent_topics":
                # Must NOT be an empty list literal
                assert not (isinstance(kw.value, ast.List) and len(kw.value.elts) == 0), \
                    "script_eval called with recent_topics=[] — covered topics must be passed"
```

- [ ] **Step 2: Run the test to confirm it fails**

```bash
python3 -m pytest harness/tests/test_orchestrator_topic_passing.py -v
```

Expected: FAIL — `recent_topics=[]` is hardcoded on the current line.

- [ ] **Step 3: Fix the orchestrator — pass covered topics**

In `harness/orchestrator.py`, find the line (around line 233):
```python
script_result = retry_with_backoff(lambda: script_eval(script_text, recent_topics=[]), max_retries=2, initial_backoff=5, step_name="script_eval")
```

Replace it with:
```python
try:
    from harness.tools.learnings import get_covered_topics as _get_covered
    _recent_topics = _get_covered(days=30)
except Exception:
    _recent_topics = []
script_result = retry_with_backoff(lambda: script_eval(script_text, recent_topics=_recent_topics), max_retries=2, initial_backoff=5, step_name="script_eval")
```

- [ ] **Step 4: Also pass topic into generate_script call in the orchestrator**

In `harness/orchestrator.py`, find the line (around line 206):
```python
metadata = generate_script(channel_config=channel_config)
```

Replace it with:
```python
metadata = generate_script(channel_config=channel_config, topic=topic)
```

- [ ] **Step 5: Run the test to confirm it passes**

```bash
python3 -m pytest harness/tests/test_orchestrator_topic_passing.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add harness/orchestrator.py harness/tests/test_orchestrator_topic_passing.py
git commit -m "fix(canine): pass covered topics to script_eval and topic to generate_script in orchestrator"
```

---

## Task 3: Tighten the topic queue garbage filter

**Files:**
- Modify: `harness/agents/trend.py`
- Test: `harness/tests/test_trend_garbage_filter.py`

The current filter lets through: "and fun", "you didn't know", "video", "telugu", "dog behavior 101", "dog behavior videos". These are useless as Claude prompts. We need a stricter positive-match filter: a suggestion must look like a genuine fact/question/concept phrase, not a platform artifact or language artifact.

- [ ] **Step 1: Write the failing tests**

Create `harness/tests/test_trend_garbage_filter.py`:

```python
"""Test that the garbage filter rejects platform artifacts and junk suggestions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[2]))

from harness.agents.trend import _is_garbage


def test_rejects_conjunction_fragments():
    assert _is_garbage("and fun") is True
    assert _is_garbage("or dogs") is True

def test_rejects_meta_platform_terms():
    assert _is_garbage("dog behavior videos") is True
    assert _is_garbage("dog facts shorts") is True
    assert _is_garbage("dog behavior 101") is True

def test_rejects_non_english():
    assert _is_garbage("dog facts in telugu") is True
    assert _is_garbage("dog facts in hindi") is True

def test_rejects_vague_you_phrases():
    assert _is_garbage("you didn't know") is True
    assert _is_garbage("dog facts you didn't know") is True

def test_rejects_single_word_residue():
    assert _is_garbage("video") is True
    assert _is_garbage("dogs") is True  # too short / no substance

def test_accepts_real_topics():
    assert _is_garbage("dogs can detect cancer in humans") is False
    assert _is_garbage("why do dogs tilt their head") is False
    assert _is_garbage("dog nose print is unique like fingerprint") is False
    assert _is_garbage("oldest dog breeds in history") is False
    assert _is_garbage("how dogs read human emotions") is False

def test_accepts_behavior_topics_with_substance():
    """'dog behavior' alone is vague but 'dog separation anxiety signs' is real."""
    assert _is_garbage("dog behavior") is True   # too generic, no specific angle
    assert _is_garbage("dog separation anxiety signs") is False
```

- [ ] **Step 2: Run the tests to confirm they fail**

```bash
python3 -m pytest harness/tests/test_trend_garbage_filter.py -v 2>&1 | head -40
```

Expected: several FAIL — current filter passes "and fun", "dog behavior videos", etc.

- [ ] **Step 3: Rewrite `_is_garbage` in `harness/agents/trend.py`**

Replace the entire `_is_garbage` function (find it by `def _is_garbage`) with:

```python
# Extended garbage terms — platform artifacts, language tags, meta words
_GARBAGE_TERMS = {
    "in hindi", "in english", "in tamil", "in telugu", "in urdu", "in kannada",
    "in marathi", "in bengali", "for kids", "for beginners",
    "shorts", "short", "2024", "2025", "2026",
    "top 10", "top 5", "top 3", "top 7",
    "compilation", "playlist", "subscribe", "channel",
    "videos", "video", "101", "part 1", "part 2", "episode",
    "you didn't know", "you don't know", "did you know",
    "amazing facts", "mind blowing", "unbelievable",
}

# A topic must contain at least one of these substance words to be real
_SUBSTANCE_WORDS = {
    "why", "how", "what", "when", "can", "do", "does", "are", "is",
    "detect", "smell", "hear", "see", "feel", "learn", "read", "understand",
    "ancient", "history", "breed", "health", "disease", "cancer", "anxiety",
    "sleep", "dream", "memory", "emotion", "loyal", "nose", "brain",
    "train", "bite", "bark", "growl", "wag", "lick", "play",
    "unique", "oldest", "fastest", "strongest", "smartest",
    "separation", "aggression", "fear", "stress", "pack",
    "signs", "symptoms", "facts", "secret", "reason", "cause",
}


def _is_garbage(suggestion: str) -> bool:
    s = suggestion.lower().strip()

    # Too short
    if len(s) < 10:
        return True

    # Must mention dogs
    if not any(w in s for w in ["dog", "puppy", "canine", "pup"]):
        return True

    # Contains a garbage term
    if any(g in s for g in _GARBAGE_TERMS):
        return True

    # Starts with a conjunction/preposition fragment
    import re as _re
    if _re.match(r'^(and|or|but|the |a |an |in |on |at |by |to |you )', s):
        return True

    # Must contain at least one substance word to be a real topic
    words = set(s.split())
    if not words & _SUBSTANCE_WORDS:
        return True

    return False
```

- [ ] **Step 4: Run the tests to confirm they pass**

```bash
python3 -m pytest harness/tests/test_trend_garbage_filter.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Delete today's cached topic queue so it rebuilds with the new filter**

```bash
rm -f harness/data/topics/$(date +%Y-%m-%d).json
```

- [ ] **Step 6: Commit**

```bash
git add harness/agents/trend.py harness/tests/test_trend_garbage_filter.py
git commit -m "fix(canine): tighten topic queue garbage filter — require substance words, reject platform artifacts"
```

---

## Task 4: Integration smoke test — verify a dry-run produces a unique, on-topic script

**Files:**
- No modifications — run-only verification.

- [ ] **Step 1: Delete today's topic queue cache so it rebuilds fresh**

```bash
rm -f harness/data/topics/$(date +%Y-%m-%d).json
```

- [ ] **Step 2: Run the harness in dry mode (no upload)**

We don't have a `CANINE_DRY_RUN` env var, so just check that the script is generated and inspect the topic. Run with a quick import check first:

```bash
python3 -c "
from harness.agents.trend import build_topic_queue, pick_best_topic
import datetime
q = build_topic_queue(date=datetime.date.today().strftime('%Y-%m-%d'))
t = pick_best_topic(q)
print('Top topic:', t['topic'] if t else 'NONE')
print('Cluster:', t['topic_cluster'] if t else 'NONE')
print('First 5 topics:')
for top in q['topics'][:5]:
    print(' -', top['topic'], '|', top['topic_cluster'])
"
```

Expected: all 5 topics are specific, descriptive dog fact phrases — no "and fun", "video", or single-word junk.

- [ ] **Step 3: Run the full harness test suite**

```bash
python3 -m pytest harness/tests/ tests/test_generate_script.py -v 2>&1 | tail -25
```

Expected: all tests pass (pre-existing `test_reddit_harvest` failures are unrelated and can be ignored).

- [ ] **Step 4: Spot-check the prompt to confirm topic injection works end-to-end**

```bash
python3 -c "
from generate_script import _build_prompt
p = _build_prompt(topic='dogs can detect low blood sugar in diabetics')
# Find the TOPIC line
for line in p.split('\n'):
    if 'TOPIC' in line or 'diabetics' in line:
        print(repr(line))
"
```

Expected: prints a line containing `TOPIC:` and `dogs can detect low blood sugar in diabetics`.

---

## Self-Review

**Spec coverage:**
- ✅ Topic phrase injected into Claude prompt → Task 1 (`generate_script._build_prompt`)
- ✅ `generate_script()` accepts topic param → Task 1
- ✅ Orchestrator passes topic to `generate_script` → Task 2 Step 4
- ✅ Orchestrator passes real covered topics to `script_eval` → Task 2 Step 3
- ✅ Garbage filter rejects platform artifacts, language tags, meta words → Task 3
- ✅ Garbage filter requires substance words → Task 3
- ✅ Integration smoke test → Task 4
- ✅ Canine-wisdom only — horror harness untouched

**Placeholder scan:** No TBDs, all code complete.

**Type consistency:**
- `generate_script(channel_config=None, topic: str = "")` — default `""` means existing callers (e.g. tests) with no topic arg are unaffected
- `_build_prompt(channel_config=None, topic: str = "")` — same
- `_is_garbage(suggestion: str) -> bool` — signature unchanged, tests import it directly
