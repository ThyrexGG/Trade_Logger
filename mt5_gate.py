# -*- coding: utf-8 -*-
"""
MT5 terminal master switch — one place every module consults before it calls
``MetaTrader5.initialize()``.

``mt5.initialize()`` *launches* the MetaTrader 5 terminal if it is not already
open, and nothing in this codebase ever closes it. So a running API server plus
a polling browser tab (or the startup warm-up) will keep re-opening the
terminal on a machine where the user does not want it running.

This switch is persisted in ``app_settings`` (key ``market_data_live_enabled``)
and defaults to ON. When OFF, every read-side MT5 branch is skipped and the
existing fallbacks (Binance / Yahoo / cache / persisted DB rows) serve instead.

Read-only concern: this governs *where market/account data is read from*. It has
no effect on execution / broker transmission, which is permanently BLOCKED by
the frozen safety layer regardless of this flag.
"""
from __future__ import annotations

import time
from typing import Any, Dict

SETTING_KEY = "market_data_live_enabled"
_TTL_SEC = 3.0
_cache: Dict[str, Any] = {"value": True, "at": 0.0}


def is_mt5_enabled() -> bool:
    """True unless an operator has explicitly turned the live-MT5 switch off."""
    now = time.time()
    if now - _cache["at"] < _TTL_SEC:
        return bool(_cache["value"])
    val = True
    try:
        import database
        raw = database.get_setting(SETTING_KEY, "true")
        val = (raw or "true").strip().lower() != "false"
    except Exception:
        val = True
    _cache["value"] = val
    _cache["at"] = now
    return val


def set_mt5_enabled(enabled: bool) -> bool:
    """Persist the switch and refresh the in-process cache immediately."""
    import database
    database.set_setting(SETTING_KEY, "true" if enabled else "false")
    _cache["value"] = bool(enabled)
    _cache["at"] = time.time()
    return bool(enabled)
