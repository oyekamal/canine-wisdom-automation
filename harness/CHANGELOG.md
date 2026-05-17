# Harness CHANGELOG

Auto-updated by `harness/agents/healer.py` when self-healing changes are applied.

---

## [Session 1] 2026-05-17

### Added
- `harness/storage.py` — atomic JSON read/write with file locking (fcntl) on state.json
- `harness/evals/base.py` — `EvalResult` dataclass, `save_eval_result`, `_parse_llm_score`
- `harness/evals/hook_eval.py` — LLM judge: first-sentence hook strength ≥7/10
- `harness/evals/script_eval.py` — LLM judge: accuracy, novelty, pacing ≥7/10
- `harness/evals/title_eval.py` — LLM judge: CTR potential ≥7/10
- `harness/evals/description_eval.py` — LLM judge: SEO quality ≥7/10
- `harness/evals/thumbnail_eval.py` — placeholder (Session 3)
- `harness/evals/audio_eval.py` — deterministic: ffprobe duration 10–90s
- `harness/evals/video_eval.py` — deterministic: ffprobe resolution 1080x1920
- `harness/evals/channel_eval.py` — placeholder (Session 3)
- `harness/orchestrator.py` — eval-gated daily pipeline replacing main.py
- `harness/data/` — JSON state storage with all subdirectories
- `harness/tests/` — full test suite (39 tests)
