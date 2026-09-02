# -*- coding: utf-8 -*-
"""
TradeLogger FastAPI Pydantic Response & Request Schemas
Stage 2 & Stage 3 Read-Only Vertical Slice Models
"""
from typing import Dict, List, Literal, Optional, Any
from pydantic import BaseModel, ConfigDict, Field, model_validator


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
# 8. Forward Evidence & Governance Schemas (Read-Only)
#
# Stage 9: the response is widened to a faithful pass-through of the
# sub-states the authoritative Phase 49 engine ALREADY computes inside
# Phase49MonitoringFacade.get_cached_forward_state_snapshot(). No statistical,
# governance, or milestone logic lives in the adapter — every value below is
# produced verbatim by the engine and merely serialized here.
# -------------------------------------------------------------------------
class HistoricalBaselineModel(BaseModel):
    sample_size: int = 82
    expected_r: float = 0.637
    win_rate_pct: float = 58.6
    profit_factor: float = 2.52
    status: str = "LOCKED & UNPOOLED"


class ForwardMetricsModel(BaseModel):
    trades_n: int
    win_rate_pct: float
    expectancy_r: float
    average_r: float
    median_r: float
    profit_factor: float
    cumulative_r: float
    max_drawdown_r: float
    std_dev_r: float
    win_count: int
    loss_count: int
    breakeven_count: int
    win_streak: int
    loss_streak: int
    outcomes: Dict[str, float]
    maturity_tier: str
    maturity_label: str
    interpretation: str


class UncertaintyModel(BaseModel):
    sample_n: int
    statistical_status: str
    status_badge: str
    win_rate_statement: str
    expectancy_statement: str
    ci_90_wr: Optional[List[float]] = None
    ci_95_wr: Optional[List[float]] = None
    ci_99_wr: Optional[List[float]] = None
    ci_90_exp: Optional[List[float]] = None
    ci_95_exp: Optional[List[float]] = None
    ci_99_exp: Optional[List[float]] = None
    prohibited_claim: str
    valid_statement: str


class HoldoutComparisonModel(BaseModel):
    historical: Dict[str, Any]
    forward: Dict[str, Any]
    deltas: Dict[str, float]
    comparison_verdict: str
    explanation: str
    pooling_prevention_check: str


class AlphaDecayModel(BaseModel):
    forward_n: int
    decay_state: str
    loss_clustering_detected: bool
    expectancy_deterioration: bool
    max_drawdown_expansion: Optional[bool] = None
    action_required: str
    summary: str


class MilestoneRoadmapEntry(BaseModel):
    target_n: int
    status_label: str
    trades_remaining: int
    is_reached: bool


class MilestoneProgressModel(BaseModel):
    current_n: int
    next_milestone: int
    trades_remaining: int
    completion_pct_toward_next: float
    milestone_roadmap: List[MilestoneRoadmapEntry]


class DecisionStateModel(BaseModel):
    decision_state: str
    rationale: str
    research_action: str


class DatasetProvenanceModel(BaseModel):
    symbol: str
    mode: str
    total_records: int
    clean_n: int
    quarantined_count: int
    dataset_fingerprint: str
    contract_hash: str
    is_isolated: bool
    status: str


class SafetyBarrierModel(BaseModel):
    live_automation_enabled: bool = False
    broker_transmission: str = "BLOCKED (FAIL-CLOSED)"
    status: str = "PASS (SAFETY LOCKED)"


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
    contract_valid: bool = True
    live_broker_transmission: str = "BLOCKED"
    # Stage 9 — authoritative sub-state pass-through
    metrics: ForwardMetricsModel
    uncertainty: UncertaintyModel
    holdout: HoldoutComparisonModel
    alpha_decay: AlphaDecayModel
    milestones: MilestoneProgressModel
    decision: DecisionStateModel
    dataset: DatasetProvenanceModel
    safety: SafetyBarrierModel
    timestamp: str


# -------------------------------------------------------------------------
# 9. Strategy Lab & Backtesting Schemas (Research-Only)
#
# Stage 10: thin adapter over the authoritative research code
# (`backtester.run_backtest` / `run_walk_forward` / `run_monte_carlo`,
# `research_engine.ResearchExperiment`, the `strategies` registry). React
# never reproduces any backtest, indicator, optimization or Monte-Carlo
# calculation — every value below is produced by the Python research engine
# and merely serialized here. Research-only: no broker, no live execution.
# -------------------------------------------------------------------------
class StrategyInfo(BaseModel):
    name: str
    version: str
    description: str


class ResearchDefaults(BaseModel):
    train_split: float
    val_split: float
    holdout_split: float
    struct_tf: str
    bias_tf: str
    spread_pips: float
    slippage_pips: float
    commission_pct: float
    random_seed: int


class BacktestDefaults(BaseModel):
    strategy: str
    risk_pct: float
    sl_atr: float
    tp_atr: float
    capital: float
    slippage: float
    commission_pct: float
    fixed_spread: float
    train_split: float


class TimeframeSpec(BaseModel):
    timeframe: str
    period: str
    interval: str
    struct_tf: str
    bias_tf: str


class ResearchMethodology(BaseModel):
    execution_model: str
    lookahead_protection: bool
    lookahead_note: str
    data_source: str
    timezone: str
    slippage_model: str
    commission_model: str
    spread_model: str
    split_model: str
    notes: List[str]


class StrategyLabResponse(BaseModel):
    contract_hash: str
    strategies: List[StrategyInfo]
    research_defaults: ResearchDefaults
    backtest_defaults: BacktestDefaults
    supported_symbols: List[str]
    timeframes: List[TimeframeSpec]
    methodology: ResearchMethodology
    mode: str = "RESEARCH"
    live_broker_transmission: str = "BLOCKED"
    timestamp: str


class BacktestRunRequest(BaseModel):
    symbol: str = "XAUUSD"
    timeframe: str = "1h"
    strategy: str = "Trend Continuation"
    mode: str = "standard"  # "standard" | "walk_forward"
    risk_pct: float = 1.0
    sl_atr: float = 1.5
    tp_atr: float = 2.0
    capital: float = 10000.0
    slippage: float = 0.0001
    commission_pct: float = 0.01
    fixed_spread: float = 0.0
    train_split: float = 0.8
    include_monte_carlo: bool = True


class BacktestMetricsBlock(BaseModel):
    total_trades: int
    win_rate_pct: Optional[float] = None
    profit_factor: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    wfo_flag: Optional[str] = None
    raw: Dict[str, str]


class BacktestTrade(BaseModel):
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    direction: Optional[str] = None
    position_size: Optional[float] = None
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    gross_pnl: Optional[float] = None
    commission: Optional[float] = None
    pnl: Optional[float] = None
    equity: Optional[float] = None
    is_oos: Optional[bool] = None
    session: Optional[str] = None
    liquidity_type: Optional[str] = None
    confluence_score: Optional[float] = None


class EquityPoint(BaseModel):
    time: str
    equity: float


class MonteCarloBlock(BaseModel):
    iterations: int
    risk_of_ruin_pct: float
    confidence_95_dd_pct: float
    median_dd_pct: float
    note: str = "Trade-order reshuffle simulation over the executed trade P&L series."


class BacktestConfigEcho(BaseModel):
    symbol: str
    timeframe: str
    strategy: str
    mode: str
    risk_pct: float
    sl_atr: float
    tp_atr: float
    capital: float
    slippage: float
    commission_pct: float
    fixed_spread: float
    train_split: float


class BacktestRunResponse(BaseModel):
    status: str  # "complete" | "failed"
    mode: str
    config: BacktestConfigEcho
    config_id: str
    error: Optional[str] = None
    ran_at: str
    duration_sec: float
    metrics: Optional[BacktestMetricsBlock] = None
    metrics_is: Optional[BacktestMetricsBlock] = None
    metrics_oos: Optional[BacktestMetricsBlock] = None
    final_capital: Optional[str] = None
    final_capital_value: Optional[float] = None
    trades: List[BacktestTrade] = Field(default_factory=list)
    trades_total: int = 0
    trades_truncated: bool = False
    equity_curve: List[EquityPoint] = Field(default_factory=list)
    equity_curve_total: int = 0
    equity_curve_sampled: bool = False
    monte_carlo: Optional[MonteCarloBlock] = None
    wfo_flag: Optional[str] = None
    live_broker_transmission: str = "BLOCKED"


# -------------------------------------------------------------------------
# 9B. Research Lab / Adversarial Audit Schemas (Stage 15B)
#     Thin adapter over research_analytics.* + research_engine.* applied to an
#     authoritative backtester.run_backtest result. Every statistic is produced
#     by the canonical research code and only serialized here. Research-only:
#     no broker / execution / automation path.
# -------------------------------------------------------------------------
class ResearchAuditRequest(BaseModel):
    symbol: str = "XAUUSD"
    timeframe: str = "1h"
    strategy: str = "Trend Continuation"
    risk_pct: float = 1.0
    sl_atr: float = 1.5
    tp_atr: float = 2.0
    capital: float = 10000.0
    slippage: float = 0.0001
    commission_pct: float = 0.01
    fixed_spread: float = 0.0
    train_split: float = 0.60


class ResearchDimensionRow(BaseModel):
    """One row of `research_analytics.analyze_dimension_metrics` (observed + calculated)."""
    group: str
    trades_n: int
    sample_tier: str
    win_rate_pct: float
    expectancy_r: float
    mean_r: float
    median_r: float
    profit_factor: float
    max_drawdown_r: float
    avg_mae_r: float
    avg_mfe_r: float
    cumulative_r: float


class ResearchLayerExpectancy(BaseModel):
    train_r: float
    train_trades: int
    validation_r: float
    validation_trades: int
    holdout_r: float
    holdout_trades: int


class ResearchBootstrapCI(BaseModel):
    sample_size: int
    observed_mean_r: float
    observed_median_r: float
    ci_lower: float
    ci_upper: float
    ci_range_str: str
    verdict: str
    sample_confidence: str


class ResearchScorecard(BaseModel):
    status: str
    color: str
    is_deployable: bool
    sample_size: int
    oos_trades: int
    oos_expectancy_r: float
    holdout_expectancy_r: float
    score_reasons: List[str]


class ResearchStressScenario(BaseModel):
    scenario: str
    expectancy_r: float
    edge_retention_pct: float
    is_profitable: bool


class ResearchExecutionStress(BaseModel):
    base_expectancy_r: float
    fragility_rating: str
    scenarios: List[ResearchStressScenario]


class ResearchDriftPoint(BaseModel):
    trade_index: int
    rolling_20_r: float


class ResearchExpectancyDrift(BaseModel):
    status: str
    historical_expectancy_r: float
    rolling_20_r: float
    rolling_50_r: float
    rolling_100_r: float
    curve: List[ResearchDriftPoint]


class ResearchQualityPoint(BaseModel):
    min_confluence: float
    trades_n: int
    expectancy_r: float
    win_rate_pct: float


class ResearchConfluenceCalibration(BaseModel):
    calibration_status: str
    buckets: List[ResearchDimensionRow]
    quality_curve: List[ResearchQualityPoint]


class ResearchAuditResponse(BaseModel):
    status: str  # "complete" | "failed"
    config: BacktestConfigEcho
    config_id: str
    error: Optional[str] = None
    ran_at: str
    duration_sec: float
    contract_hash: str
    sample_n: int
    layer_expectancy: Optional[ResearchLayerExpectancy] = None
    bootstrap_ci: Optional[ResearchBootstrapCI] = None
    scorecard: Optional[ResearchScorecard] = None
    execution_stress: Optional[ResearchExecutionStress] = None
    expectancy_drift: Optional[ResearchExpectancyDrift] = None
    liquidity_breakdown: List[ResearchDimensionRow] = []
    session_breakdown: List[ResearchDimensionRow] = []
    liquidity_session_matrix: List[ResearchDimensionRow] = []
    regime_breakdown: List[ResearchDimensionRow] = []
    hourly_breakdown: List[ResearchDimensionRow] = []
    daily_breakdown: List[ResearchDimensionRow] = []
    confluence: Optional[ResearchConfluenceCalibration] = None
    notes: List[str] = []
    live_broker_transmission: str = "BLOCKED"


# -------------------------------------------------------------------------
# 10. Operations Schemas (Positions page reuses section 7; Journal / Audit /
#     System are read-only pass-throughs of authoritative SQLite tables and
#     `system_health.evaluate_system_health`). No execution, no mutation.
# -------------------------------------------------------------------------
class JournalTradeItem(BaseModel):
    trade_id: str
    account_id: str
    symbol: str
    direction: str
    volume: float
    entry_price: float
    exit_price: float
    commission: float
    swap: float
    gross_profit: float
    net_profit: float
    entry_time: str
    exit_time: str
    duration_minutes: float
    setup_tag: Optional[str] = None
    notes: Optional[str] = None
    rating: Optional[int] = None
    chart_snapshot_url: Optional[str] = None


class JournalResponse(BaseModel):
    entries: List[JournalTradeItem]
    total_trades: int
    wins: int
    losses: int
    total_net_profit: float
    accounts: List[str]
    source: str = "closed_trades"
    writable: bool = True
    timestamp: str


# --- Journal edit (Stage 12) -----------------------------------------------
# Only the subjective annotation fields the legacy Streamlit journal edits
# (`database.update_trade_journal`) are writable. Every execution / trade fact
# (symbol, side, prices, volume, timestamps, P&L, ids) is immutable and is
# rejected as an unknown field by `extra="forbid"`.
_JOURNAL_EDITABLE_FIELDS = ("setup_tag", "notes", "chart_snapshot_url")


class JournalUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    setup_tag: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=20_000)
    chart_snapshot_url: Optional[str] = Field(default=None, max_length=3_000_000)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "JournalUpdateRequest":
        if all(getattr(self, f) is None for f in _JOURNAL_EDITABLE_FIELDS):
            raise ValueError(
                "provide at least one editable field: "
                + ", ".join(_JOURNAL_EDITABLE_FIELDS)
            )
        return self


class JournalUpdateResponse(BaseModel):
    entry: JournalTradeItem
    updated_fields: List[str]
    writable: bool = True
    source: str = "closed_trades"
    live_broker_transmission: str = "BLOCKED"
    timestamp: str


class AuditOrderItem(BaseModel):
    execution_id: str
    signal_id: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    requested_quantity: Optional[float] = None
    requested_entry: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    broker: Optional[str] = None
    mode: Optional[str] = None
    state: Optional[str] = None
    reconciliation_status: Optional[str] = None
    created_at: Optional[str] = None
    submitted_at: Optional[str] = None
    resolved_at: Optional[str] = None
    filled_at: Optional[str] = None
    execution_latency_ms: Optional[float] = None
    reject_reason: Optional[str] = None
    last_error: Optional[str] = None


class AuditResponse(BaseModel):
    events: List[AuditOrderItem]
    total_returned: int
    total_records: int
    state_counts: Dict[str, int]
    mode_counts: Dict[str, int]
    decision_ledger_records: int
    latest_event_at: Optional[str] = None
    source: str = "execution_orders"
    read_only: bool = True
    live_broker_transmission: str = "BLOCKED"
    timestamp: str


class ReconciliationHealth(BaseModel):
    status: Optional[str] = None
    healthy: Optional[bool] = None
    reason: Optional[str] = None
    last_heartbeat: Optional[str] = None
    last_success: Optional[str] = None
    consecutive_failures: Optional[int] = None
    iterations_count: Optional[int] = None


class SystemSafetyGate(BaseModel):
    overall_status: str
    automation_allowed: bool
    reasons: List[str]
    kill_switch_engaged: Optional[bool] = None
    emergency_halt_engaged: Optional[bool] = None
    database_connected: Optional[bool] = None
    unresolved_unknown_orders_count: Optional[int] = None
    reconciliation: Optional[ReconciliationHealth] = None


class OperationsSystemResponse(BaseModel):
    api_status: str
    app_name: str
    version: str
    live_automation_enabled: bool = False
    live_broker_transmission: str = "BLOCKED"
    safety_gate: SystemSafetyGate
    open_positions: int
    timestamp: str


# -------------------------------------------------------------------------
# 11. Price Alerts Schemas (Stage 13) — monitoring only. Thin adapter over the
#     authoritative `price_alerts` table and `database.*_price_alert` helpers.
#     No execution, no broker, no order path. `id` / `status` / `created_at` /
#     `triggered_at` are server-maintained and never client-controlled.
# -------------------------------------------------------------------------
AlertCondition = Literal["ABOVE", "BELOW"]


class AlertItem(BaseModel):
    id: int
    symbol: str
    target_price: float
    condition: AlertCondition
    status: str
    account_id: str = "ALL"
    notes: Optional[str] = None
    created_at: Optional[str] = None
    triggered_at: Optional[str] = None


class AlertsResponse(BaseModel):
    alerts: List[AlertItem]
    total: int
    active: int
    triggered: int
    supported_symbols: List[str]
    source: str = "price_alerts"
    live_broker_transmission: str = "BLOCKED"
    timestamp: str


class AlertCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(..., min_length=1, max_length=32)
    target_price: float = Field(..., gt=0)
    condition: AlertCondition
    notes: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _finite_price(self) -> "AlertCreateRequest":
        import math as _math
        if not _math.isfinite(self.target_price):
            raise ValueError("target_price must be a finite number")
        return self


class AlertCreateResponse(BaseModel):
    alert: AlertItem
    live_broker_transmission: str = "BLOCKED"
    timestamp: str


class AlertDeleteResponse(BaseModel):
    deleted: bool = True
    alert_id: int
    timestamp: str


# -------------------------------------------------------------------------
# 12. Analytics Schemas (Stage 14) — read-only. Thin adapter over the
#     authoritative `analytics.calculate_performance_metrics` + the
#     `closed_trades` table. GET-only, no execution / broker / order path.
# -------------------------------------------------------------------------
class SymbolPnl(BaseModel):
    symbol: str
    net_profit: float


class DirectionStats(BaseModel):
    trades: int
    win_rate: float
    pnl: float


class PerformanceMetrics(BaseModel):
    """Faithful mirror of `analytics.calculate_performance_metrics` output."""
    total_trades: int
    winning_trades: int
    losing_trades: int
    break_even_trades: int
    win_rate: float
    loss_rate: float
    total_net_pnl: float
    total_gross_profit: float
    total_gross_loss: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    win_loss_ratio: float
    expectancy: float
    max_drawdown_usd: float
    max_drawdown_pct: float
    sqn: float
    gain_pct: float
    final_balance: float
    peak_balance: float
    avg_duration_minutes: float
    long_stats: DirectionStats
    short_stats: DirectionStats
    best_trade: float
    worst_trade: float
    best_symbols: List[SymbolPnl]
    worst_symbols: List[SymbolPnl]


class EquityAnchor(BaseModel):
    time: str
    equity: float
    net_profit: float
    symbol: str


class DailyPnl(BaseModel):
    date: str
    net_profit: float
    trades: int


class SymbolBreakdownRow(BaseModel):
    symbol: str
    net_profit: float
    trades: int
    wins: int
    win_rate: float


class TagBreakdownRow(BaseModel):
    setup_tag: str
    net_profit: float
    trades: int


class PeriodReturns(BaseModel):
    """P&L windows relative to *now* (matches the Streamlit implementation)."""
    avg_daily_pct: float
    weekly_pct: float
    monthly_pct: float
    annualized_pct: float
    weekly_pnl: float
    monthly_pnl: float


class AnalyticsFiltersEcho(BaseModel):
    account: str
    symbols: List[str]
    start: Optional[str] = None
    end: Optional[str] = None
    initial_balance: float


class AnalyticsAvailable(BaseModel):
    accounts: List[str]
    symbols: List[str]
    date_min: Optional[str] = None
    date_max: Optional[str] = None


class AnalyticsPerformanceResponse(BaseModel):
    metrics: PerformanceMetrics
    equity_curve: List[EquityAnchor]
    equity_curve_sampled: bool
    daily_pnl: List[DailyPnl]
    symbol_breakdown: List[SymbolBreakdownRow]
    tag_breakdown: List[TagBreakdownRow]
    period_returns: PeriodReturns
    official_balance: Optional[float] = None
    filters_applied: AnalyticsFiltersEcho
    available: AnalyticsAvailable
    matched_trades: int
    source: str = "closed_trades"
    live_broker_transmission: str = "BLOCKED"
    timestamp: str


# -------------------------------------------------------------------------
# 13. Daily Command Center Schemas (Stage 15A) — read-only aggregator.
#     Every section is a re-shaped slice of an already-authoritative source
#     (analytics / positions / alerts / intelligence / forward-evidence /
#     research notes). No new calculation, no execution / broker path.
# -------------------------------------------------------------------------
class CCSessionClock(BaseModel):
    utc_time: str
    current_session: str
    next_session: str
    next_session_in_min: Optional[int] = None


class CCSafety(BaseModel):
    automation_enabled: bool = False
    live_broker_transmission: str = "BLOCKED"
    kill_switch_engaged: Optional[bool] = None
    overall_status: str = "UNKNOWN"


class CCDailyPerformance(BaseModel):
    date: str
    net_pnl: float
    trades: int
    wins: int
    losses: int
    win_rate: float
    gross_profit: float
    gross_loss: float


class CCAccountSummary(BaseModel):
    all_time_net_pnl: float
    all_time_trades: int
    all_time_win_rate: float
    profit_factor: float
    max_drawdown_pct: float
    official_balance: Optional[float] = None
    derived_balance: float


class CCSymbolExposure(BaseModel):
    symbol: str
    count: int
    floating_pnl: float


class CCPositions(BaseModel):
    total_open: int
    total_floating_pnl: float
    long_count: int
    short_count: int
    by_symbol: List[CCSymbolExposure]


class CCTriggeredAlert(BaseModel):
    id: int
    symbol: str
    condition: str
    target_price: float
    triggered_at: Optional[str] = None


class CCAlerts(BaseModel):
    active: int
    triggered: int
    triggered_recent: List[CCTriggeredAlert]


class CCMarketContext(BaseModel):
    primary_regime: str
    regime_confidence_pct: float
    breadth_bullish_pct: float
    breadth_bearish_pct: float
    strongest_asset: str
    weakest_asset: str
    usd_strength_state: str
    data_quality: int


class CCResearchState(BaseModel):
    decision_state: str
    sample_n: int
    headline: str


class CCNote(BaseModel):
    note_id: str
    created_at: str
    category: str
    note_text: str
    session_context: Optional[str] = None


class CCWatchHighlight(BaseModel):
    symbol: str
    last_price: Optional[float] = None
    bias: Optional[str] = None
    score: Optional[float] = None


class CommandCenterOverviewResponse(BaseModel):
    as_of: str
    session: CCSessionClock
    safety: CCSafety
    daily_performance: Optional[CCDailyPerformance] = None
    account_summary: Optional[CCAccountSummary] = None
    positions: Optional[CCPositions] = None
    alerts: Optional[CCAlerts] = None
    market_context: Optional[CCMarketContext] = None
    research_state: Optional[CCResearchState] = None
    research_notes: List[CCNote] = []
    watchlist_highlights: List[CCWatchHighlight] = []
    sections_degraded: List[str] = []
    source: str = "command_center_aggregate"
    live_broker_transmission: str = "BLOCKED"
    timestamp: str


# -------------------------------------------------------------------------
# 14. AI Assistant Schemas (Stage 15C) — read-only analytical chat over an
#     allowlisted TradeLogger context + Gemini. The chat endpoint being POST
#     does NOT give it execution authority: it only generates text. No path to
#     execution_pipeline / broker_adapter / risk_gateway / order submission.
# -------------------------------------------------------------------------
AIChatRole = Literal["user", "assistant"]


class AIChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: AIChatRole
    content: str = Field(..., min_length=1, max_length=4000)


class AIChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: List[AIChatMessage] = Field(..., min_length=1, max_length=20)

    @model_validator(mode="after")
    def _bounds(self) -> "AIChatRequest":
        if self.messages[-1].role != "user":
            raise ValueError("the last message must be from the user")
        total = sum(len(m.content) for m in self.messages)
        if total > 24_000:
            raise ValueError("conversation too large (max 24000 characters total)")
        return self


class AIChatResponse(BaseModel):
    ok: bool
    reply: Optional[str] = None
    error: Optional[str] = None
    error_kind: Optional[str] = None  # not_configured | provider_unavailable | timeout | rate_limit | empty
    model: Optional[str] = None
    context_sections_used: List[str] = []
    context_sections_unavailable: List[str] = []
    read_only: bool = True
    live_broker_transmission: str = "BLOCKED"
    timestamp: str


class AIStatusResponse(BaseModel):
    configured: bool
    model: Optional[str] = None
    read_only: bool = True
    live_broker_transmission: str = "BLOCKED"
    timestamp: str
