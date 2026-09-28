# -*- coding: utf-8 -*-
"""
Killzone Scanner push alerts: an opt-in, per-user list of watched symbols.
When a scan turns up a candidate that meets the user's own confluence
threshold AND happened recently (not backlog), one push notification goes
out — the same assistive, never-a-signal posture as the scanner page itself
(see killzone_scanner.py's module docstring: pattern-flagging only, no
recommendation, no execution path). Off by default; nothing is watched and
nothing is ever sent until the user explicitly saves a config.

Piggybacks on the existing per-user alert loop (api/sync_service.py's
`_check_alerts_for`, alongside price alerts / loss limits / the weekly
summary) instead of starting a loop of its own. That loop already runs for
exactly the users who could receive a push (anyone with a registered
device — a prerequisite for a push to go anywhere), so this adds no new
trigger to when the loop runs at all, which matters: see sync_service.py's
own docstring on why an unconditional new trigger there would reopen the
2026-09 Neon compute-hour incident.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import database
import tenant

log = logging.getLogger(__name__)

SETTING_KEY = "killzone_watch_config"
DEFAULT_MIN_CONFLUENCE = 4
MAX_WATCHED_SYMBOLS = 10  # each is its own live candle fetch + structure calc every cycle — kept bounded
# A candidate older than this when first seen is backlog from before the user configured
# alerts (or the app was offline a while), not something that "just happened" — stay silent
# on it, the same discipline trade_notify.py's other record_* functions already apply.
CANDIDATE_STALE_AFTER_SEC = 2 * 3600


def get_config(user_id: Optional[str] = None) -> Dict[str, Any]:
    """{"symbols": [...], "min_confluence": int, "enabled": bool}. Empty and
    disabled until the user explicitly saves one."""
    try:
        raw = database.get_user_setting(SETTING_KEY, "", user_id=user_id)
        if not raw:
            return {"symbols": [], "min_confluence": DEFAULT_MIN_CONFLUENCE, "enabled": False}
        data = json.loads(raw)
        symbols = [str(s).strip().upper() for s in (data.get("symbols") or []) if str(s).strip()]
        return {
            "symbols": symbols[:MAX_WATCHED_SYMBOLS],
            "min_confluence": max(0, min(5, int(data.get("min_confluence", DEFAULT_MIN_CONFLUENCE)))),
            "enabled": bool(data.get("enabled", False)),
        }
    except Exception:
        return {"symbols": [], "min_confluence": DEFAULT_MIN_CONFLUENCE, "enabled": False}


def set_config(symbols: List[str], min_confluence: int, enabled: bool,
                user_id: Optional[str] = None) -> Dict[str, Any]:
    cleaned = [str(s).strip().upper() for s in (symbols or []) if str(s).strip()][:MAX_WATCHED_SYMBOLS]
    payload = {
        "symbols": cleaned,
        "min_confluence": max(0, min(5, int(min_confluence))),
        "enabled": bool(enabled) and bool(cleaned),  # enabling with nothing to watch is a no-op, store it as off
    }
    database.set_user_setting(SETTING_KEY, json.dumps(payload), user_id=user_id)
    return payload


def check(logfn=None) -> int:
    """One pass for the current tenant: scan each watched symbol, push for any
    candidate meeting their confluence bar that happened within
    CANDIDATE_STALE_AFTER_SEC. Returns how many pushes were recorded. A no-op
    (no scan, no network call) for the common case of a user who never
    configured this."""
    logfn = logfn or (lambda _m: None)
    cfg = get_config(tenant.current_user_id())
    if not cfg["enabled"] or not cfg["symbols"]:
        return 0

    import killzone_scanner
    import trade_notify

    now = datetime.now(timezone.utc).timestamp()
    sent = 0
    for sym in cfg["symbols"]:
        try:
            result = killzone_scanner.scan(sym, ltf="15m", htf="1h")
        except Exception:
            continue
        if not result.get("ok"):
            continue
        for c in result.get("candidates", []):
            age = now - float(c.get("shift_time") or 0)
            if age > CANDIDATE_STALE_AFTER_SEC:
                break  # candidates are sorted most-recent-first: everything after this is older still
            if age < 0 or c.get("confluence_score", 0) < cfg["min_confluence"]:
                continue
            event_id = trade_notify.record_killzone_candidate(sym, c)
            if event_id is not None:
                sent += 1
                logfn(f"Killzone alert sent: {sym} {c.get('direction')} {c.get('confluence_score')}/5")
    return sent
