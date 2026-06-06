#!/usr/bin/env python3
"""
low_cpu_runner.py — Run a channel pipeline only when CPU is idle.

Usage:
  python scripts/low_cpu_runner.py --channel dailyygstories
  python scripts/low_cpu_runner.py --channel horror-narration
  python scripts/low_cpu_runner.py --all   # runs both video channels

Guards:
  - CPU load average (1-min) must be < CPU_LOAD_THRESHOLD (default 1.5)
  - Per-channel lock file prevents overlapping runs
  - Min gap between runs: MIN_GAP_MINUTES (default 240 = 4 hours) per channel

If guard fails: exits 0 silently (not an error, just "not now").
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(REPO_ROOT))

CPU_LOAD_THRESHOLD = float(os.environ.get("LOW_CPU_THRESHOLD", "1.5"))
MIN_GAP_MINUTES = int(os.environ.get("MIN_GAP_MINUTES", "240"))
RUNNER_STATE_DIR = Path.home() / ".kamil-harness" / "video-runner"

CHANNEL_PIPELINES = {
    "dailyygstories": "channels.dailyygstories.harness.orchestrator:run_dailyygstories_pipeline",
    "horror-narration": "channels.horror_narration.harness.orchestrator:run_horror_pipeline",
    "canine-wisdom": "harness.orchestrator:run_canine_wisdom_pipeline",
}

VIDEO_CHANNELS = ["dailyygstories", "horror-narration"]


def _cpu_load() -> float:
    try:
        return os.getloadavg()[0]
    except (AttributeError, OSError):
        return 0.0


def _is_cpu_idle() -> bool:
    load = _cpu_load()
    print(f"[low_cpu_runner] CPU load: {load:.2f} (threshold: {CPU_LOAD_THRESHOLD})")
    return load < CPU_LOAD_THRESHOLD


def _state_path(channel: str) -> Path:
    RUNNER_STATE_DIR.mkdir(parents=True, exist_ok=True)
    return RUNNER_STATE_DIR / f"{channel}.json"


def _lock_path(channel: str) -> Path:
    RUNNER_STATE_DIR.mkdir(parents=True, exist_ok=True)
    return RUNNER_STATE_DIR / f"{channel}.lock"


def _is_locked(channel: str) -> bool:
    lock = _lock_path(channel)
    if not lock.exists():
        return False
    age = time.time() - lock.stat().st_mtime
    if age > 7200:
        lock.unlink(missing_ok=True)
        return False
    return True


def _acquire_lock(channel: str):
    _lock_path(channel).write_text(str(os.getpid()))


def _release_lock(channel: str):
    _lock_path(channel).unlink(missing_ok=True)


def _last_run(channel: str):
    sp = _state_path(channel)
    if not sp.exists():
        return None
    try:
        data = json.loads(sp.read_text())
    except Exception:
        return None
    ts = data.get("last_run_at")
    if not ts:
        return None
    return datetime.fromisoformat(ts)


def _record_run(channel: str, success: bool):
    sp = _state_path(channel)
    try:
        data = json.loads(sp.read_text()) if sp.exists() else {}
    except Exception:
        data = {}
    data["last_run_at"] = datetime.now().isoformat()
    data["last_success"] = success
    sp.write_text(json.dumps(data, indent=2))


def _min_gap_passed(channel: str) -> bool:
    last = _last_run(channel)
    if last is None:
        return True
    gap = datetime.now() - last
    passed = gap >= timedelta(minutes=MIN_GAP_MINUTES)
    if not passed:
        remaining = timedelta(minutes=MIN_GAP_MINUTES) - gap
        print(f"[low_cpu_runner] {channel}: {remaining} until next eligible run")
    return passed


def _run_channel(channel: str) -> bool:
    if _is_locked(channel):
        print(f"[low_cpu_runner] {channel}: already running, skip")
        return False
    if not _min_gap_passed(channel):
        return False

    pipeline_ref = CHANNEL_PIPELINES.get(channel)
    if not pipeline_ref:
        print(f"[low_cpu_runner] Unknown channel: {channel}")
        return False

    module_path, func_name = pipeline_ref.rsplit(":", 1)

    import importlib
    import importlib.util as ilu

    try:
        mod = importlib.import_module(module_path)
    except (ModuleNotFoundError, ImportError):
        # channels with hyphens: load directly from file
        channel_mod_file = REPO_ROOT / "channels" / channel / "harness" / "orchestrator.py"
        if not channel_mod_file.exists():
            print(f"[low_cpu_runner] {channel}: orchestrator not found at {channel_mod_file}")
            return False
        spec = ilu.spec_from_file_location("orchestrator", channel_mod_file)
        mod = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)

    fn = getattr(mod, func_name, None)
    if fn is None:
        print(f"[low_cpu_runner] {channel}: function {func_name} not found in module")
        return False

    _acquire_lock(channel)
    print(f"[low_cpu_runner] Starting {channel} pipeline...")
    try:
        result = fn()
        success = result.get("success", False)
        detail = result.get("video_url") or result.get("reason") or ""
        print(f"[low_cpu_runner] {channel}: {'✅ success' if success else '❌ failed'} — {detail}")
        _record_run(channel, success)
        return success
    except Exception as e:
        print(f"[low_cpu_runner] {channel}: exception — {e}")
        _record_run(channel, False)
        return False
    finally:
        _release_lock(channel)


def main():
    parser = argparse.ArgumentParser(description="Run video channel pipelines when CPU is idle")
    parser.add_argument("--channel", help="Channel slug to run")
    parser.add_argument("--all", action="store_true", help="Run all video channels")
    args = parser.parse_args()

    if not _is_cpu_idle():
        print("[low_cpu_runner] CPU busy — skipping this tick")
        sys.exit(0)

    channels = VIDEO_CHANNELS if args.all else ([args.channel] if args.channel else [])
    if not channels:
        print("[low_cpu_runner] No channel specified. Use --channel <slug> or --all")
        sys.exit(1)

    for ch in channels:
        _run_channel(ch)


if __name__ == "__main__":
    main()
