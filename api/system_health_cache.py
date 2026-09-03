# -*- coding: utf-8 -*-
"""
Short-TTL cache for the PAPER-mode system-health gate (Phase 62).

`system_health.evaluate_system_health` is authoritative but expensive: even with
the DB connection pool it performs a couple of sequential round-trips to the
cloud Postgres (`SELECT 1`, unresolved-UNKNOWN-orders count). Two read-only
surfaces call it on every request — `GET /api/operations/system` and the
`safety` section of `GET /api/command-center/overview` — so an un-cached call
adds ~250-500 ms to each.

This wrapper caches the *result dict* for a few seconds. It is intentionally
**not** placed inside `system_health.py`: any real execution-gating path must
keep calling the authoritative evaluator directly with no caching. This helper
is for the read-only status endpoints only, and only for `mode="PAPER"` (live
automation is permanently disabled).
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict

_LOCK = threading.Lock()
_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}
_DEFAULT_TTL = 8.0


def cached_paper_system_health(broker: str = "MT5", ttl: float = _DEFAULT_TTL) -> Dict[str, Any]:
    """Return `evaluate_system_health(broker, "PAPER")`, cached for `ttl` seconds.

    On any evaluation error the exception propagates to the caller (which already
    has its own defensive handling) and nothing is cached.
    """
    key = f"PAPER::{broker}"
    now = time.monotonic()
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and (now - hit[0]) < ttl:
            return hit[1]

    import system_health

    result = system_health.evaluate_system_health(broker=broker, mode="PAPER") or {}
    with _LOCK:
        _CACHE[key] = (time.monotonic(), result)
    return result


def invalidate() -> None:
    with _LOCK:
        _CACHE.clear()
