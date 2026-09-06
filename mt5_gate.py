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
from typing import Optional

_ENV_KEY = "MT5_ENABLED"

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
