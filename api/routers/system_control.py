# -*- coding: utf-8 -*-
"""
FastAPI System Control Router — small operator toggles.

Currently one switch: whether market_data may touch the local MetaTrader 5
terminal for live quotes. When OFF, every MT5 branch in ``market_data`` is
skipped and the existing fallbacks (Binance / Yahoo / cache / default)
serve instead — so a running server + a polling browser tab can no longer
auto-relaunch the MT5 terminal.

Read-only with respect to trading: this governs only where quotes come
from. It has NO effect on execution or broker transmission, which are
permanently BLOCKED.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

import market_data

router = APIRouter(prefix="/api/system", tags=["System Control"])

_SAFETY = {"live_automation_enabled": False, "live_broker_transmission": "BLOCKED"}


class MarketDataToggle(BaseModel):
    enabled: bool


def _payload() -> Dict[str, Any]:
    return {
        "live_market_data_enabled": market_data.is_live_market_data_enabled(),
        "description": "When enabled, live quotes may come from the local MetaTrader 5 terminal "
                       "(which auto-launches it). When disabled, only Binance / Yahoo / cached data "
                       "is used and the terminal is never opened by the app.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "safety_barrier": _SAFETY,
    }


@router.get("/market-data")
def get_market_data_toggle() -> Dict[str, Any]:
    """Current state of the live-market-data (MT5) switch."""
    return _payload()


@router.put("/market-data")
def set_market_data_toggle(body: MarketDataToggle) -> Dict[str, Any]:
    """Enable or disable live MT5 market data. Persisted in app_settings."""
    market_data.set_live_market_data_enabled(bool(body.enabled))
    return _payload()
