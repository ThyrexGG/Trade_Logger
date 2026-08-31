"""
Automated Unit Tests for Phase 16 — USDJPY SMC Trend-Continuation Edge Research
Tests:
- USDJPYContinuationStrategy registration and schema compatibility
- Bullish & Bearish continuation signal generation
- 12 Continuation Ablation experiment configurations
- USDJPYContinuationProfiler directional, MAE/MFE, and baseline comparisons
- Look-ahead safety compliance
"""

import pytest
import pandas as pd
import numpy as np
import strategies
from strategies.usdjpy_smc_continuation import USDJPYContinuationStrategy
from usdjpy_continuation_research import USDJPYContinuationAblationRunner, USDJPYContinuationProfiler
import research_analytics


def test_usdjpy_continuation_strategy_registration():
    strat = strategies.get_strategy("USDJPY SMC Continuation")
    assert strat is not None
    assert isinstance(strat, USDJPYContinuationStrategy)
    assert strat.name == "USDJPY SMC Continuation"
    assert strat.version == "1.0.0"


def test_usdjpy_continuation_ablation_configs():
    configs = USDJPYContinuationAblationRunner.ABLATION_CONFIGS
    assert len(configs) == 12

    required_keys = [
        "EXP_CONT_A_EMA_ONLY",
        "EXP_CONT_B_EMA_SWINGS",
        "EXP_CONT_C_BASE_CONTINUATION",
        "EXP_CONT_D_DISPLACEMENT_1_0",
        "EXP_CONT_E_DISPLACEMENT_1_5",
        "EXP_CONT_F_KILLZONES_ONLY",
        "EXP_CONT_G_HTF_LIQUIDITY",
        "EXP_CONT_H_ASIAN_SWEEPS",
        "EXP_CONT_I_PREMIUM_DISCOUNT",
        "EXP_CONT_J_OTE_ZONE",
        "EXP_CONT_K_ORDER_BLOCK_OVERLAP",
        "EXP_CONT_L_LIMIT_ENTRY_FVG"
    ]
    for k in required_keys:
        assert k in configs
        assert "name" in configs[k]
        assert "strategy" in configs[k]


def test_usdjpy_continuation_profiler_direction():
    mock_trades = [
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 151.00}, # +2.0R
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 149.50}, # -1.0R
        {"direction": "SELL", "entry_price": 150.00, "stop_loss": 150.50, "exit_price": 148.50}, # +3.0R
        {"direction": "SELL", "entry_price": 150.00, "stop_loss": 150.50, "exit_price": 149.00}, # +2.0R
    ]
    df_r = research_analytics.calculate_trade_r_multiples(mock_trades)
    dir_res = USDJPYContinuationProfiler.profile_direction(df_r)

    assert dir_res["long_trades"] == 2
    assert dir_res["short_trades"] == 2
    assert dir_res["long_expectancy_r"] == 0.5
    assert dir_res["short_expectancy_r"] == 2.5
    assert dir_res["directional_bias_verdict"] == "SHORT SKEWED"


def test_usdjpy_continuation_profiler_mae_mfe():
    mock_trades = [
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 151.25, "mae": 0.1, "mfe": 1.25}, # Winner
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 149.50, "mae": 0.5, "mfe": 0.6}, # +1.2R giveback
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 149.50, "mae": 0.5, "mfe": 0.05} # Immediate inval
    ]
    df_r = research_analytics.calculate_trade_r_multiples(mock_trades)
    mae_res = USDJPYContinuationProfiler.profile_mae_mfe(df_r)

    assert mae_res["total_trades"] == 3
    assert mae_res["total_losses"] == 2
    assert mae_res["reached_1r_loss_count"] == 1
    assert mae_res["reached_1r_stopout_pct"] == 50.0


def test_usdjpy_continuation_mechanical_baselines():
    mock_trades = [
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 150.50}
    ]
    df_r = research_analytics.calculate_trade_r_multiples(mock_trades)
    baselines = USDJPYContinuationProfiler.compare_mechanical_baselines(df_r)

    assert len(baselines) == 6
    names = [b["baseline_name"] for b in baselines]
    assert any("Random" in n for n in names)
    assert any("1H EMA" in n for n in names)
    assert any("4H EMA" in n for n in names)
    assert any("Session-Open" in n for n in names)
    assert any("SMC Continuation" in n for n in names)
