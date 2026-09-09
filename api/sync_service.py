# -*- coding: utf-8 -*-
"""
In-process broker-sync service.

Runs the same sync cycle as the standalone ``auto_sync.py`` daemon
(``auto_sync.run_sync_cycle`` — MT5 + Capital.com trade/position sync,
closed-trade push alerts, price-alert checks) but hosted inside the API
server so it can be driven from the website:

  * "Sync now" — one cycle on demand, for the calling user.
  * an on/off auto toggle — a background thread that, while any user has it
    on, runs a cycle for each of them every ``INTERVAL_SEC``.

**Multi-user (W8.6).** A cycle is always bound to one tenant:

  * a user with saved broker connections (``broker_connections``) → one cycle
    per active connection, using that connection's decrypted credentials, with
    ``tenant`` bound so the rows land under that user.
  * the owner / single-user "local" tenant with no saved connection → the
    Capital.com ``CAPITAL_*`` environment credentials, exactly as before.

The heartbeat (``user_settings["inprocess_sync_heartbeat"]``) and the auto
toggle (``user_settings["sync_auto_enabled"]``) are per-user.

Data ingestion only. This module places / modifies / cancels no order,
enables no automation, and imports no execution / broker-adapter / risk
module. It only reads broker state and writes rows to the local journal DB.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import auto_sync
import database
import tenant

try:
    INTERVAL_SEC = max(15, int(os.getenv("TL_SYNC_INTERVAL_SEC", "120")))
except (TypeError, ValueError):
    INTERVAL_SEC = 120

_AUTO_SETTING_KEY = "sync_auto_enabled"
_HEARTBEAT_KEY = "inprocess_sync_heartbeat"

_lock = threading.Lock()          # guards a single running cycle
_state_lock = threading.Lock()    # guards the fields below
_thread: Optional[threading.Thread] = None
_stop = threading.Event()
_known_by_user: Dict[str, set] = {}
_last_run: Optional[Dict[str, Any]] = None
_running = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- per-user settings ------------------------------------------------

def is_auto_enabled(user_id: Optional[str] = None) -> bool:
    try:
        raw = database.get_user_setting(_AUTO_SETTING_KEY, "false", user_id=user_id)
        return (raw or "false").strip().lower() == "true"
    except Exception:
        return False


def _any_auto_enabled() -> bool:
    try:
        for uid in _auto_enabled_user_ids():
            return True
    except Exception:
        pass
    return is_auto_enabled(tenant.LOCAL_USER_ID)


def _auto_enabled_user_ids() -> List[str]:
    try:
        return database.user_ids_with_setting(_AUTO_SETTING_KEY, "true")
    except Exception:
        return []


def _heartbeat_age_sec(user_id: Optional[str] = None) -> Optional[float]:
    try:
        raw = database.get_user_setting(_HEARTBEAT_KEY, "", user_id=user_id)
        if not raw:
            return None
        ts = datetime.fromisoformat(raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except Exception:
        return None


# --- credential resolution -----------------------------------------

def _connections_for(user_id: str) -> List[Dict[str, Any]]:
    """List of ``{"id", "creds"}`` for a user's active broker connections.
    Empty when encryption is off or the user has none."""
    try:
        from api import broker_credentials as bc
        if not bc.enc_enabled():
            return []
        out = []
        for meta in bc.list_connections(user_id=user_id):
            if not meta.get("is_active"):
                continue
            try:
                out.append({"id": meta["id"], "creds": bc.get_secret(meta["id"], user_id=user_id)})
            except Exception:
                pass
        return out
    except Exception:
        return []


# --- one cycle -----------------------------------------------------

def _run_cycle(user_id: str, creds: Optional[Dict[str, Any]], source: str) -> Dict[str, Any]:
    """One sync cycle for one tenant / one credential set. Serialised."""
    global _last_run, _running
    with _lock:
        with _state_lock:
            _running = True
        started = time.time()
        known = _known_by_user.setdefault(user_id, set())
        if not known:
            try:
                with tenant.use(user_id):
                    df = database.get_closed_trades()
                if df is not None and not df.empty:
                    known.update(df["trade_id"].tolist())
            except Exception:
                pass
        try:
            with tenant.use(user_id):
                cycle = auto_sync.run_sync_cycle(known, logfn=lambda _m: None, creds=creds)
            ok = not cycle["errors"]
        except Exception as e:  # noqa: BLE001
            cycle = {"errors": [str(e)], "mt5_ok": False, "capital_ok": False, "new_closed_trades": 0}
            ok = False
        result = {
            "at": _now_iso(), "source": source, "user_id": user_id, "ok": ok,
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
            database.set_user_setting(_HEARTBEAT_KEY, _now_iso(), user_id=user_id)
        except Exception:
            pass
        return result


def run_for_user(user_id: Optional[str] = None, source: str = "manual") -> Dict[str, Any]:
    """Sync every active connection for ``user_id`` (default: the current
    tenant). Falls back to the ``CAPITAL_*`` env credentials for the local /
    owner tenant with no saved connection."""
    uid = tenant.resolve(user_id)
    conns = _connections_for(uid)
    if conns:
        results = [_run_cycle(uid, c["creds"], source) for c in conns]
        return {
            "ran": results if len(results) > 1 else results[0],
            "connections": len(results),
        }
    # no saved connection: env-credential path (owner / single-user only)
    if uid == tenant.LOCAL_USER_ID:
        return {"ran": _run_cycle(uid, None, source), "connections": 0}
    return {"skipped": True, "reason": "no_connection", "user_id": uid}


# Back-compat alias — older callers / tests use run_once().
def run_once(source: str = "manual", user_id: Optional[str] = None) -> Dict[str, Any]:
    out = run_for_user(user_id, source)
    ran = out.get("ran")
    if isinstance(ran, list):
        return ran[-1] if ran else {"ok": False, "errors": ["no cycle"]}
    return ran if ran is not None else {"ok": False, "errors": [out.get("reason", "skipped")]}


def run_if_stale(max_age_sec: int = 900, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Run a cycle for ``user_id`` only if their last sync is older than
    ``max_age_sec``. Deduplicated per user via the persisted heartbeat."""
    uid = tenant.resolve(user_id)
    if is_auto_enabled(uid):
        return {"skipped": True, "reason": "auto_loop_on", "heartbeat_age_sec": _heartbeat_age_sec(uid)}
    with _state_lock:
        if _running:
            return {"skipped": True, "reason": "in_progress", "heartbeat_age_sec": _heartbeat_age_sec(uid)}
    age = _heartbeat_age_sec(uid)
    if age is not None and age < max_age_sec:
        return {"skipped": True, "reason": "fresh", "heartbeat_age_sec": round(age, 1)}
    out = run_for_user(uid, source="open")
    out["heartbeat_age_sec_before"] = round(age, 1) if age is not None else None
    return out


# --- auto loop ---------------------------------------------------

def _loop() -> None:
    while not _stop.is_set():
        try:
            uids = set(_auto_enabled_user_ids())
            if is_auto_enabled(tenant.LOCAL_USER_ID):
                uids.add(tenant.LOCAL_USER_ID)
            for uid in sorted(uids):
                if _stop.is_set():
                    break
                try:
                    run_for_user(uid, source="auto")
                except Exception:
                    pass
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


def set_auto(enabled: bool, user_id: Optional[str] = None) -> Dict[str, Any]:
    database.set_user_setting(_AUTO_SETTING_KEY, "true" if enabled else "false", user_id=user_id)
    if enabled:
        _ensure_thread()
    return status(user_id=user_id)


def start_if_enabled() -> None:
    """Called from the app lifespan — bring the loop up if anyone left it on."""
    if _any_auto_enabled():
        _ensure_thread()


def status(user_id: Optional[str] = None) -> Dict[str, Any]:
    with _state_lock:
        thread_alive = _thread is not None and _thread.is_alive()
        return {
            "auto_enabled": is_auto_enabled(user_id),
            "loop_running": thread_alive,
            "cycle_in_progress": _running,
            "interval_seconds": INTERVAL_SEC,
            "last_run": _last_run,
            "generated_at": _now_iso(),
        }
