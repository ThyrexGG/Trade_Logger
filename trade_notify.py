# -*- coding: utf-8 -*-
"""
Trade open/close events -> phone push (Expo) + a server-side event log the
desktop app polls.

Called from two places, both already running inside the user's tenant context:
  * ``database.save_open_positions`` -> ``record_opened`` for a position that was
    not in the previous broker snapshot.
  * ``auto_sync.run_sync_cycle``     -> ``record_closed`` for a newly seen closed trade.

Design rules:
  * Every event has a stable key (``opened:<position_id>`` / ``closed:<trade_id>``)
    and the log is UNIQUE per (user, key) — a re-sync, restart or retry can never
    fire the same notification twice.
  * Old trades never notify: a brand-new account's first sync sees months of
    history, so events older than a short window are skipped.
  * Nothing here may raise into a sync cycle, and pushing never blocks it (the
    HTTP call to Expo runs in a background thread).
  * Read-only with respect to trading: this only *reports* what the broker sync
    already saw. It can't place, modify or close anything.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

import database

log = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
_PUSH_TIMEOUT_SEC = 8

# A position is "newly opened" only if the broker says it opened this recently…
OPENED_MAX_AGE = timedelta(minutes=30)
# …and a closed trade only notifies if it closed this recently (history backfills stay silent).
CLOSED_MAX_AGE = timedelta(hours=6)


def push_enabled() -> bool:
    """Kill switch: TL_PUSH_ENABLED=0 stops sending pushes (events are still logged)."""
    return os.getenv("TL_PUSH_ENABLED", "1").strip().lower() not in ("0", "false", "no")


def _parse_ts(value: Any) -> Optional[datetime]:
    """Parse an ISO timestamp; a value with no zone is UTC (that is how the broker sync stores them)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("nan", "nat", "none"):
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _is_recent(value: Any, max_age: timedelta) -> bool:
    dt = _parse_ts(value)
    if dt is None:
        return False  # can't prove it is fresh -> stay silent rather than risk spamming history
    age = datetime.now(timezone.utc) - dt
    return timedelta(0) - timedelta(minutes=5) <= age <= max_age


def _num(value: Any) -> Optional[float]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # drop NaN


def _money(value: float) -> str:
    return f"{'+' if value >= 0 else '-'}${abs(value):,.2f}"


def _duration(minutes: Optional[float]) -> str:
    if minutes is None or minutes <= 0:
        return ""
    if minutes < 60:
        return f"{minutes:.0f}m"
    if minutes < 60 * 24:
        return f"{minutes / 60:.1f}h"
    return f"{minutes / 1440:.1f}d"


# --- event builders -----------------------------------------------------

def record_opened(pos: Dict[str, Any]) -> Optional[int]:
    """A position appeared in the broker snapshot. Returns the event id, or None if skipped/duplicate."""
    try:
        if not _is_recent(pos.get("open_time"), OPENED_MAX_AGE):
            return None
        pid = str(pos.get("position_id") or "")
        if not pid:
            return None
        symbol = str(pos.get("symbol") or "").upper()
        direction = str(pos.get("direction") or "").upper()
        volume = _num(pos.get("volume"))
        price = _num(pos.get("entry_price"))
        title = f"{symbol} {direction} opened".strip()
        parts = []
        if volume is not None:
            parts.append(f"{volume:g}")
        if price is not None:
            parts.append(f"@ {price:g}")
        body = " ".join(parts) or "New position"
        return _record(f"opened:{pid}", "opened", title, body, symbol, direction, volume, price, None, pid)
    except Exception:  # noqa: BLE001 - a notification must never break a sync
        log.exception("record_opened failed")
        return None


def record_closed(trade: Dict[str, Any]) -> Optional[int]:
    """A closed trade newly appeared. Returns the event id, or None if skipped/duplicate."""
    try:
        if not _is_recent(trade.get("exit_time"), CLOSED_MAX_AGE):
            return None
        tid = str(trade.get("trade_id") or "")
        if not tid:
            return None
        symbol = str(trade.get("symbol") or "").upper()
        direction = str(trade.get("direction") or "").upper()
        volume = _num(trade.get("volume"))
        price = _num(trade.get("exit_price"))
        pnl = _num(trade.get("net_profit")) or 0.0
        held = _duration(_num(trade.get("duration_minutes")))
        title = f"{symbol} closed {_money(pnl)}"
        parts = [direction]
        if volume is not None:
            parts.append(f"{volume:g}")
        if held:
            parts.append(f"· held {held}")
        body = " ".join(p for p in parts if p)
        return _record(f"closed:{tid}", "closed", title, body, symbol, direction, volume, price, pnl, tid)
    except Exception:  # noqa: BLE001
        log.exception("record_closed failed")
        return None


def record_price_alert(symbol: Any, price: Any, target: Any, condition: Any, alert_id: Any) -> Optional[int]:
    """A price alert crossed its target. Returns the event id, or None if skipped/duplicate."""
    try:
        aid = str(alert_id or "")
        if not aid:
            return None
        sym = str(symbol or "").upper()
        now_price = _num(price)
        tgt = _num(target)
        side = "above" if str(condition or "").upper() == "ABOVE" else "below"
        title = f"{sym} price alert"
        if now_price is not None and tgt is not None:
            body = f"{sym} is {now_price:g}, {side} your {tgt:g} target"
        else:
            body = f"{sym} crossed your target"
        return _record(f"alert:{aid}", "alert", title, body, sym, "", None, now_price, None, aid)
    except Exception:  # noqa: BLE001
        log.exception("record_price_alert failed")
        return None


def record_risk_alert(key: str, title: str, body: str, account: Any, pnl: Any = None) -> Optional[int]:
    """A loss limit (daily loss / drawdown) was approached or reached. `key` makes the event unique per
    account + limit + level + period, so it notifies once. Returns the event id, or None if duplicate."""
    try:
        acct = str(account or "")
        if not key or not acct:
            return None
        return _record(key, "risk", title, body, "", "", None, None, _num(pnl), acct)
    except Exception:  # noqa: BLE001
        log.exception("record_risk_alert failed")
        return None


def _record(key, kind, title, body, symbol, direction, volume, price, pnl, ref_id) -> Optional[int]:
    event_id = database.add_trade_event(
        key, kind, title, body, symbol=symbol, direction=direction,
        volume=volume, price=price, pnl=pnl, ref_id=ref_id,
    )
    if event_id is None:
        return None  # already recorded — never notify twice
    if push_enabled():
        devices = database.list_push_devices()
        tokens = [d["token"] for d in devices if d.get("token")]
        if tokens:
            data = {"kind": kind, "symbol": symbol, "ref_id": ref_id, "event_id": event_id}
            uid = _current_user_id()
            # Background thread: the sync cycle must not wait on Expo's servers.
            threading.Thread(
                target=send_pushes, args=(tokens, title, body, data, uid), daemon=True
            ).start()
    return event_id


def _current_user_id() -> str:
    import tenant
    return tenant.current_user_id()


# --- delivery -------------------------------------------------------------

def _messages(tokens: List[str], title: str, body: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "to": t, "title": title, "body": body, "data": data,
            "sound": "default", "priority": "high", "channelId": "trades",
        }
        for t in tokens
    ]


def send_pushes(tokens: List[str], title: str, body: str, data: Dict[str, Any],
                user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """POST to Expo's push service. Returns Expo's per-token tickets (empty on failure).
    Tokens Expo reports as DeviceNotRegistered (app uninstalled) are removed."""
    if not tokens:
        return []
    try:
        resp = requests.post(
            EXPO_PUSH_URL,
            json=_messages(tokens, title, body, data),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=_PUSH_TIMEOUT_SEC,
        )
        resp.raise_for_status()
        tickets = (resp.json() or {}).get("data") or []
    except Exception as exc:  # noqa: BLE001
        log.warning("Expo push failed: %s", exc)
        return []

    for token, ticket in zip(tokens, tickets):
        if not isinstance(ticket, dict) or ticket.get("status") == "ok":
            continue
        err = (ticket.get("details") or {}).get("error")
        if err == "DeviceNotRegistered":
            try:
                database.delete_push_device(token, user_id=user_id)
            except Exception:  # noqa: BLE001
                pass
        else:
            log.warning("Expo push ticket error for a device: %s", ticket.get("message") or err)
    return tickets


def send_test(user_devices: List[Dict[str, Any]], user_id: Optional[str] = None) -> Dict[str, Any]:
    """Synchronous test push for the Account screen's "Send test" button.
    Returns what Expo said so a misconfiguration (e.g. missing FCM credentials) is visible."""
    tokens = [d["token"] for d in user_devices if d.get("token")]
    if not tokens:
        return {"sent": 0, "tickets": [], "error": "No device is registered yet."}
    tickets = send_pushes(
        tokens, "TradeLogger test", "Push notifications are working.", {"kind": "test"}, user_id
    )
    ok = sum(1 for t in tickets if isinstance(t, dict) and t.get("status") == "ok")
    errors = [
        (t.get("message") or (t.get("details") or {}).get("error") or "error")
        for t in tickets if isinstance(t, dict) and t.get("status") != "ok"
    ]
    return {
        "sent": ok,
        "tickets": len(tickets),
        "error": "; ".join(errors) if errors else (None if tickets else "Expo did not respond."),
    }
