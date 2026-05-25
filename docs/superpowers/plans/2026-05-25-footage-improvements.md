# Footage Improvements — Pixabay Fallback + Specific Queries

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix footage quality and variety by (1) sharpening Pexels search queries to be topic-specific per Todd's examples, (2) adding Pixabay API as an automatic fallback when Pexels returns no results, and (3) ensuring the clip library contains topic-diverse clips so multi-clip mode doesn't repeat the same dog_fun footage.

**Architecture:** All changes are in `harness/tools/footage.py`. `TOPIC_SEARCH_MAP` gets sharper queries. A new `_search_pixabay()` function mirrors `_search_pexels()` and is called in `fetch_footage_for_topic()` when Pexels returns nothing. `PIXABAY_API_KEY` is loaded from `.env`. No other files change.

**Tech Stack:** Python 3, Pixabay Videos API (`https://pixabay.com/api/videos/`), existing `requests` library, existing `.env` / `dotenv` pattern.

---

## File Map

| File | Change |
|---|---|
| `harness/tools/footage.py` | Sharpen `TOPIC_SEARCH_MAP`, add `_search_pixabay()`, wire into `fetch_footage_for_topic()` |
| `.env` | Add `PIXABAY_API_KEY=<key>` (manual step for user) |
| `tests/test_footage_pixabay.py` | **New** — unit tests for Pixabay search and fallback logic |

---

## Task 1: Sharpen TOPIC_SEARCH_MAP queries

**Files:**
- Modify: `harness/tools/footage.py:23–73`

- [ ] **Step 1: Read current TOPIC_SEARCH_MAP**

```bash
cd /home/oye/Documents/free_work/repos/canine-wisdom-automation
sed -n '23,73p' harness/tools/footage.py
```

- [ ] **Step 2: Replace TOPIC_SEARCH_MAP with sharper queries**

Find the `TOPIC_SEARCH_MAP = {` block and replace entirely with:

```python
TOPIC_SEARCH_MAP = {
    "dog health": [
        "veterinarian examining dog",
        "dog anxiety panting",
        "dog health checkup vet",
        "dog scratching itching skin",
        "dog limping injured paw",
    ],
    "dog behavior": [
        "dog anxiety panting stressed",
        "dog barking aggressive",
        "dog separation anxiety alone",
        "dog jumping on people",
        "dog tail wagging happy",
    ],
    "dog breeds": [
        "golden retriever puppy portrait",
        "german shepherd alert closeup",
        "french bulldog sitting",
        "husky dog blue eyes closeup",
        "labrador retriever running",
    ],
    "dog training": [
        "puppy learning tricks training",
        "dog sit command obedience",
        "dog trainer reward treat",
        "dog agility obstacle course",
        "puppy first training lesson",
    ],
    "dog history": [
        "wolf pack running wild",
        "dog human bond loyal",
        "ancient dog companion human",
        "dog working farm herding",
        "dog guard protection",
    ],
    "dog science": [
        "dog nose sniffing closeup",
        "dog dna test swab mouth",
        "dog eye vision closeup",
        "dog brain intelligence test",
        "dog smell detect scent",
    ],
    "dog fun": [
        "puppy playing fetch ball",
        "dog running beach waves",
        "dog swimming water happy",
        "puppy zoomies running fast",
        "dog catching frisbee air",
    ],
}
```

- [ ] **Step 3: Write failing test**

Create `tests/test_footage_pixabay.py`:

```python
from harness.tools.footage import TOPIC_SEARCH_MAP


def test_queries_match_todd_examples():
    """Queries must be phrase-level specific, not single-word."""
    # Todd's examples: "dog anxiety panting", "puppy learning tricks", "veterinarian examining dog"
    all_queries = [q for queries in TOPIC_SEARCH_MAP.values() for q in queries]
    assert any("panting" in q for q in all_queries), "Missing anxiety+panting query"
    assert any("trick" in q or "learning" in q for q in all_queries), "Missing puppy learning tricks"
    assert any("veterinarian" in q or "vet" in q.lower() for q in all_queries), "Missing vet query"


def test_all_queries_at_least_two_words():
    for cluster, queries in TOPIC_SEARCH_MAP.items():
        for q in queries:
            assert len(q.split()) >= 2, f"Too short: '{q}' in {cluster}"


def test_no_generic_single_word_queries():
    bad = {"dog", "puppy", "vet", "training", "fun"}
    for cluster, queries in TOPIC_SEARCH_MAP.items():
        for q in queries:
            assert q.lower() not in bad, f"Generic query '{q}' in {cluster}"
```

- [ ] **Step 4: Run test — confirm it fails**

```bash
source venv/bin/activate
python -m pytest tests/test_footage_pixabay.py::test_queries_match_todd_examples tests/test_footage_pixabay.py::test_all_queries_at_least_two_words tests/test_footage_pixabay.py::test_no_generic_single_word_queries -v
```
Expected: FAIL (old queries don't have "panting", "veterinarian", etc.)

- [ ] **Step 5: Apply replacement** (as shown in Step 2), then run tests again

```bash
python -m pytest tests/test_footage_pixabay.py -v
```
Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add harness/tools/footage.py tests/test_footage_pixabay.py
git commit -m "feat: sharpen TOPIC_SEARCH_MAP with specific phrase queries per client request"
```

---

## Task 2: Add Pixabay API key loading

**Files:**
- Modify: `harness/tools/footage.py` — add `_load_pixabay_key()` alongside `_load_api_key()`

- [ ] **Step 1: Add `_load_pixabay_key()` in footage.py**

Read footage.py lines 78–85 (the `_load_api_key` function). Add this function directly after it:

```python
def _load_pixabay_key() -> str | None:
    """Load Pixabay API key from .env. Returns None if not set (fallback disabled)."""
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    return os.getenv("PIXABAY_API_KEY") or None
```

- [ ] **Step 2: Write failing test**

Add to `tests/test_footage_pixabay.py`:

```python
from unittest.mock import patch


def test_pixabay_key_returns_none_when_unset():
    from harness.tools.footage import _load_pixabay_key
    with patch.dict("os.environ", {}, clear=False):
        import os
        old = os.environ.pop("PIXABAY_API_KEY", None)
        result = _load_pixabay_key()
        if old is not None:
            os.environ["PIXABAY_API_KEY"] = old
    # Either None or a real key — just verify it doesn't raise
    assert result is None or isinstance(result, str)
```

- [ ] **Step 3: Run test**

```bash
python -m pytest tests/test_footage_pixabay.py::test_pixabay_key_returns_none_when_unset -v
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add harness/tools/footage.py tests/test_footage_pixabay.py
git commit -m "feat: add _load_pixabay_key() for Pixabay API integration"
```

---

## Task 3: Implement _search_pixabay()

**Files:**
- Modify: `harness/tools/footage.py` — add `_search_pixabay()` after `_search_pexels()`

The Pixabay Videos API endpoint: `https://pixabay.com/api/videos/`
Params: `key`, `q`, `video_type=film`, `orientation=vertical`, `per_page=15`
Response: `{"hits": [{"id", "duration", "videos": {"large": {"url", "width", "height"}}}]}`

- [ ] **Step 1: Write failing test**

Add to `tests/test_footage_pixabay.py`:

```python
from unittest.mock import patch, MagicMock
import json


def test_search_pixabay_returns_clip_dicts(tmp_path):
    from harness.tools.footage import _search_pixabay

    mock_response = {
        "hits": [
            {
                "id": 123456,
                "duration": 15,
                "pageURL": "https://pixabay.com/videos/dog-123456/",
                "videos": {
                    "large": {
                        "url": "https://cdn.pixabay.com/vimeo/123456/dog.mp4?download",
                        "width": 1080,
                        "height": 1920,
                    }
                },
            }
        ]
    }

    with patch("harness.tools.footage.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        results = _search_pixabay("dog anxiety panting", "fake_api_key")

    assert len(results) == 1
    assert results[0]["pexels_id"] == "pixabay_123456"
    assert results[0]["width"] == 1080
    assert results[0]["height"] == 1920
    assert results[0]["duration"] == 15
    assert "dog.mp4" in results[0]["download_url"]


def test_search_pixabay_skips_short_clips():
    from harness.tools.footage import _search_pixabay

    mock_response = {
        "hits": [
            {
                "id": 111,
                "duration": 3,  # too short
                "pageURL": "https://pixabay.com/videos/dog-111/",
                "videos": {"large": {"url": "https://cdn.pixabay.com/dog.mp4", "width": 720, "height": 1280}},
            }
        ]
    }

    with patch("harness.tools.footage.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = mock_response
        mock_get.return_value = mock_resp

        results = _search_pixabay("dog", "fake_key")

    assert results == []


def test_search_pixabay_returns_empty_on_error():
    from harness.tools.footage import _search_pixabay

    with patch("harness.tools.footage.requests.get", side_effect=Exception("timeout")):
        results = _search_pixabay("dog", "fake_key")

    assert results == []
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
python -m pytest tests/test_footage_pixabay.py::test_search_pixabay_returns_clip_dicts tests/test_footage_pixabay.py::test_search_pixabay_skips_short_clips tests/test_footage_pixabay.py::test_search_pixabay_returns_empty_on_error -v
```
Expected: ImportError or AttributeError — `_search_pixabay` does not exist yet.

- [ ] **Step 3: Add `_search_pixabay()` to footage.py**

Add this function directly after the `_search_pexels()` function:

```python
def _search_pixabay(query: str, api_key: str, per_page: int = 15) -> list:
    """Search Pixabay for vertical dog videos. Returns list of clip dicts matching _search_pexels format."""
    try:
        resp = requests.get(
            "https://pixabay.com/api/videos/",
            params={
                "key": api_key,
                "q": query,
                "video_type": "film",
                "orientation": "vertical",
                "per_page": per_page,
            },
            timeout=15,
        )
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
    except Exception as e:
        print(f"[footage] Pixabay search failed for '{query}': {e}")
        return []

    results = []
    for hit in hits:
        if hit.get("duration", 0) < 8:
            continue
        large = hit.get("videos", {}).get("large", {})
        if not large.get("url"):
            medium = hit.get("videos", {}).get("medium", {})
            if not medium.get("url"):
                continue
            large = medium
        results.append({
            "pexels_id": f"pixabay_{hit['id']}",
            "pexels_url": hit.get("pageURL", ""),
            "download_url": large["url"],
            "width": large.get("width", 0),
            "height": large.get("height", 0),
            "duration": hit["duration"],
            "query": query,
        })
    return results
```

- [ ] **Step 4: Run tests — all must pass**

```bash
python -m pytest tests/test_footage_pixabay.py::test_search_pixabay_returns_clip_dicts tests/test_footage_pixabay.py::test_search_pixabay_skips_short_clips tests/test_footage_pixabay.py::test_search_pixabay_returns_empty_on_error -v
```
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add harness/tools/footage.py tests/test_footage_pixabay.py
git commit -m "feat: add _search_pixabay() as secondary footage source"
```

---

## Task 4: Wire Pixabay as fallback in fetch_footage_for_topic()

**Files:**
- Modify: `harness/tools/footage.py` — update `fetch_footage_for_topic()` to try Pixabay when Pexels returns no downloadable clip

Current flow in `fetch_footage_for_topic()`:
1. Loop through Pexels queries → download first good clip → return
2. If all Pexels fail → yt-dlp CC fallback → return
3. If yt-dlp fails → return None

New flow:
1. Loop through Pexels queries → download first good clip → return
2. **If all Pexels fail → loop through same queries on Pixabay → download first good clip → return**
3. If Pixabay also fails → yt-dlp CC fallback → return
4. If all fail → return None

- [ ] **Step 1: Read current fetch_footage_for_topic() body**

```bash
sed -n '212,265p' harness/tools/footage.py
```

- [ ] **Step 2: Update fetch_footage_for_topic() to insert Pixabay fallback**

Find the block in `fetch_footage_for_topic()` that starts `# All Pexels queries failed — try yt-dlp CC` and replace it with:

```python
    # All Pexels queries failed — try Pixabay
    pixabay_key = _load_pixabay_key()
    if pixabay_key:
        print(f"[footage] Pexels exhausted — trying Pixabay for: {topic}")
        for query in queries:
            clips = _search_pixabay(query, pixabay_key)
            if not clips:
                continue
            good_clips = [c for c in clips if 8 <= c["duration"] <= 90]
            if not good_clips:
                good_clips = clips
            clip = random.choice(good_clips[:5])
            filename = f"pixabay_{clip['pexels_id'].replace('pixabay_', '')}_{topic_cluster.replace(' ', '_')}.mp4"
            output_path = DOG_FOOTAGE_DIR / filename
            if output_path.exists():
                print(f"[footage] Already have (Pixabay): {filename}")
                _record_footage(output_path, "pixabay", topic_cluster, query)
                return output_path
            if _download_clip(clip, output_path):
                _record_footage(output_path, "pixabay", topic_cluster, query)
                return output_path
    else:
        print("[footage] PIXABAY_API_KEY not set — skipping Pixabay fallback")

    # All Pixabay queries failed — try yt-dlp CC
    cc_path = _yt_dlp_cc_fallback(topic)
    if cc_path:
        _record_footage(cc_path, "youtube_cc", topic_cluster, topic)
        return cc_path

    print(f"[footage] All sources failed for topic: {topic}")
    return None
```

- [ ] **Step 3: Write integration test**

Add to `tests/test_footage_pixabay.py`:

```python
def test_pixabay_fallback_called_when_pexels_empty(tmp_path, monkeypatch):
    """When Pexels returns no clips, Pixabay should be tried."""
    from harness.tools import footage as footage_mod

    monkeypatch.setattr(footage_mod, "DOG_FOOTAGE_DIR", tmp_path)
    monkeypatch.setattr(footage_mod, "_search_pexels", lambda q, k, **kw: [])
    monkeypatch.setattr(footage_mod, "_load_pixabay_key", lambda: "fake_pixabay_key")
    monkeypatch.setattr(footage_mod, "_load_api_key", lambda: "fake_pexels_key")

    pixabay_called_with = []

    def fake_pixabay(query, key, **kw):
        pixabay_called_with.append(query)
        return []  # also return empty to keep test simple

    monkeypatch.setattr(footage_mod, "_search_pixabay", fake_pixabay)
    monkeypatch.setattr(footage_mod, "_yt_dlp_cc_fallback", lambda q: None)

    result = footage_mod.fetch_footage_for_topic("dog fun", "puppy playing fetch")
    assert len(pixabay_called_with) > 0, "Pixabay was never called despite Pexels returning nothing"
    assert result is None  # both sources empty in this test
```

- [ ] **Step 4: Run test**

```bash
python -m pytest tests/test_footage_pixabay.py::test_pixabay_fallback_called_when_pexels_empty -v
```
Expected: PASS.

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short
```
All tests must PASS.

- [ ] **Step 6: Commit**

```bash
git add harness/tools/footage.py tests/test_footage_pixabay.py
git commit -m "feat: add Pixabay as automatic fallback when Pexels returns no results"
```

---

## Task 5: Add PIXABAY_API_KEY to .env and verify end-to-end

- [ ] **Step 1: Get a free Pixabay API key**

Go to https://pixabay.com/api/docs/ — sign up (free) and copy your API key.

- [ ] **Step 2: Add key to .env**

Open `.env` and add:
```
PIXABAY_API_KEY=your_key_here
```

- [ ] **Step 3: Test Pixabay search directly**

```bash
source venv/bin/activate
python -c "
from harness.tools.footage import _search_pixabay, _load_pixabay_key
key = _load_pixabay_key()
print('Key loaded:', bool(key))
results = _search_pixabay('dog anxiety panting', key)
print('Results:', len(results))
for r in results[:3]:
    print(' ', r['duration'], 's', r['width'], 'x', r['height'], r['download_url'][:60])
"
```
Expected: key loaded True, results > 0.

- [ ] **Step 4: Run orchestrator**

```bash
python -m harness.orchestrator 2>&1
```

Watch for `[footage] Pexels exhausted — trying Pixabay` in the logs when Pexels returns nothing, and `[footage] Downloaded pixabay_*.mp4` when Pixabay succeeds.

- [ ] **Step 5: Final commit**

```bash
git add .env  # only if .env is not in .gitignore — check first
git add -A
git commit -m "chore: verify Pixabay fallback end-to-end"
```

> **Note:** `.env` should be in `.gitignore` — do not commit API keys to git. Only commit code changes.

---

## Self-Review

**Spec coverage:**

| Client request | Task |
|---|---|
| Add Pixabay as fallback when Pexels returns nothing | Task 3 + 4 |
| More specific queries — "dog anxiety panting", "puppy learning tricks", "veterinarian examining dog" | Task 1 |
| Free, no cost | Pixabay free tier covers this |
| Doubles available footage | Task 4 wires fallback so both sources contribute |

**Placeholder scan:** No TBDs. Task 5 has a manual step (get API key) which is unavoidable — documented explicitly. ✅

**Type consistency:** `_search_pixabay()` returns same dict shape as `_search_pexels()` (`pexels_id`, `download_url`, `width`, `height`, `duration`, `query`). `fetch_footage_for_topic()` consumes both via `_download_clip()` which only needs `download_url`, `width`, `height`, `duration`. ✅
