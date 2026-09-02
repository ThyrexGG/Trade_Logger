# -*- coding: utf-8 -*-
"""
FastAPI Watchlist Router — Stage 2 Read-Only Watchlist Telemetry Endpoint
Consumes authoritative TradingWorkspaceCockpit.get_watchlist_data() without modification.
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Query
from api.schemas import WatchlistResponse, WatchlistItem
from trading_workspace_cockpit import TradingWorkspaceCockpit

router = APIRouter(prefix="/api", tags=["Watchlist"])


@router.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist(
    asset_class: str = Query(default="ALL", description="Asset class filter: ALL, COMMODITY, FOREX, INDEX, CRYPTO"),
    search: Optional[str] = Query(default="", description="Search symbol or name substring")
) -> WatchlistResponse:
    """
    Returns 10-field quantitative watchlist data directly from authoritative TradingWorkspaceCockpit engine.
    """
    raw_data = TradingWorkspaceCockpit.get_watchlist_data(
        asset_filter=asset_class.upper().strip(),
        search_query=search.strip() if search else ""
    )

    items = [WatchlistItem(**row) for row in raw_data]

    return WatchlistResponse(
        items=items,
        total_count=len(items),
        asset_filter=asset_class.upper().strip(),
        timestamp=datetime.now(timezone.utc).isoformat()
    )
