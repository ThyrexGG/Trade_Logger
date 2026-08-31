"""
Automated Unit Tests for Phase 18 — USDJPY Regime-Conditional Edge Validation
Tests:
- USDJPYPhase17Auditor mathematical and timestamp integrity
- USDJPYSubgroupAuditor statistical calculations (N, wins/losses, CI, Drawdown, Streaks)
- USDJPYFixedMomentumModel weekday evaluation
- USDJPYFixedHoldingTester durations
- USDJPYCombinationTester metrics
- USDJPYPermutationTester reproducibility & empirical p-value
- USDJPYWalkForwardValidator window stability
- USDJPYRegimeTransitionAnalyzer antecedent tests
- USDJPYVolatilitySessionDirectionProfiler interactions
- USDJPYCumulativeMultipleTesting counter
- USDJPYCandidateCostStressTester friction degradation
- USDJPYBaselineComplexityComparator incremental edge
- USDJPYMonteCarloSimulator distribution & ruin metrics
- USDJPYFinalClassifier objective criteria
"""

import pytest
import numpy as np
import pandas as pd
from usdjpy_conditional_validation import (
    USDJPYPhase17Auditor,
    USDJPYSubgroupAuditor,
    USDJPYFixedMomentumModel,
    USDJPYFixedHoldingTester,
    USDJPYCombinationTester,
    USDJPYPermutationTester,
    USDJPYWalkForwardValidator,
    USDJPYRegimeTransitionAnalyzer,
    USDJPYVolatilitySessionDirectionProfiler,
    USDJPYCumulativeMultipleTesting,
    USDJPYCandidateCostStressTester,
    USDJPYBaselineComplexityComparator,
    USDJPYMonteCarloSimulator,
    USDJPYFinalClassifier
)


def test_phase17_mathematical_auditor():
    mock_valid_trades = [
        {"direction": "BUY", "entry_price": 150.00, "stop_loss": 149.00, "exit_price": 152.00, "entry_time": "2026-08-01 08:00:00", "exit_time": "2026-08-01 12:00:00"},
        {"direction": "SELL", "entry_price": 152.00, "stop_loss": 153.00, "exit_price": 151.00, "entry_time": "2026-08-02 08:00:00", "exit_time": "2026-08-02 12:00:00"}
    ]
    audit_res = USDJPYPhase17Auditor.audit_trade_calculations(mock_valid_trades)
    assert audit_res["audit_passed"] is True
    assert audit_res["math_errors_count"] == 0
    assert audit_res["timestamp_anomalies_count"] == 0


def test_subgroup_auditor_calculations():
    sample_r = [1.0, -1.0, 2.0, -1.0, 1.5, -0.5, 0.0, 2.5, -1.0, 1.0]
    res = USDJPYSubgroupAuditor.audit_subgroup("Test Group", sample_r)
    assert res["trades_N"] == 10
    assert res["wins"] == 5
    assert res["losses"] == 5
    assert res["win_rate_pct"] == 50.0
    assert res["expectancy_r"] == pytest.approx(0.45, abs=0.01)
    assert res["max_drawdown_r"] > 0
    assert res["max_losing_streak"] >= 1


def test_fixed_momentum_model_and_holding():
    df_empty = pd.DataFrame()
    wd_res = USDJPYFixedMomentumModel.evaluate_weekday_hypothesis(df_empty)
    assert "tuesday" in wd_res
    assert "wednesday" in wd_res
    assert "tue_wed_combined" in wd_res
    assert wd_res["weekday_delta_r"] > 0

    durations = USDJPYFixedHoldingTester.test_fixed_holding_durations()
    assert len(durations) == 6
    assert any(d["holding_bars"] == 16 for d in durations)


def test_combination_and_permutation_reproducibility():
    comb = USDJPYCombinationTester.evaluate_combination()
    assert "candidate" in comb
    assert comb["incremental_weekday_edge_r"] > 0

    perm_res1 = USDJPYPermutationTester.run_permutation_test(n_iterations=500, random_seed=42)
    perm_res2 = USDJPYPermutationTester.run_permutation_test(n_iterations=500, random_seed=42)
    assert perm_res1["empirical_p_value"] == perm_res2["empirical_p_value"]
    assert "statistical_verdict" in perm_res1


def test_walk_forward_and_transitions():
    wfo = USDJPYWalkForwardValidator.run_walk_forward()
    assert wfo["total_windows"] == 4
    assert wfo["profitable_windows"] >= 3

    transitions = USDJPYRegimeTransitionAnalyzer.analyze_transitions()
    assert len(transitions) == 4
    for t in transitions:
        assert "transition" in t
        assert "condition" in t
        assert "expectancy_r" in t


def test_volatility_session_direction_interactions():
    prof = USDJPYVolatilitySessionDirectionProfiler.profile_interactions()
    assert "volatility_interaction" in prof
    assert "session_interaction" in prof
    assert "directional_interaction" in prof
    assert len(prof["volatility_interaction"]) == 5
    assert len(prof["session_interaction"]) == 4
    assert len(prof["directional_interaction"]) == 4


def test_multiple_testing_counter_and_cost_stress():
    mt = USDJPYCumulativeMultipleTesting.audit_cumulative_hypotheses()
    assert mt["total_cumulative_hypotheses"] == 76
    assert mt["multiple_testing_penalty_r"] > 0

    stress = USDJPYCandidateCostStressTester.run_stress_test(base_expectancy_r=0.243)
    assert len(stress) == 5
    assert stress[0]["expectancy_r"] == 0.243


def test_complexity_comparator_and_monte_carlo():
    comp = USDJPYBaselineComplexityComparator.compare_and_penalize()
    assert comp["candidate_incremental_edge_r"] > 0
    assert len(comp["baseline_matrix"]) == 8

    mc = USDJPYMonteCarloSimulator.run_monte_carlo(n_simulations=500, random_seed=42)
    assert mc["n_simulations"] == 500
    assert mc["median_expectancy_r"] > 0
    assert mc["probability_negative_total_return_pct"] >= 0.0


def test_final_classifier_verdict():
    # Post-hoc high multiple testing scenario with positive holdout
    res = USDJPYFinalClassifier.determine_final_classification(
        sample_N=70,
        holdout_exp_r=0.225,
        boot_ci_lower=0.048,
        wfo_profitable_pct=75.0,
        p_value=0.012,
        cumulative_hypotheses=76
    )
    assert res["status"] == "PROMISING BUT UNCONFIRMED"

    # Small sample size
    res_small = USDJPYFinalClassifier.determine_final_classification(
        sample_N=15,
        holdout_exp_r=0.40,
        boot_ci_lower=-0.10,
        wfo_profitable_pct=50.0,
        p_value=0.08,
        cumulative_hypotheses=76
    )
    assert res_small["status"] == "INSUFFICIENT DATA"
