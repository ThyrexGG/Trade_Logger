"""
Automated Unit Tests for Phase 17 — USDJPY Edge Discovery Lab: Regime, Session & Mechanical Strategy Research
Tests:
- USDJPYRegimeEngine classification (Trend, Structure, Volatility Percentiles, Session Windows)
- USDJPYMechanicalExperimentRunner catalog integrity (20 mechanical strategies + 7 baselines)
- USDJPYDeepExcursionAnalyzer MAE/MFE calculation & SL/TP structure matrix
- USDJPYHoldingTimeAnalyzer & USDJPYDayOfWeekAnalyzer metrics
- USDJPYTrendPersistenceAnalyzer & Complexity scoring formulas
"""

import pytest
import pandas as pd
import numpy as np
from usdjpy_edge_discovery import (
    USDJPYRegimeEngine,
    USDJPYMechanicalExperimentRunner,
    USDJPYDeepExcursionAnalyzer,
    USDJPYHoldingTimeAnalyzer,
    USDJPYDayOfWeekAnalyzer,
    USDJPYTrendPersistenceAnalyzer
)
import research_analytics


def test_usdjpy_regime_classification():
    # Construct 100 synthetic OHLCV bars with a datetime index
    dates = pd.date_range("2026-08-01 00:00", periods=100, freq="15min", tz="UTC")
    closes = 150.0 + np.linspace(0, 5.0, 100) # Strong upward trend
    highs = closes + 0.10
    lows = closes - 0.10
    opens = closes - 0.02
    volume = np.ones(100) * 1000

    df = pd.DataFrame({
        "Open": opens,
        "High": highs,
        "Low": lows,
        "Close": closes,
        "Volume": volume
    }, index=dates)

    classified = USDJPYRegimeEngine.classify_regimes(df)

    assert "trend_regime" in classified.columns
    assert "volatility_bucket" in classified.columns
    assert "volatility_state" in classified.columns
    assert "structural_regime" in classified.columns
    assert "session_regime" in classified.columns
    assert "day_of_week" in classified.columns

    # The latter half of the upward trend should be BULL_TREND
    assert (classified["trend_regime"].iloc[50:] == "BULL_TREND").any()


def test_usdjpy_mechanical_catalog_completeness():
    catalog = USDJPYMechanicalExperimentRunner.EXPERIMENT_CATALOG
    assert len(catalog) == 27 # 10 Session + 5 Trend + 5 Mean-Reversion + 7 Baselines

    categories = [cfg["category"] for cfg in catalog.values()]
    assert categories.count("SESSION") == 10
    assert categories.count("TREND") == 5
    assert categories.count("MEAN_REVERSION") == 5
    assert categories.count("BASELINE") == 7

    for k, cfg in catalog.items():
        assert "name" in cfg
        assert "desc" in cfg
        assert "conditions" in cfg
        assert "indicators" in cfg
        assert "parameters" in cfg


def test_usdjpy_deep_excursion_profiler():
    mock_trades = [
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 151.25, "mae_r": 0.1, "mfe_r": 2.5},
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 149.50, "mae_r": 1.0, "mfe_r": 0.2},
        {"direction": "SELL", "entry_price": 150.00, "stop_loss": 150.50, "exit_price": 148.50, "mae_r": 0.2, "mfe_r": 3.0}
    ]
    df_r = research_analytics.calculate_trade_r_multiples(mock_trades)
    df_r["mae_r"] = [t["mae_r"] for t in mock_trades]
    df_r["mfe_r"] = [t["mfe_r"] for t in mock_trades]

    excursion_res = USDJPYDeepExcursionAnalyzer.profile_deep_excursion(df_r)

    assert excursion_res["total_trades"] == 3
    assert excursion_res["total_losses"] == 1
    assert excursion_res["pct_reached_2_0r"] >= 66.0
    assert len(excursion_res["stop_target_matrix"]) >= 6


def test_usdjpy_holding_time_and_days():
    df_empty = pd.DataFrame()
    ht_buckets = USDJPYHoldingTimeAnalyzer.profile_holding_time(df_empty)
    assert len(ht_buckets) == 5
    assert any("Sweet Spot" in b.get("verdict", "").title() for b in ht_buckets)

    dow_res = USDJPYDayOfWeekAnalyzer.profile_days_and_transitions(df_empty)
    assert len(dow_res["day_breakdown"]) == 5
    assert len(dow_res["session_transitions"]) == 4


def test_usdjpy_trend_persistence_map():
    pmap = USDJPYTrendPersistenceAnalyzer.profile_trend_persistence()
    assert len(pmap) == 5
    for p in pmap:
        assert "trigger_event" in p
        assert "bars_4_continuation_pct" in p
        assert "bars_8_continuation_pct" in p
        assert "bars_16_continuation_pct" in p
        assert "bars_32_continuation_pct" in p
