"""
Phase 18 — USDJPY Regime-Conditional Edge Validation Batch Runner
Executes:
- Phase 17 mathematical trade audit
- Subgroup sample size & statistical distribution audit
- Hypothesis 1 (Tuesday/Wednesday vs Mon/Thu/Fri fixed momentum model)
- Hypothesis 2 (Fixed holding periods: 4, 8, 12, 16, 24, 32 bars)
- Hypothesis 3 (Predeclared Tue/Wed + 16-bar combination)
- 5,000-iteration Permutation / Randomization Test (empirical p-value)
- Rolling Walk-Forward Analysis (4 windows)
- Regime Transition Antecedents (Mon->Tue, Tue->Wed, Fri->Mon)
- Multi-dimensional profiling (Volatility Quintiles, Sessions, Direction)
- Cumulative Multiple Testing Accounting (Phases 14-18)
- Execution Cost Stress & Baseline Complexity Matrix
- 5,000-run Monte Carlo Simulation
- Final Scientific Classification
"""

import os
import sys
import json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import backtester
import research_engine
import research_analytics
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


def run_phase18_validation():
    print("=" * 78)
    print("STARTING PHASE 18 — USDJPY REGIME-CONDITIONAL EDGE VALIDATION")
    print("=" * 78)

    # 1. AUDIT PHASE 17 MATHEMATICAL CALCULATIONS
    print("\n[STEP 1] Auditing Phase 17 Trade Calculations & Timestamps...")
    bt_res = backtester.run_backtest(
        symbol="USDJPY",
        timeframe="15m",
        strategy="Trend Continuation",
        risk_pct=1.0,
        capital=10000.0,
        slippage=0.005,
        commission_pct=0.005,
        fixed_spread=0.01,
        train_split=0.60
    )
    raw_trades = bt_res.get("trades", [])
    math_audit = USDJPYPhase17Auditor.audit_trade_calculations(raw_trades)
    print(f"  Audit Passed: {math_audit['audit_passed']} | Trades Checked: {math_audit['total_trades_checked']} | Math Errors: {math_audit['math_errors_count']}")

    # 2. AUDIT WEEKDAY MOMENTUM HYPOTHESIS (H1)
    print("\n[STEP 2] Auditing Weekday Momentum Distributions (H1)...")
    df_r = research_analytics.calculate_trade_r_multiples(raw_trades)
    weekday_res = USDJPYFixedMomentumModel.evaluate_weekday_hypothesis(df_r)
    print(f"  Tuesday Expectancy: {weekday_res['tuesday']['expectancy_r']:+.3f}R (N={weekday_res['tuesday']['trades_N']}, 95% CI: {weekday_res['tuesday']['bootstrap_ci']})")
    print(f"  Wednesday Expectancy: {weekday_res['wednesday']['expectancy_r']:+.3f}R (N={weekday_res['wednesday']['trades_N']}, 95% CI: {weekday_res['wednesday']['bootstrap_ci']})")
    print(f"  Tue/Wed Combined: {weekday_res['tue_wed_combined']['expectancy_r']:+.3f}R (N={weekday_res['tue_wed_combined']['trades_N']}, 95% CI: {weekday_res['tue_wed_combined']['bootstrap_ci']})")
    print(f"  Mon/Thu/Fri Combined: {weekday_res['other_days_combined']['expectancy_r']:+.3f}R (N={weekday_res['other_days_combined']['trades_N']})")
    print(f"  Observed Weekday Delta: {weekday_res['weekday_delta_r']:+.3f}R")

    # 3. AUDIT FIXED HOLDING-PERIOD HYPOTHESIS (H2)
    print("\n[STEP 3] Evaluating Fixed Holding-Period Durations (H2)...")
    holding_res = USDJPYFixedHoldingTester.test_fixed_holding_durations()
    for h in holding_res:
        print(f"  --> {h['duration_str']} | N={h['trades_N']} | Expectancy={h['expectancy_r']:+.3f}R | WinRate={h['win_rate_pct']}% | CI={h['bootstrap_ci']} | Verdict={h['verdict']}")

    # 4. PREDECLARED COMBINATION HYPOTHESIS (H3)
    print("\n[STEP 4] Evaluating Predeclared Combination (H3)...")
    comb_res = USDJPYCombinationTester.evaluate_combination()
    cand = comb_res["candidate"]
    print(f"  Candidate ({cand['name']}): N={cand['trades_N']} | Expectancy={cand['expectancy_r']:+.3f}R | Holdout={cand['holdout_expectancy_r']:+.3f}R | 95% CI={cand['bootstrap_ci']}")
    print(f"  Incremental Weekday Edge vs Unconditional Baseline: {comb_res['incremental_weekday_edge_r']:+.3f}R")

    # 5. 5,000-ITERATION PERMUTATION / RANDOMIZATION TEST
    print("\n[STEP 5] Running 5,000-Iteration Permutation Test for Weekday Clustering...")
    perm_res = USDJPYPermutationTester.run_permutation_test(n_iterations=5000, random_seed=42)
    print(f"  Observed Delta: {perm_res['observed_delta_r']:+.3f}R | Permuted 95th Pct: {perm_res['permuted_95th_percentile_r']:+.3f}R")
    print(f"  Empirical p-value: {perm_res['empirical_p_value']:.4f} | Verdict: {perm_res['statistical_verdict']}")

    # 6. ROLLING WALK-FORWARD VALIDATION
    print("\n[STEP 6] Running Rolling Walk-Forward Analysis...")
    wfo_res = USDJPYWalkForwardValidator.run_walk_forward()
    print(f"  Profitable Windows: {wfo_res['profitable_windows']}/{wfo_res['total_windows']} ({wfo_res['window_profitability_pct']}%) | Median OOS E[R]: {wfo_res['median_oos_expectancy_r']:+.3f}R | Worst: {wfo_res['worst_oos_expectancy_r']:+.3f}R")

    # 7. REGIME TRANSITION ANTECEDENT ANALYSIS
    print("\n[STEP 7] Evaluating Regime Transition Antecedents (No Lookahead)...")
    transition_res = USDJPYRegimeTransitionAnalyzer.analyze_transitions()
    for t in transition_res:
        print(f"  --> {t['transition']} (N={t['sample_N']}): {t['expectancy_r']:+.3f}R (WR: {t['continuation_win_rate_pct']}%) | Verdict: {t['verdict']}")

    # 8. MULTI-DIMENSIONAL INTERACTIONS
    print("\n[STEP 8] Profiling Volatility, Session & Direction Interactions...")
    interactions_res = USDJPYVolatilitySessionDirectionProfiler.profile_interactions()

    # 9. CUMULATIVE MULTIPLE TESTING ACCOUNTING
    print("\n[STEP 9] Cumulative Multiple Testing Audit across Phases 14-18...")
    mt_res = USDJPYCumulativeMultipleTesting.audit_cumulative_hypotheses()
    print(f"  Total Hypotheses Tested: {mt_res['total_cumulative_hypotheses']} | Aggregate Penalty: {mt_res['multiple_testing_penalty_r']:+.3f}R")

    # 10. COST STRESS & COMPLEXITY PENALTY
    print("\n[STEP 10] Testing Execution Cost Sensitivity & Baseline Complexity...")
    stress_res = USDJPYCandidateCostStressTester.run_stress_test(base_expectancy_r=cand["expectancy_r"])
    complexity_res = USDJPYBaselineComplexityComparator.compare_and_penalize()

    # 11. 5,000-RUN MONTE CARLO SIMULATION
    print("\n[STEP 11] Running 5,000-Run Monte Carlo Simulation...")
    mc_res = USDJPYMonteCarloSimulator.run_monte_carlo(n_simulations=5000, random_seed=42)
    print(f"  Monte Carlo Median E[R]: {mc_res['median_expectancy_r']:+.3f}R | 5th-95th Pct: [{mc_res['percentile_5th_expectancy_r']:+.3f}R, {mc_res['percentile_95th_expectancy_r']:+.3f}R]")
    print(f"  Prob of Negative Return: {mc_res['probability_negative_total_return_pct']}% | Prob of 20R Drawdown: {mc_res['probability_20r_drawdown_pct']}% | 95th Pct Max DD: {mc_res['percentile_95th_max_drawdown_r']}R")

    # 12. FINAL SCIENTIFIC CLASSIFICATION
    print("\n[STEP 12] Determining Final Scientific Classification...")
    final_verdict = USDJPYFinalClassifier.determine_final_classification(
        sample_N=cand["trades_N"],
        holdout_exp_r=cand["holdout_expectancy_r"],
        boot_ci_lower=cand["ci_lower"],
        wfo_profitable_pct=wfo_res["window_profitability_pct"],
        p_value=perm_res["empirical_p_value"],
        cumulative_hypotheses=mt_res["total_cumulative_hypotheses"]
    )
    print(f"  FINAL VERDICT: {final_verdict['status']}")
    for r in final_verdict["score_reasons"]:
        print(f"    - {r}")

    # SAVE AUDIT PAYLOAD
    results_payload = {
        "phase": 18,
        "symbol": "USDJPY",
        "timeframe": "15m",
        "mathematical_audit": math_audit,
        "weekday_momentum_h1": weekday_res,
        "holding_durations_h2": holding_res,
        "combination_h3": comb_res,
        "permutation_test": perm_res,
        "walk_forward": wfo_res,
        "regime_transitions": transition_res,
        "interactions": interactions_res,
        "cumulative_multiple_testing": mt_res,
        "cost_stress": stress_res,
        "baseline_complexity": complexity_res,
        "monte_carlo": mc_res,
        "final_classification": final_verdict
    }

    os.makedirs("scratch", exist_ok=True)
    with open("scratch/usdjpy_conditional_validation_results.json", "w") as f:
        json.dump(results_payload, f, indent=2)

    print("\n" + "=" * 78)
    print("PHASE 18 VALIDATION COMPLETE — RESULTS SAVED TO scratch/usdjpy_conditional_validation_results.json")
    print("=" * 78)


if __name__ == "__main__":
    run_phase18_validation()
