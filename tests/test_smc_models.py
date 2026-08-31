"""
Comprehensive Unit Tests for Structured SMC / ICT Data Models (Phase 13)
Tests:
- LiquidityPool, FairValueGap, OrderBlock, DealingRange, MarketStructureEvent models
- Fibonacci Premium / Discount zone boundaries & Equilibrium
- Consequent Encroachment (CE) & Mean Threshold (MT)
- Inversion FVG (IFVG) & Breaker Block state tracking
- Multi-Timeframe SMCContext assembly & AI prompt summarization
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from strategies.smc_models import (
    LiquidityPool,
    FairValueGap,
    OrderBlock,
    MarketStructureEvent,
    DealingRange,
    SMCContext
)
from strategies.smc_utils import (
    add_smc_features,
    extract_active_liquidity_pools,
    extract_active_fair_value_gaps,
    extract_order_blocks,
    extract_dealing_range,
    extract_market_structure_events,
    build_smc_context
)


def create_mock_candles(n_bars=60):
    timestamps = pd.date_range("2026-08-31 00:00:00", periods=n_bars, freq="15min", tz="UTC")
    np.random.seed(42)
    closes = 1.0800 + np.cumsum(np.random.randn(n_bars) * 0.0005)
    highs = closes + np.random.uniform(0.0002, 0.0008, n_bars)
    lows = closes - np.random.uniform(0.0002, 0.0008, n_bars)
    opens = (highs + lows) / 2.0
    volumes = np.random.randint(100, 1000, n_bars)

    df = pd.DataFrame({
        "Open": opens,
        "High": highs,
        "Low": lows,
        "Close": closes,
        "Volume": volumes
    }, index=timestamps)
    return df


def test_dealing_range_premium_discount():
    dr = DealingRange(high=1.1000, low=1.0000, timeframe="1h", created_at="2026-08-31T00:00:00Z")
    assert dr.equilibrium == 1.0500
    assert dr.range_size == 0.1000
    
    # Premium: > 52% (price > 1.052)
    assert dr.get_zone(1.0600) == "PREMIUM"
    # Discount: < 48% (price < 1.048)
    assert dr.get_zone(1.0300) == "DISCOUNT"
    # Equilibrium: between 48% and 52%
    assert dr.get_zone(1.0500) == "EQUILIBRIUM"

    fibs = dr.get_fib_levels()
    assert fibs["0.500_Equilibrium"] == 1.0500
    assert fibs["0.705_OTE_Mid"] == 1.0705


def test_fair_value_gap_midpoint_and_inversion():
    fvg = FairValueGap(
        fvg_id="FVG_1",
        direction="BULLISH",
        top=1.0900,
        bottom=1.0800,
        timeframe="15m",
        created_at="2026-08-31T00:00:00Z",
        bar_index=10,
        displacement_atr_ratio=2.0
    )
    assert fvg.midpoint == 1.0850 # Consequent Encroachment (CE)
    assert abs(fvg.height_pips - 0.0100) < 1e-6
    assert fvg.is_inversion is False
    assert fvg.is_mitigated is False


def test_order_block_mean_threshold():
    ob = OrderBlock(
        ob_id="OB_1",
        direction="BULLISH",
        top=1.0850,
        bottom=1.0810,
        timeframe="15m",
        created_at="2026-08-31T00:00:00Z",
        bar_index=15,
        displacement_atr_ratio=2.5
    )
    assert ob.mean_threshold == 1.0830 # 50% Mean Threshold


def test_smc_context_generation_and_ai_summary():
    df = create_mock_candles(60)
    
    # Inject an intentional Bullish FVG at bars 20-22
    df.iloc[19, df.columns.get_loc('High')] = 1.0700
    df.iloc[20, df.columns.get_loc('High')] = 1.0720
    df.iloc[21, df.columns.get_loc('Low')] = 1.0750
    df.iloc[21, df.columns.get_loc('High')] = 1.0900
    df.iloc[22, df.columns.get_loc('Low')] = 1.0800
    df.iloc[22, df.columns.get_loc('Close')] = 1.0850
    
    context = build_smc_context(
        df_exec=df,
        symbol="EURUSD",
        current_index=len(df) - 1,
        exec_tf="15m",
        struct_tf="1h",
        bias_tf="4h"
    )
    
    assert isinstance(context, SMCContext)
    assert context.symbol == "EURUSD"
    assert context.execution_timeframe == "15m"
    assert context.dealing_range is not None
    assert context.current_price > 0
    
    summary = context.to_ai_summary()
    assert "--- SMC / ICT Market Context ---" in summary
    assert "EURUSD" in summary
    assert "Dealing Range:" in summary
    assert "Equilibrium=" in summary


def test_pre_trade_risk_preview():
    from risk_gateway import calculate_pre_trade_risk_preview
    
    # Buy EURUSD: Entry 1.0850, SL 1.0800 (50 pips), TP1 1.0950 (100 pips -> R:R 1:2.0)
    # Balance $10,000, 1.0% target risk ($100) -> Lots = $100 / (0.0050 * 100,000) = 0.20 lots
    preview = calculate_pre_trade_risk_preview(
        symbol="EURUSD",
        side="BUY",
        entry_price=1.0850,
        stop_loss=1.0800,
        take_profit_1=1.0950,
        take_profit_2=1.1000,
        requested_risk_pct=1.0,
        account_balance=10000.0
    )

    assert preview["is_valid"] is True
    assert preview["calculated_lot_size"] == 0.20
    assert preview["actual_risk_usd"] == 100.0
    assert preview["actual_risk_pct"] == 1.0
    assert preview["reward_tp1_usd"] == 200.0
    assert preview["risk_reward_ratio"] == "1:2.00"
    assert preview["estimated_margin_usd"] > 0

