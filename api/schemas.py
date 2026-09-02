# -*- coding: utf-8 -*-
"""
TradeLogger FastAPI Pydantic Response & Request Schemas
Stage 2 & Stage 3 Read-Only Vertical Slice Models
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


# -------------------------------------------------------------------------
# 1. Health Schemas
# -------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = Field(default="HEALTHY", description="Service health state")
    app_name: str = Field(default="TradeLogger Fast Terminal API")
    version: str = Field(default="2.0.0")
    live_broker_transmission: str = Field(default="BLOCKED", description="Safety gate state")
    automation_enabled: bool = Field(default=False, description="Live automation safety flag")
    timestamp: str = Field(description="ISO UTC Timestamp")


# -------------------------------------------------------------------------
# 2. Watchlist Schemas
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
# 3. Market Snapshot Schemas
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


# -------------------------------------------------------------------------
# 4. User Preferences Schemas (Stage 3)
# -------------------------------------------------------------------------
class UserPreferencesModel(BaseModel):
    selected_asset: str = "XAUUSD"
    selected_timeframe: str = "15m"
    active_workspace_layout: str = "DEFAULT"
    watchlist_filter: str = "ALL"
    compact_mode: bool = False
    shortcuts_enabled: bool = True
    last_active_zone: str = "TRADING WORKSPACE"
    last_active_subtab: str = "CHARTS & WORKSPACE"


class UserPreferencesUpdateRequest(BaseModel):
    selected_asset: Optional[str] = None
    selected_timeframe: Optional[str] = None
    active_workspace_layout: Optional[str] = None
    watchlist_filter: Optional[str] = None
    compact_mode: Optional[bool] = None
    shortcuts_enabled: Optional[bool] = None
    last_active_zone: Optional[str] = None
    last_active_subtab: Optional[str] = None


class UserPreferencesResponse(BaseModel):
    preferences: UserPreferencesModel
    updated_at: str


# -------------------------------------------------------------------------
# 5. Market Intelligence Schemas (Stage 3)
# -------------------------------------------------------------------------
class IntelligenceSummaryResponse(BaseModel):
    primary_regime: str
    secondary_regime: str = "NEUTRAL"
    regime_confidence_pct: float
    breadth_bullish_pct: float
    breadth_bearish_pct: float
    breadth_neutral_pct: float
    strongest_asset: str
    weakest_asset: str
    usd_strength_score: float
    usd_strength_state: str
    overall_data_quality: int
    quality_rating: str
    live_broker_transmission: str = "BLOCKED"
    timestamp: str


class OpportunityMapItem(BaseModel):
    symbol: str
    asset_class: str
    edge_score: float
    macro_score: float
    agreement_pct: float
    data_quality_score: int
    context_state: str
    dominant_driver: str
    conflict_state: str
    ranking_eligible: bool


class OpportunityMapResponse(BaseModel):
    total_assets: int
    ranked_assets: List[OpportunityMapItem]
    timestamp: str


class AssetProfileResponse(BaseModel):
    symbol: str
    overall_edge_score: float
    macro_context_score: float
    technical_score: float
    positioning_score: float
    data_quality_score: int
    factor_agreement_pct: float
    context_state: str
    dominant_drivers: List[str]
    conflicts: List[str]
    recent_surprises: List[Dict[str, Any]]
    cot_sentiment: Dict[str, Any]
    timestamp: str


class HeatmapCell(BaseModel):
    value: Optional[float] = None
    badge_label: str
    state_color: str
    freshness: str


class EconomyHeatmapRow(BaseModel):
    economy_code: str
    country_name: str
    flag: str
    growth: Dict[str, Any]
    inflation: Dict[str, Any]
    labor: Dict[str, Any]
    rates: Dict[str, Any]
    surprise: Dict[str, Any]


class EconomicHeatmapResponse(BaseModel):
    matrix: List[EconomyHeatmapRow]
    total_economies: int
    timestamp: str


# -------------------------------------------------------------------------
# 6. Risk Gateway Schemas (Stage 3 Calculation-Only)
# -------------------------------------------------------------------------
class RiskPreviewRequest(BaseModel):
    symbol: str = "XAUUSD"
    side: str = "BUY"
    entry_price: float
    stop_loss: float
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    requested_risk_pct: float = 1.0
    account_balance: float = 10000.0


class RiskPreviewResponse(BaseModel):
    symbol: str
    side: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    account_balance: float
    target_risk_usd: float
    calculated_lot_size: float
    actual_risk_usd: float
    actual_risk_pct: float
    reward_tp1_usd: float
    reward_tp1_pct: float
    reward_tp2_usd: float
    reward_tp2_pct: float
    risk_reward_ratio: str
    estimated_margin_usd: float
    is_valid: bool
    warnings: List[str]
    errors: List[str]
    live_broker_transmission: str = "BLOCKED"


# -------------------------------------------------------------------------
# 7. Positions Schemas (Stage 3 Read-Only)
# -------------------------------------------------------------------------
class PositionItem(BaseModel):
    position_id: str
    symbol: str
    direction: str
    volume: float
    entry_price: float
    current_price: float
    sl: float
    tp: float
    floating_pnl: float
    unrealized_r: str
    mae: str
    mfe: str
    account_id: str


class PositionsResponse(BaseModel):
    positions: List[PositionItem]
    total_open: int
    total_floating_pnl: float
    timestamp: str


# -------------------------------------------------------------------------
# 8. Forward Evidence Schemas (Stage 3 Read-Only)
# -------------------------------------------------------------------------
class HistoricalBaselineModel(BaseModel):
    sample_size: int = 82
    expected_r: float = 0.637
    win_rate_pct: float = 58.6
    profit_factor: float = 2.52
    status: str = "LOCKED & UNPOOLED"


class ForwardEvidenceStateResponse(BaseModel):
    symbol: str = "XAUUSD"
    mode: str = "PAPER"
    sample_n: int
    win_rate_pct: float
    profit_factor: float
    expected_r: float
    next_milestone: int
    decision_state: str
    wilson_ci_lower_pct: float
    wilson_ci_upper_pct: float
    historical_baseline: HistoricalBaselineModel
    strategy_contract_hash: str
    live_broker_transmission: str = "BLOCKED"
    timestamp: str
