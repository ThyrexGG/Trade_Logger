# -*- coding: utf-8 -*-
"""In-process AI-assistant usage meter.

Tracks token + request counts for the current UTC day and since process start —
just enough for the header "usage" indicator. Not persisted; a restart resets
the counters. Read-only, no bearing on execution.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict

_LOCK = threading.Lock()
_STATE: Dict[str, Any] = {
    "day": "",              # UTC date the day-counters belong to
    "day_requests": 0,
    "day_tokens": 0,
    "session_requests": 0,
    "session_tokens": 0,
    "last_request_utc": None,
}


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _roll_day_locked() -> None:
    today = _today()
    if _STATE["day"] != today:
        _STATE["day"] = today
        _STATE["day_requests"] = 0
        _STATE["day_tokens"] = 0


def record(total_tokens: int) -> None:
    """Log one completed assistant reply."""
    with _LOCK:
        _roll_day_locked()
        t = max(0, int(total_tokens or 0))
        _STATE["day_requests"] += 1
        _STATE["day_tokens"] += t
        _STATE["session_requests"] += 1
        _STATE["session_tokens"] += t
        _STATE["last_request_utc"] = datetime.now(timezone.utc).isoformat()


def snapshot() -> Dict[str, Any]:
    with _LOCK:
        _roll_day_locked()
        return {
            "day": _STATE["day"],
            "day_requests": _STATE["day_requests"],
            "day_tokens": _STATE["day_tokens"],
            "session_requests": _STATE["session_requests"],
            "session_tokens": _STATE["session_tokens"],
            "last_request_utc": _STATE["last_request_utc"],
        }
