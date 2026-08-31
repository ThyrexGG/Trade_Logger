"""
Automated Unit Tests for Phase 15 — USDJPY ICT/SMC Edge Investigation & Research
Tests:
- USDJPYAblationRunner (Configuration integrity for Experiments A-L)
- USDJPYDiagnosticProfiler (Directional analysis, MAE/MFE profiling, Mechanical Baselines)
- Multiple-Testing Tracking on USDJPY hypotheses
- Structural Excursion Calculations (+1R, +2R giveback detection)
"""

import pytest
import pandas as pd
import numpy as np
import strategies
from usdjpy_research import USDJPYAblationRunner, USDJPYDiagnosticProfiler
import research_engine
import research_analytics


def test_usdjpy_ablation_runner_configs():
    configs = USDJPYAblationRunner.ABLATION_CONFIGS
    assert len(configs) == 12

    required_keys = [
        "EXP_A_SWEEP_ONLY",
        "EXP_B_SWEEP_MSS",
        "EXP_C_SWEEP_MSS_FVG",
        "EXP_D_SWEEP_MSS_FVG_HTF",
        "EXP_E_SWEEP_MSS_FVG_KILLZONE",
        "EXP_F_SWEEP_MSS_FVG_HTF_KILLZONE",
        "EXP_G_HTF_LIQUIDITY_PRIORITY",
        "EXP_H_EQH_EQL_LIQUIDITY",
        "EXP_I_DISPLACEMENT_FILTER",
        "EXP_J_PREMIUM_DISCOUNT_FILTER",
        "EXP_K_OTE_FIBONACCI_FILTER",
        "EXP_L_ORDER_BLOCK_CONFIRMATION"
    ]
    for k in required_keys:
        assert k in configs
        assert "name" in configs[k]
        assert "strategy" in configs[k]


def test_profile_direction():
    mock_trades = [
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 151.00}, # +2.0R
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 149.50}, # -1.0R
        {"direction": "SELL", "entry_price": 150.00, "stop_loss": 150.50, "exit_price": 148.50}, # +3.0R
        {"direction": "SELL", "entry_price": 150.00, "stop_loss": 150.50, "exit_price": 149.00}, # +2.0R
    ]
    df_r = research_analytics.calculate_trade_r_multiples(mock_trades)
    dir_res = USDJPYDiagnosticProfiler.profile_direction(df_r)

    assert dir_res["long_trades"] == 2
    assert dir_res["short_trades"] == 2
    assert dir_res["long_expectancy_r"] == 0.5
    assert dir_res["short_expectancy_r"] == 2.5
    assert dir_res["directional_bias_verdict"] == "SHORT SKEWED"


def test_profile_mae_mfe_profit_giveback():
    mock_trades = [
        # Winner
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 151.25, "mae": 0.1, "mfe": 1.25}, # +2.5R
        # Loser that reached +1.2R before stopping out
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 149.50, "mae": 0.5, "mfe": 0.6}, # -1.0R, mfe_r = 1.2R
        # Loser that reached +1.5R before stopping out
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 149.50, "mae": 0.5, "mfe": 0.75}, # -1.0R, mfe_r = 1.5R
        # Immediate invalidation
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 149.50, "mae": 0.5, "mfe": 0.05} # -1.0R, mfe_r = 0.1R
    ]
    df_r = research_analytics.calculate_trade_r_multiples(mock_trades)
    mae_res = USDJPYDiagnosticProfiler.profile_mae_mfe(df_r)

    assert mae_res["total_trades"] == 4
    assert mae_res["total_losses"] == 3
    assert mae_res["reached_1r_loss_count"] == 2
    assert mae_res["reached_1r_stopout_pct"] > 60.0
    assert "SEVERE PROFIT GIVEBACK" in mae_res["structural_diagnosis"]


def test_compare_mechanical_baselines():
    mock_trades = [
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.50, "exit_price": 150.50}
    ]
    df_r = research_analytics.calculate_trade_r_multiples(mock_trades)
    baselines = USDJPYDiagnosticProfiler.compare_mechanical_baselines(df_r)

    assert len(baselines) == 5
    names = [b["baseline_name"] for b in baselines]
    assert any("Observed" in n for n in names)
    assert any("Random" in n for n in names)
    assert any("Long-Only" in n for n in names)
    assert any("Session Open" in n for n in names)


def test_ablation_runner_structure():
    # Verify ablation keys are properly mapped to strategy classes
    for key, cfg in USDJPYAblationRunner.ABLATION_CONFIGS.items():
        strat = strategies.get_strategy(cfg["strategy"])
        assert strat is not None, f"Strategy {cfg['strategy']} not registered for {key}"
        assert strat.version == "1.1.0"

