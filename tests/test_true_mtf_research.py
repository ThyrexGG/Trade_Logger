"""
Automated Unit Tests for Phase 19 — True Multi-Timeframe ICT/SMC Research Engine & Best-Asset Discovery
Tests:
- TrueMTFStateMachine 18-state lifecycle & transition rules
- TrueMTFDataLoader lookahead leak assertions & future timestamp rejection
- TrueMTFExecutionComparer 1M vs 5M vs 15M execution metrics
- CrossAssetDiscoveryRunner cross-asset leaderboard ranking
- TrueMTFScorecardClassifier selection logic
"""

import pytest
import pandas as pd
from true_mtf_engine import (
    TrueMTFStateMachine,
    TrueMTFDataLoader,
    TrueMTFStrategyEngine,
    TrueMTFExecutionComparer,
    CrossAssetDiscoveryRunner,
    TrueMTFScorecardClassifier
)


def test_true_mtf_state_machine_valid_transitions():
    sm = TrueMTFStateMachine()
    assert sm.state == "NO_SETUP"

    # Valid progression
    assert sm.transition_to("BIAS_ESTABLISHED") is True
    assert sm.transition_to("HTF_ZONE_IDENTIFIED") is True
    assert sm.transition_to("LIQUIDITY_TARGET_IDENTIFIED") is True
    assert sm.transition_to("15M_SETUP_ARMED") is True
    assert sm.transition_to("15M_LIQUIDITY_SWEPT") is True
    assert sm.transition_to("15M_STRUCTURE_CONFIRMED") is True
    assert sm.transition_to("5M_CONFIRMATION_PENDING") is True
    assert sm.transition_to("5M_CONFIRMED") is True
    assert sm.transition_to("1M_ENTRY_ARMED") is True
    assert sm.transition_to("ENTRY_TRIGGERED") is True
    assert sm.transition_to("ORDER_FILLED") is True
    assert sm.transition_to("TRADE_ACTIVE") is True
    assert sm.transition_to("TP1_HIT") is True
    assert sm.transition_to("TP2_HIT") is True

    # Invalid backward transition
    assert sm.transition_to("BIAS_ESTABLISHED") is False


def test_true_mtf_lookahead_leak_prevention():
    exec_ts = pd.Timestamp("2026-08-01 12:00:00", tz="UTC")
    valid_feature_ts = pd.Timestamp("2026-08-01 11:45:00", tz="UTC")
    future_feature_ts = pd.Timestamp("2026-08-01 12:15:00", tz="UTC")

    # Valid check
    assert TrueMTFDataLoader.verify_no_lookahead(exec_ts, valid_feature_ts, "15M") is True

    # Future feature must raise ValueError with LOOKAHEAD_LEAK_DETECTED
    with pytest.raises(ValueError, match="LOOKAHEAD_LEAK_DETECTED"):
        TrueMTFDataLoader.verify_no_lookahead(exec_ts, future_feature_ts, "15M")


def test_true_mtf_execution_comparer():
    comparisons = TrueMTFExecutionComparer.compare_execution_timeframes(symbol="XAUUSD")
    assert len(comparisons) == 3

    m_15m = [c for c in comparisons if c["execution_tf"] == "15m"][0]
    m_5m = [c for c in comparisons if c["execution_tf"] == "5m"][0]
    m_1m = [c for c in comparisons if c["execution_tf"] == "1m"][0]

    # 1M execution should have lower SL distance and higher R-expectancy than 15M
    assert m_1m["avg_sl_distance_pips"] < m_15m["avg_sl_distance_pips"]
    assert m_1m["expectancy_r"] > m_15m["expectancy_r"]
    assert m_1m["avg_mfe_r"] > m_15m["avg_mfe_r"]


def test_cross_asset_discovery_catalog_and_ranking():
    leaderboard = CrossAssetDiscoveryRunner.run_cross_asset_discovery()
    assert len(leaderboard) == 16

    # Verify rank ordering
    for i in range(len(leaderboard) - 1):
        assert leaderboard[i]["research_score"] >= leaderboard[i + 1]["research_score"]

    # Gold (XAUUSD) should rank in the top tier
    top_assets = [row["asset"] for row in leaderboard[:3]]
    assert "XAUUSD" in top_assets


def test_true_mtf_scorecard_best_candidate_selection():
    mock_leaderboard = [
        {"asset": "XAUUSD", "status": "STRONG", "holdout_expectancy_r": +0.412, "bootstrap_ci": "[+0.252R, +0.592R]", "research_score": +0.232},
        {"asset": "EURUSD", "status": "STRONG", "holdout_expectancy_r": +0.228, "bootstrap_ci": "[+0.068R, +0.408R]", "research_score": +0.048},
        {"asset": "USDJPY", "status": "FAILED", "holdout_expectancy_r": -0.065, "bootstrap_ci": "[-0.225R, +0.115R]", "research_score": -0.245}
    ]
    res = TrueMTFScorecardClassifier.select_best_candidate(mock_leaderboard)
    assert res["verdict"] == "ROBUST RESEARCH CANDIDATE"
    assert res["best_candidate"]["asset"] == "XAUUSD"
