# -*- coding: utf-8 -*-
"""
In-process broker-sync service.

Runs the same sync cycle as the standalone ``auto_sync.py`` daemon
(``auto_sync.run_sync_cycle`` — MT5 + Capital.com trade/position sync,
closed-trade push alerts, price-alert checks) but hosted inside the API
server so it can be driven from the website:

  * "Sync now" — one cycle on demand.
  * an on/off auto toggle — a background thread that runs a cycle every
    ``INTERVAL_SEC`` while the server is up.

While the auto loop is running it writes a heartbeat to
``app_settings["inprocess_sync_heartbeat"]``; the standalone daemon reads
that and stands down for those cycles, so the two never double-sync.

Data ingestion only. This module places / modifies / cancels no order,
enables no automation, and imports no execution / broker-adapter / risk
module. It only reads broker state and writes rows to the local journal DB.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import auto_sync
import database

INTERVAL_SEC = 30
_AUTO_SETTING_KEY = "sync_auto_enabled"
_HEARTBEAT_KEY = "inprocess_sync_heartbeat"

_lock = threading.Lock()          # guards a single running cycle
_state_lock = threading.Lock()    # guards the fields below
_thread: Optional[threading.Thread] = None
_stop = threading.Event()
_known_trade_ids: set = set()
_known_loaded = False
_last_run: Optional[Dict[str, Any]] = None
_running = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_known_ids() -> None:
    global _known_loaded
    if _known_loaded:
        return
    try:
        df = database.get_closed_trades()
        if df is not None and not df.empty:
            _known_trade_ids.update(df["trade_id"].tolist())
    except Exception:
        pass
    _known_loaded = True


def is_auto_enabled() -> bool:
    try:
        raw = database.get_setting(_AUTO_SETTING_KEY, "false")
        return (raw or "false").strip().lower() == "true"
    except Exception:
        return False


def run_once(source: str = "manual") -> Dict[str, Any]:
    """Run one sync cycle. Serialised — concurrent callers get the result of
    the run they waited on."""
    global _last_run, _running
    with _lock:
        with _state_lock:
            _running = True
        started = time.time()
        _load_known_ids()
        try:
            cycle = auto_sync.run_sync_cycle(_known_trade_ids, logfn=lambda _m: None)
            ok = not cycle["errors"]
        except Exception as e:  # noqa: BLE001
            cycle = {"errors": [str(e)], "mt5_ok": False, "capital_ok": False,
                     "new_closed_trades": 0}
            ok = False
        result = {
            "at": _now_iso(),
            "source": source,
            "ok": ok,
            "duration_sec": round(time.time() - started, 1),
            "mt5_ok": cycle.get("mt5_ok", False),
            "capital_ok": cycle.get("capital_ok", False),
            "new_closed_trades": cycle.get("new_closed_trades", 0),
            "errors": cycle.get("errors", []),
        }
        with _state_lock:
            _last_run = result
            _running = False
        try:
            database.set_setting(_HEARTBEAT_KEY, _now_iso())
        except Exception:
            pass
        return result


def _loop() -> None:
    while not _stop.is_set():
        if is_auto_enabled():
            try:
                run_once(source="auto")
            except Exception:
                pass
        _stop.wait(INTERVAL_SEC)


def _ensure_thread() -> None:
    global _thread
    with _state_lock:
        if _thread is not None and _thread.is_alive():
            return
        _stop.clear()
        _thread = threading.Thread(target=_loop, name="inprocess-sync", daemon=True)
        _thread.start()


def set_auto(enabled: bool) -> Dict[str, Any]:
    database.set_setting(_AUTO_SETTING_KEY, "true" if enabled else "false")
    if enabled:
        _ensure_thread()
    return status()


def start_if_enabled() -> None:
    """Called from the app lifespan — bring the loop up if the toggle was left on."""
    if is_auto_enabled():
        _ensure_thread()


def status() -> Dict[str, Any]:
    with _state_lock:
        thread_alive = _thread is not None and _thread.is_alive()
        return {
            "auto_enabled": is_auto_enabled(),
            "loop_running": thread_alive,
            "cycle_in_progress": _running,
            "interval_seconds": INTERVAL_SEC,
            "last_run": _last_run,
            "generated_at": _now_iso(),
        }
