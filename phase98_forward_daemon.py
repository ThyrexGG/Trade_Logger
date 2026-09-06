# -*- coding: utf-8 -*-
"""
Phase 98 Forward-Evidence Daemon.

Automates the weekly run of the funding-carry forward-evidence harness
(``phase98_carry_forward_evidence``). It is a thin scheduler wrapper --
NO strategy logic, NO execution, NO orders. It only decides *when* to call
the harness and logs the outcome.

Two modes:

  --once   Run the harness once IF it is due (>= 7 days since the last
           snapshot, or no snapshot yet), then exit. Intended for a daily
           OS scheduler trigger (Windows Task Scheduler / cron) -- the
           daily trigger fires, this script decides whether the weekly run
           is actually due. Robust to missed days, sleeping laptops, etc.

  --loop   Run forever, checking every few hours and running the harness
           whenever it becomes due. Intended for "leave it running" use
           (a terminal, or the Windows startup folder via pythonw).

Every run passes --refresh to the harness so recent crypto data is
re-ingested first. All output is appended to phase98_daemon_log.txt.
Exceptions are caught and logged, never raised past the loop.

Register it as a weekly Windows task with:
    powershell -ExecutionPolicy Bypass -File register_phase98_weekly.ps1
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_LOG = os.path.join(_HERE, "phase98_daemon_log.txt")
_DUE_AFTER_DAYS = 7
_LOOP_CHECK_HOURS = 6


def _log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}"
    print(line, flush=True)
    try:
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _last_snapshot_age_days() -> float | None:
    """Days since the most recent forward snapshot, or None if there is
    none yet (also None if the store cannot be read -- treat as 'due')."""
    try:
        import phase98_carry_forward_evidence as p98
        res = p98.get_result()
        hist = (res or {}).get("snapshot_history") or []
        if not hist:
            return None
        last = hist[-1].get("captured_at")
        if not last:
            return None
        ts = datetime.fromisoformat(last)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0
    except Exception as e:  # pragma: no cover
        _log(f"could not read last snapshot age ({e!r}); treating as due")
        return None


def is_due() -> bool:
    age = _last_snapshot_age_days()
    if age is None:
        return True
    return age >= _DUE_AFTER_DAYS


def run_harness() -> int:
    """Invoke the harness in a child process (isolation: a hang or crash
    cannot take down a --loop daemon). Returns the child exit code."""
    cmd = [sys.executable, "-m", "phase98_carry_forward_evidence", "--refresh"]
    _log(f"running: {' '.join(cmd)}")
    try:
        p = subprocess.run(cmd, cwd=_HERE, capture_output=True, text=True, timeout=1800)
    except subprocess.TimeoutExpired:
        _log("harness TIMED OUT after 1800s")
        return 124
    tail = "\n".join((p.stdout or "").strip().splitlines()[-12:])
    _log(f"harness exit {p.returncode}\n{tail}")
    if p.returncode != 0 and p.stderr:
        _log("stderr tail:\n" + "\n".join(p.stderr.strip().splitlines()[-8:]))
    return p.returncode


def run_once(force: bool = False) -> int:
    if force or is_due():
        age = _last_snapshot_age_days()
        _log(f"due (last snapshot {age if age is None else round(age, 1)} days ago){' [forced]' if force else ''}")
        return run_harness()
    age = _last_snapshot_age_days()
    _log(f"not due yet (last snapshot {round(age, 1)} days ago; runs every {_DUE_AFTER_DAYS})")
    return 0


def run_loop() -> int:
    _log(f"daemon loop started (check every {_LOOP_CHECK_HOURS}h, run every {_DUE_AFTER_DAYS}d)")
    while True:
        try:
            run_once()
        except Exception as e:  # pragma: no cover
            _log(f"loop iteration error: {e!r}")
        time.sleep(_LOOP_CHECK_HOURS * 3600)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Phase 98 forward-evidence daemon (scheduler wrapper only)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true", help="run once if due, then exit (for an OS scheduler)")
    g.add_argument("--loop", action="store_true", help="run forever, checking periodically")
    ap.add_argument("--force", action="store_true", help="with --once: run even if not due")
    ap.add_argument("--status", action="store_true", help="print whether a run is due and exit")
    args = ap.parse_args(argv)

    if args.status:
        age = _last_snapshot_age_days()
        print(f"last snapshot: {'none' if age is None else str(round(age, 1)) + ' days ago'}")
        print(f"due now: {is_due()}")
        return 0
    if args.loop:
        return run_loop()
    return run_once(force=args.force)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
