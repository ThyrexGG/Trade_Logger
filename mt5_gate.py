# -*- coding: utf-8 -*-
"""
MT5 terminal master switch — one place every module consults before it calls
``MetaTrader5.initialize()``.

``mt5.initialize()`` *launches* the MetaTrader 5 terminal if it is not already
open, and nothing in this codebase ever closes it. The local MT5 terminals have
been uninstalled, so MT5 is now **off by default and opt-in via env only**:

    MT5_ENABLED=1     # in .env — the only way to re-enable the MT5 read paths

With MT5 disabled (the default), every read-side MT5 branch is skipped and the
fallbacks (Binance / Yahoo / cache / persisted DB rows) serve instead. There is
no UI toggle and no DB setting any more.

Read-only concern: this governs *where market/account data is read from*. It has
no effect on execution / broker transmission, which is permanently BLOCKED by
the frozen safety layer regardless of this flag.
"""
from __future__ import annotations

import os
import platform
import subprocess
import threading
import time
from typing import Any, Optional

_ENV_KEY = "MT5_ENABLED"
_NO_WINDOW = 0x08000000 if platform.system() == "Windows" else 0

# The MetaTrader5 python package wraps ONE connection per process -- calling
# initialize()/shutdown() from two threads at once (e.g. mt5_sync.py's sync
# loop and market_data.py's chart/tick polling, both running in the same API
# process) can silently break whichever call loses the race. Every module
# that touches the `mt5` module directly must hold this for its whole session
# (from initialize through shutdown), not just around the initialize call.
# Reentrant so a caller that already holds it (mt5_sync.py wrapping its own
# session) can still call guarded_initialize() without deadlocking itself.
LOCK = threading.RLock()

# Deliberate in-process override (tests, or a runtime opt-in). None -> read env.
_override: Optional[bool] = None


def is_mt5_enabled() -> bool:
    """False unless ``MT5_ENABLED`` is set truthy in the environment (or an
    explicit in-process override is in effect)."""
    if _override is not None:
        return _override
    return (os.getenv(_ENV_KEY) or "").strip().lower() in ("1", "true", "yes", "on")


def set_mt5_enabled(enabled: bool) -> bool:
    """Runtime in-process override, kept for backward-compatible callers/tests.
    Nothing is persisted. Prefer ``MT5_ENABLED`` in .env."""
    global _override
    _override = bool(enabled)
    return _override


def clear_override() -> None:
    """Drop the in-process override so the env var decides again."""
    global _override
    _override = None


def _mt5_pids() -> set:
    """PIDs of any running MT5 terminal process (empty set if none, or this
    couldn't be checked). Matches MetaQuotes' real binary names, which every
    white-labelled/broker-branded build still ships under the hood."""
    if platform.system() != "Windows":
        return set()
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=10,
            creationflags=_NO_WINDOW,
        ).stdout
    except Exception:
        return set()
    pids: set = set()
    for line in out.splitlines():
        line = line.strip()
        if not (line.startswith('"') and line.endswith('"')):
            continue
        parts = line[1:-1].split('","')
        if len(parts) >= 2 and parts[0].lower() in ("terminal64.exe", "terminal.exe"):
            try:
                pids.add(int(parts[1]))
            except ValueError:
                pass
    return pids


def mt5_terminal_running() -> bool:
    """True only if an MT5 terminal process is already running on this machine.

    A background/automatic read (a chart poll, an account-state refresh) must
    never be the reason MetaTrader pops open -- calling ``mt5.initialize()``
    launches a brand-new terminal window if none is running, and nothing
    closes it again, so a frequent poll against a terminal the user closed
    would keep relaunching it in their face. Callers on a passive read path
    should check this FIRST and skip MT5 entirely (falling back to whatever
    else they'd use) instead of calling ``mt5.initialize()`` when it's False.
    A genuine user-triggered action (an explicit "Sync now", the setup
    wizard) is not passive and may still launch it -- use
    ``guarded_initialize`` there so the new window gets minimized instantly
    instead of sitting in the user's face."""
    return bool(_mt5_pids())


def _minimize_windows_for_pids(pids: set) -> None:
    """Best-effort: minimize (never close) any visible window belonging to
    one of these process ids. Only ever called with PIDs WE just launched --
    a terminal the user already had open is never touched."""
    if not pids:
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_MINIMIZE = 6

        def _pid_of(hwnd) -> int:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            return pid.value

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd, _lparam):
            if user32.IsWindowVisible(hwnd) and _pid_of(hwnd) in pids:
                user32.ShowWindow(hwnd, SW_MINIMIZE)
            return True

        user32.EnumWindows(_enum, 0)
    except Exception:
        pass  # cosmetic only -- never let this get in the way of a connect


def _watch_and_minimize_new_terminal(before_pids: set, stop: threading.Event) -> None:
    deadline = time.time() + 25
    while not stop.is_set() and time.time() < deadline:
        pids = _mt5_pids()
        if pids:
            new = pids - before_pids
            if new:
                _minimize_windows_for_pids(new)
        stop.wait(0.3)


_server_utc_offset_sec = 0
_server_utc_offset_checked_at = 0.0


def server_utc_offset_sec(mt5_module: Any) -> int:
    """``broker_server_time - real_UTC``, seconds, rounded to the nearest hour
    and cached 30 min.

    MT5's ``.time`` fields on a tick / position / deal are the BROKER
    SERVER's wall clock, epoch-encoded as if it were UTC — not real UTC.
    Every module that reads a raw MT5 timestamp and stores or displays it
    must subtract this offset first (``real_utc = mt5_time - offset``), or a
    trade that actually closed late one day can get bucketed under the next
    (see 5c22ba9, which fixed this for the standalone push-agent; mt5_sync.py
    had the identical bug via a second, separate MT5 read path that fix never
    touched). ``agent/mt5_push_agent.py`` keeps its own copy of this same
    logic — it's a separately distributed script that can't import this
    module — so a change here must be mirrored there by hand."""
    global _server_utc_offset_sec, _server_utc_offset_checked_at
    now = time.time()
    if _server_utc_offset_checked_at and now - _server_utc_offset_checked_at < 1800:
        return _server_utc_offset_sec
    try:
        mt5_module.symbol_select("EURUSD", True)
        tick = mt5_module.symbol_info_tick("EURUSD") or mt5_module.symbol_info_tick("XAUUSD")
        if tick and tick.time:
            raw = tick.time - now
            _server_utc_offset_sec = int(round(raw / 3600.0) * 3600)
            _server_utc_offset_checked_at = now
    except Exception:
        pass
    return _server_utc_offset_sec


def guarded_initialize(mt5_module: Any, **initialize_kwargs: Any) -> bool:
    """``mt5_module.initialize(**initialize_kwargs)``, but if that has to
    cold-launch a fresh terminal (none was already running), minimize the new
    window the instant it appears instead of leaving it to flash in front of
    whatever the user is doing for however long the cold start takes. A
    terminal the user already had open is never touched. Use this for any
    deliberate connect (a manual sync, the setup wizard) -- for a passive
    background read, prefer ``mt5_terminal_running()`` and skip entirely.

    Acquires ``LOCK`` for the duration of the call (reentrant, so a caller
    that already holds it -- e.g. mt5_sync.py wrapping its whole session --
    can call this without deadlocking). A caller that does anything with
    ``mt5_module`` AFTER this returns (read account info, shut down, ...)
    must hold ``LOCK`` itself across that too -- this function can't do that
    for you once it has returned."""
    with LOCK:
        before_pids = _mt5_pids()
        stop = threading.Event()
        watcher = threading.Thread(
            target=_watch_and_minimize_new_terminal, args=(before_pids, stop), daemon=True,
        )
        if platform.system() == "Windows":
            watcher.start()
        try:
            ok = bool(mt5_module.initialize(**initialize_kwargs))
        finally:
            stop.set()
            if platform.system() == "Windows":
                watcher.join(timeout=2)
        after_pids = _mt5_pids()
        if after_pids:
            _minimize_windows_for_pids(after_pids - before_pids)
        return ok
