"""
Comprehensive Automated Unit Tests for Phase 14 Strategy Edge Discovery & Research Lab
Tests:
- ThreeLayerDataSplitter (60% Train, 20% Validation, 20% Untouched Final Holdout)
- BootstrapEstimator (Deterministic 95% CI reproducibility & verdict logic)
- MultipleTestingTracker (Hypotheses tracking & Bonferroni data-mining warnings)
- ScorecardClassifier (STRONG, PROMISING, UNCERTAIN, FAILED, INSUFFICIENT DATA)
- Trade R-Multiple, MAE, MFE Normalization
- Liquidity Source & Session Matrix Attribution
- Confluence Calibration Curve
- Execution Sensitivity Stress Testing & Expectancy Drift Monitoring
"""

import pytest
import pandas as pd
import numpy as np
from research_engine import (
    ResearchExperiment,
    ThreeLayerDataSplitter,
    MultipleTestingTracker,
    BootstrapEstimator,
    ScorecardClassifier
)
from research_analytics import (
    calculate_trade_r_multiples,
    analyze_dimension_metrics,
    analyze_liquidity_sources,
    analyze_sessions,
    analyze_confluence_calibration,
    stress_test_execution_sensitivity,
    monitor_expectancy_drift
)


def test_three_layer_data_splitter():
    timestamps = pd.date_range("2026-01-01", periods=100, freq="1D", tz="UTC")
    df = pd.DataFrame({"Close": np.linspace(1.0, 2.0, 100)}, index=timestamps)

    splits = ThreeLayerDataSplitter.split(df, train_ratio=0.60, val_ratio=0.20)
    train_df = splits["train"]
    val_df = splits["validation"]
    holdout_df = splits["holdout"]

    assert len(train_df) == 60
    assert len(val_df) == 20
    assert len(holdout_df) == 20

    # Ensure zero overlap
    assert train_df.index[-1] < val_df.index[0]
    assert val_df.index[-1] < holdout_df.index[0]


def test_bootstrap_estimator_reproducibility_and_verdicts():
    # 1. Positive expectancy series (e.g. mean +0.5R)
    np.random.seed(42)
    pos_r = list(np.random.normal(loc=0.5, scale=0.8, size=150))
    res_pos = BootstrapEstimator.calculate_r_expectancy_ci(pos_r, n_iterations=2000, random_seed=42)

    assert res_pos["sample_size"] == 150
    assert res_pos["sample_confidence"] == "MODERATE SAMPLE (100-299)"
    assert res_pos["observed_mean_r"] > 0
    assert res_pos["ci_lower"] > 0
    assert res_pos["verdict"] == "POSITIVE EXPECTANCY SUPPORTED BY SAMPLE"

    # Deterministic reproducibility test (same seed -> identical CI)
    res_pos2 = BootstrapEstimator.calculate_r_expectancy_ci(pos_r, n_iterations=2000, random_seed=42)
    assert res_pos["ci_lower"] == res_pos2["ci_lower"]
    assert res_pos["ci_upper"] == res_pos2["ci_upper"]

    # 2. Uncertain edge series (mean ~0.05R with high variance, crosses zero)
    uncertain_r = list(np.random.normal(loc=0.02, scale=1.0, size=80))
    res_unc = BootstrapEstimator.calculate_r_expectancy_ci(uncertain_r, n_iterations=2000, random_seed=42)
    assert res_unc["ci_lower"] < 0 < res_unc["ci_upper"]
    assert res_unc["verdict"] == "EDGE UNCERTAIN (95% CI crosses zero)"


def test_multiple_testing_tracker():
    tracker = MultipleTestingTracker()
    tracker.reset()

    exp1 = ResearchExperiment(
        run_id="EXP_1",
        strategy_name="ICT 2022 Model",
        strategy_version="1.1.0",
        symbol="EURUSD",
        timeframe="15m"
    )
    count = tracker.register_experiment(exp1)
    assert count == 1

    status1 = tracker.get_risk_status()
    assert status1["risk_level"] == "LOW"
    assert status1["adjusted_significance_alpha"] == 0.05

    # Simulate 30 hypothesis tests
    for i in range(29):
        tracker.register_experiment(exp1)

    status_high = tracker.get_risk_status()
    assert status_high["total_hypotheses_tested"] == 30
    assert "DATA-MINING RISK" in status_high["risk_level"]
    assert status_high["adjusted_significance_alpha"] < 0.002


def test_scorecard_classifier():
    # 1. Strong Strategy
    is_m = {"total_trades": 120, "expectancy_r": 0.35}
    oos_m = {"total_trades": 60, "expectancy_r": 0.28}
    holdout_m = {"total_trades": 60, "expectancy_r": 0.25}
    boot_ci = {"ci_lower": 0.08, "ci_upper": 0.45, "ci_range_str": "[+0.080R, +0.450R]"}
    
    score_strong = ScorecardClassifier.evaluate_strategy(
        is_m, oos_m, holdout_m, boot_ci, wfo_status="Robust", execution_fragility="LOW", parameter_stability="STABLE"
    )
    assert score_strong["status"] == "STRONG"
    assert score_strong["is_deployable"] is True

    # 2. Failed Strategy (Negative OOS)
    oos_fail = {"total_trades": 60, "expectancy_r": -0.15}
    score_fail = ScorecardClassifier.evaluate_strategy(
        is_m, oos_fail, holdout_m, boot_ci
    )
    assert score_fail["status"] == "FAILED"
    assert score_fail["is_deployable"] is False

    # 3. Insufficient Data
    is_small = {"total_trades": 10}
    oos_small = {"total_trades": 5}
    holdout_small = {"total_trades": 5}
    score_small = ScorecardClassifier.evaluate_strategy(
        is_small, oos_small, holdout_small, boot_ci
    )
    assert score_small["status"] == "INSUFFICIENT DATA"


def test_trade_r_multiple_normalization():
    mock_trades = [
        # Long Trade: Entry 1.0850, SL 1.0800 (Risk = 50 pips), Exit 1.0950 (+100 pips -> +2.0R)
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0950, "pnl": 200.0},
        # Long Loss: Entry 1.0850, SL 1.0800, Exit 1.0800 (-50 pips -> -1.0R)
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0800, "pnl": -100.0},
        # Short Trade: Entry 1.0850, SL 1.0900 (Risk = 50 pips), Exit 1.0700 (+150 pips -> +3.0R)
        {"direction": "SELL", "entry_price": 1.0850, "stop_loss": 1.0900, "exit_price": 1.0700, "pnl": 300.0}
    ]
    df_r = calculate_trade_r_multiples(mock_trades)
    assert len(df_r) == 3
    assert df_r['r_multiple'].iloc[0] == 2.0
    assert df_r['r_multiple'].iloc[1] == -1.0
    assert df_r['r_multiple'].iloc[2] == 3.0


def test_liquidity_source_and_session_analysis():
    mock_trades = [
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0950, "liquidity_type": "BSL_PDH", "session": "LONDON"},
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0900, "liquidity_type": "BSL_PDH", "session": "LONDON"},
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0800, "liquidity_type": "SSL_ASIAN", "session": "NEW_YORK"},
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0950, "liquidity_type": "SSL_ASIAN", "session": "NEW_YORK"}
    ]
    df_r = calculate_trade_r_multiples(mock_trades)
    
    liq_df = analyze_liquidity_sources(df_r)
    assert len(liq_df) == 2
    assert "BSL_PDH" in liq_df['liquidity_type'].values

    session_res = analyze_sessions(df_r)
    assert len(session_res["session_breakdown"]) == 2
    assert len(session_res["liquidity_session_matrix"]) == 2


def test_confluence_calibration_and_quality_curve():
    mock_trades = [
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0950, "confluence_score": 85},
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0900, "confluence_score": 75},
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0800, "confluence_score": 30},
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0800, "confluence_score": 20}
    ]
    df_r = calculate_trade_r_multiples(mock_trades)
    calib = analyze_confluence_calibration(df_r)
    
    assert "quality_curve" in calib
    assert len(calib["quality_curve"]) > 0


def test_execution_sensitivity_stress_and_drift():
    mock_trades = [
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0950},
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0900},
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0850},
        {"direction": "BUY", "entry_price": 1.0850, "stop_loss": 1.0800, "exit_price": 1.0900}
    ]
    
    stress_res = stress_test_execution_sensitivity(mock_trades)
    assert "fragility_rating" in stress_res
    assert len(stress_res["scenarios"]) > 1

    df_r = calculate_trade_r_multiples(mock_trades)
    drift = monitor_expectancy_drift(df_r)
    assert "status" in drift
