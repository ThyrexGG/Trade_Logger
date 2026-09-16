# -*- coding: utf-8 -*-
"""In-process AI-assistant usage meter.

Tracks token + request counts for the current UTC day and since process start —
just enough for the header "usage" indicator. Not persisted; a restart resets
the counters. Read-only, no bearing on execution.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _daily_budget() -> int:
    """A soft daily message budget just so the meter has something to fill
    against. Gemini's real free-tier limits vary by model; override with
    AI_DAILY_MESSAGE_BUDGET."""
    try:
        return max(1, int(os.getenv("AI_DAILY_MESSAGE_BUDGET", "200") or "200"))
    except (TypeError, ValueError):
        return 200


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
            "day_budget": _daily_budget(),
            "session_requests": _STATE["session_requests"],
            "session_tokens": _STATE["session_tokens"],
            "last_request_utc": _STATE["last_request_utc"],
        }


# --- per-user rate limiting ---------------------------------------------
# The friends-tier restriction that used to keep AI features owner-only was
# lifted 2026-09-16 -- every signed-in user can now call the Gemini-backed
# endpoints, and each call costs real money. This is a simple per-user
# sliding-window cap so one account can't exhaust the shared quota or run up
# an unbounded bill; it is deliberately per-user (tenant id), not per-IP, so
# it can't be defeated by NAT/shared-IP false positives and correctly
# attributes cost to the actual account making the calls.
_RATE_LOCK = threading.Lock()
_RATE_HITS: Dict[str, List[float]] = {}


def _hourly_limit() -> int:
    try:
        return max(1, int(os.getenv("AI_HOURLY_REQUEST_LIMIT", "20") or "20"))
    except (TypeError, ValueError):
        return 20


def rate_limited_for(user_id: str) -> Optional[int]:
    """Seconds the caller must wait, or None if they may make a request."""
    window = 3600.0
    now = time.time()
    with _RATE_LOCK:
        hits = [t for t in _RATE_HITS.get(user_id, []) if now - t < window]
        _RATE_HITS[user_id] = hits
        if len(hits) >= _hourly_limit():
            return int(window - (now - hits[0])) + 1
    return None


def record_request(user_id: str) -> None:
    with _RATE_LOCK:
        _RATE_HITS.setdefault(user_id, []).append(time.time())
