"""
Tests for Phase 27 XAUUSD Forward Validation Evidence Engine.
Verifies expectancy calculations, multi-tier bootstrap CIs, historical effect size comparisons,
sequential CUSUM evidence, Monte Carlo forward simulations, and transparent 100-point evidence scoring.
"""

import pytest
import numpy as np
import pandas as pd

from xauusd_forward_evidence import (
    ForwardEvidenceAnalyzer,
    ForwardHistoricalComparator,
    SequentialEvidenceAnalyzer,
    BootstrapStabilityAnalyzer,
    ForwardSamplePlanner,
    ForwardDistributionAnalyzer,
    ForwardMonteCarloEngine,
    RegimeEvidenceAnalyzer,
    ExecutionStrategyDecomposer,
    ForwardEvidenceScorer,
    ResearchDecisionStateClassifier
)


def test_core_statistics_calculation():
    # Test with synthetic returns
    returns = [1.5, -1.0, 2.0, -1.0, 1.8, -1.0, 2.2, -1.0, 1.0, 1.2]
    stats = ForwardEvidenceAnalyzer.calculate_core_statistics(returns)

    assert stats["trades_n"] == 10
    assert stats["expectancy_r"] == pytest.approx(0.57, rel=1e-2)
    assert stats["win_rate_pct"] == 60.0
    assert stats["profit_factor"] > 1.5
    assert stats["max_drawdown_r"] >= 1.0
    assert stats["evidence_tier"] == "INSUFFICIENT DATA"  # N < 30


def test_bootstrap_confidence_intervals_multi_tier():
    # Reproducible seed test
    returns = [1.0, -1.0, 1.5, -1.0, 2.0, 1.0, -1.0, 1.8, -1.0, 1.2] * 4  # 40 trades
    ci_res = ForwardEvidenceAnalyzer.calculate_bootstrap_confidence_intervals(returns, n_bootstrap=1000, seed=42)

    assert ci_res["sample_size"] == 40
    assert ci_res["point_estimate"] > 0
    # Lower bounds: 99% CI lower <= 95% CI lower <= 90% CI lower
    assert ci_res["ci_99"][0] <= ci_res["ci_95"][0] <= ci_res["ci_90"][0]
    # Upper bounds: 90% CI upper <= 95% CI upper <= 99% CI upper
    assert ci_res["ci_90"][1] <= ci_res["ci_95"][1] <= ci_res["ci_99"][1]
    assert ci_res["ci_width_95"] > 0
    assert ci_res["status"] == "VALIDATED"


def test_historical_comparator_and_consistency_bands():
    fwd_stats_consistent = {"trades_n": 55, "expectancy_r": 0.58, "win_rate_pct": 57.0, "profit_factor": 2.30, "max_drawdown_r": 4.10}
    comp_consistent = ForwardHistoricalComparator.compare_against_holdout(fwd_stats_consistent)
    assert comp_consistent["consistency_band"] == "CONSISTENT"
    assert comp_consistent["hist_expectancy"] == 0.637
    assert comp_consistent["abs_expectancy_diff"] == pytest.approx(-0.057, abs=1e-3)

    fwd_stats_warning = {"trades_n": 55, "expectancy_r": -0.15, "win_rate_pct": 38.0, "profit_factor": 0.85, "max_drawdown_r": 8.50}
    comp_warning = ForwardHistoricalComparator.compare_against_holdout(fwd_stats_warning)
    assert comp_warning["consistency_band"] == "WARNING"


def test_sequential_evidence_and_cusum():
    returns = [1.0, -1.0, 2.0, -1.0, 1.5, -1.0, -1.0, -1.0, 2.0, 1.0]
    seq_res = SequentialEvidenceAnalyzer.analyze_sequence(returns)

    assert len(seq_res["cumulative_r_series"]) == 10
    assert seq_res["consecutive_losses_max"] == 3
    assert seq_res["consecutive_wins_max"] == 2
    assert seq_res["status"] == "ACTIVE"


def test_bootstrap_stability_analyzer():
    returns = [1.0, -1.0, 2.0, 1.5, -1.0, 1.0, -1.0, 2.5, -1.0, 1.2, 1.0, -1.0] * 3
    stab = BootstrapStabilityAnalyzer.evaluate_bootstrap_stability(returns, seed=42)

    assert "prob_expectancy_le_zero" in stab
    assert "prob_expectancy_lt_baseline" in stab
    assert "prob_expectancy_ge_baseline" in stab
    assert "disclaimer" in stab
    assert "bootstrap distribution of the observed forward sample" in stab["disclaimer"]


def test_forward_only_monte_carlo():
    returns = [1.5, -1.0, 2.0, -1.0, 1.2, -1.0, 2.5, -1.0, 1.0, 1.8] * 2
    mc = ForwardMonteCarloEngine.run_forward_monte_carlo(returns, n_sims=500, seed=42)

    assert mc["median_cumulative_r"] > 0
    assert mc["p5_cumulative_r"] <= mc["median_cumulative_r"] <= mc["p95_cumulative_r"]
    assert mc["median_max_dd_r"] >= 0
    assert mc["label"] == "FORWARD-SAMPLE RESAMPLING SIMULATION"


def test_regime_evidence_sample_size_protection():
    df_trades = pd.DataFrame([
        {"trade_id": "T1", "session": "London", "realized_r": 1.5},
        {"trade_id": "T2", "session": "London", "realized_r": -1.0},
        {"trade_id": "T3", "session": "New York", "realized_r": 2.0}
    ])
    regimes = RegimeEvidenceAnalyzer.analyze_regime_evidence(df_trades)

    for r in regimes:
        if r["trades_n"] < 15:
            assert r["status"] == "INSUFFICIENT DATA"


def test_forward_evidence_scorer_and_state():
    score_res = ForwardEvidenceScorer.calculate_evidence_score(mode="PAPER")
    assert 0 <= score_res["total_score"] <= 100
    assert len(score_res["breakdown"]) == 8

    state_res = ResearchDecisionStateClassifier.classify_state(mode="PAPER")
    assert state_res["state"] in ["COLLECTING", "EARLY EVIDENCE", "FORWARD CONSISTENT", "FORWARD WATCH", "FORWARD DIVERGENCE", "INTEGRITY BLOCKED"]
