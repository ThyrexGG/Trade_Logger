# -*- coding: utf-8 -*-
"""
FastAPI Market Router — Stage 2 Read-Only Market Snapshot Endpoint
Provides near-instant cached multi-timeframe bias, price, spread, and context
consuming authoritative TradingWorkspaceCockpit and market_data without modification.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from api.schemas import MarketSnapshotResponse
from trading_workspace_cockpit import TradingWorkspaceCockpit, WATCHLIST_SYMBOLS
import market_data

router = APIRouter(prefix="/api/market", tags=["Market"])


def _calculate_market_session(dt: datetime) -> str:
    """Calculates active global institutional market session from UTC time."""
    weekday = dt.weekday()
    hour = dt.hour

    if weekday >= 5:  # Saturday or Sunday
        return "WEEKEND CLOSED"
    elif 13 <= hour < 16:
        return "LONDON / NY OVERLAP"
    elif 8 <= hour < 16:
        return "LONDON SESSION"
    elif 13 <= hour < 21:
        return "NEW YORK SESSION"
    elif 0 <= hour < 8:
        return "TOKYO / ASIAN SESSION"
    else:
        return "PACIFIC / SYDNEY"


@router.get("/snapshot/{symbol}", response_model=MarketSnapshotResponse)
async def get_market_snapshot(symbol: str) -> MarketSnapshotResponse:
    """
    Returns near-instant cached Market Snapshot and multi-timeframe bias hierarchy.
    Directly queries single symbol without full universe iteration.
    """
    sym = symbol.upper().replace("/", "").replace(":", "").strip()
    now_utc = datetime.now(timezone.utc)

    # 1. Check if symbol exists in standard catalog or default fallback
    matched_meta = next((s for s in WATCHLIST_SYMBOLS if s["symbol"] == sym), None)
    display_name = matched_meta["display"] if matched_meta else sym

    # 2. Retrieve authoritative price, tick, and spread for single symbol
    price = market_data.get_latest_price(sym) or 0.0
    tick = market_data.get_latest_tick(sym) or {}
    bid = tick.get("bid", price)
    ask = tick.get("ask", price)
    spread = round(abs(ask - bid), 4) if (ask and bid) else 0.0

    # 3. Retrieve authoritative MTF bias hierarchy
    mtf_bias = TradingWorkspaceCockpit.get_mtf_bias_hierarchy(sym)

    # 4. Extract edge score, setup state, and data quality directly for this symbol
    ctx = TradingWorkspaceCockpit.get_symbol_context_metrics(sym)

    return MarketSnapshotResponse(
        symbol=sym,
        display=display_name,
        price=price,
        bid=bid,
        ask=ask,
        spread=spread,
        session=_calculate_market_session(now_utc),
        mtf_bias=mtf_bias,
        setup_state=ctx["setup_state"],
        edge_score=ctx["edge_score"],
        macro_score=ctx["macro_score"],
        data_quality=ctx["data_quality"],
        live_broker_transmission="BLOCKED",
        cached=True,
        timestamp=now_utc.isoformat()
    )
