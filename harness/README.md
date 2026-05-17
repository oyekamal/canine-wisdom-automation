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

**Run tests:**
```bash
python -m pytest harness/tests/ -v
```

## How evals work

Every artifact is scored before upload. LLM evals retry up to 3× (regenerating
the artifact each time). Hard evals halt the pipeline immediately on failure.

| Eval | Type | Threshold | On fail |
|------|------|-----------|---------|
| hook_eval | LLM judge | ≥7/10 | Regenerate script (3× max) |
| script_eval | LLM judge | ≥7/10 | Regenerate script (3× max) |
| title_eval | LLM judge | ≥7/10 | Regenerate script (3× max) |
| thumbnail_eval | Placeholder | — | Pick best (Session 3) |
| description_eval | LLM judge | ≥7/10 | Log incident + continue |
| audio_eval | Deterministic | pass/fail | Halt pipeline |
| video_eval | Deterministic | pass/fail | Halt pipeline |
| channel_eval | Placeholder | — | Trigger healer (Session 4) |

## Incident reports

Written to `harness/data/incidents/{timestamp}-{id}.json` and `.md` when evals fail
after max retries or hard-fail. The self-healing agent (Session 4) reads these and
proposes code patches.

## Self-healing bounds (Session 4)

The healer is allowed to:
- Install pip packages and update `requirements.txt`
- Add new files and edit existing pipeline scripts
- Create git branches and commit changes

The healer is NOT allowed to:
- Rotate or expose API keys
- Delete `archive/` or `run_logs/`
- Push to remote without user approval
- Spend money on paid APIs without surfacing a cost estimate first

## Data directory

```
harness/data/
├── performance/     {video_id}.json + index.json  (Session 3)
├── competitors/     {channel_id}.json             (Session 2)
├── topics/          {YYYY-MM-DD}.json             (Session 2)
├── eval_runs/       {date}/{run_id}/{eval_name}.json
├── incidents/       {timestamp}-{id}.json + .md
├── comments/        {video_id}.json               (Session 4)
├── thumbnails/      {video_id}.json               (Session 3)
└── state.json       global state (KPIs, config, last run)
```

## Extending

**Add a new eval:** Create `harness/evals/my_eval.py` returning `EvalResult`, import
it in `orchestrator.py`, call `save_eval_result(result, run_id)` after running it.

**Add a new agent:** Create `harness/agents/my_agent.py`, import and call it from
`orchestrator.py` at the appropriate step.

## Session roadmap

- **Session 1 (done):** Storage + evals + orchestrator (eval-gated pipeline)
- **Session 2:** Competitor intel + trend research + SEO module
- **Session 3:** Thumbnail generation + analytics tracking + performance storage
- **Session 4:** Comment agent + self-healing loop + CHANGELOG auto-update
