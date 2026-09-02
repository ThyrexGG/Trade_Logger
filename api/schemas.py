# -*- coding: utf-8 -*-
"""
TradeLogger FastAPI Pydantic Response & Request Schemas (Stage 2 Read-Only Vertical Slice)
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


# -------------------------------------------------------------------------
# Health Schemas
# -------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = Field(default="HEALTHY", description="Service health state")
    app_name: str = Field(default="TradeLogger Fast Terminal API")
    version: str = Field(default="2.0.0")
    live_broker_transmission: str = Field(default="BLOCKED", description="Safety gate state")
    automation_enabled: bool = Field(default=False, description="Live automation safety flag")
    timestamp: str = Field(description="ISO UTC Timestamp")


# -------------------------------------------------------------------------
# Watchlist Schemas
# -------------------------------------------------------------------------
class WatchlistItem(BaseModel):
    symbol: str
    display: str
    name: str
    asset_class: str
    price: float
    spread: float
    bias_4h: str
    bias_15m: str
    setup_state: str
    edge_score: float
    macro_score: float
    agreement_pct: float
    data_quality: int
    mode: str = "PAPER"


class WatchlistResponse(BaseModel):
    items: List[WatchlistItem]
    total_count: int
    asset_filter: str = "ALL"
    timestamp: str


# -------------------------------------------------------------------------
# Market Snapshot Schemas
# -------------------------------------------------------------------------
class MTFBiasHierarchy(BaseModel):
    tf_1d: str = Field(alias="1D", default="NEUTRAL")
    tf_4h: str = Field(alias="4H", default="NEUTRAL")
    tf_1h: str = Field(alias="1H", default="NEUTRAL")
    tf_15m: str = Field(alias="15M", default="NEUTRAL")
    tf_5m: str = Field(alias="5M", default="NEUTRAL")
    tf_1m: str = Field(alias="1M", default="STANDBY")

    model_config = {
        "populate_by_name": True
    }


class MarketSnapshotResponse(BaseModel):
    symbol: str
    display: str
    price: float
    bid: float
    ask: float
    spread: float
    session: str
    mtf_bias: Dict[str, str]
    setup_state: str
    edge_score: float
    macro_score: float
    data_quality: int
    live_broker_transmission: str = "BLOCKED"
    cached: bool = True
    timestamp: str
