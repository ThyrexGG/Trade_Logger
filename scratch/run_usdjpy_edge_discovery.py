"""
Phase 17 — USDJPY Edge Discovery Empirical Research Runner
Executes:
- 27 Mechanical Strategies & Baselines across 60% Train / 20% Val / 20% Final Holdout
- Regime Classification & Performance Matrix (Trending vs Ranging, Volatility Percentiles)
- Deep MAE/MFE Excursion Profiling & Holding-Time Duration Buckets
- Day-of-Week Breakdown & Session Transition Matrices
- Trend Persistence Analysis (+4, +8, +16, +32 bars)
- Complexity Penalty & Final Scorecard Generation
"""

import os
import sys
import json
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import backtester
import research_engine
import research_analytics
from usdjpy_edge_discovery import (
    USDJPYRegimeEngine,
    USDJPYMechanicalExperimentRunner,
    USDJPYDeepExcursionAnalyzer,
    USDJPYHoldingTimeAnalyzer,
    USDJPYDayOfWeekAnalyzer,
    USDJPYTrendPersistenceAnalyzer
)


def run_phase17_edge_discovery():
    print("=" * 75)
    print("STARTING PHASE 17 — USDJPY EDGE DISCOVERY LAB (REGIMES, SESSIONS & BASELINES)")
    print("=" * 75)

    tracker = research_engine.MultipleTestingTracker()
    tracker.reset()

    # 1. RUN 27 MECHANICAL STRATEGIES & BASELINES
    print("\n[STEP 1] Running 27 Mechanical Strategy & Baseline Experiments on USDJPY (15m)...")
    exp_results = USDJPYMechanicalExperimentRunner.run_all_experiments(timeframe="15m")

    for r in exp_results:
        print(f"  --> {r['name']} [{r['category']}] | N={r['trades_N']} | Expectancy={r.get('expectancy_r', 0):+.3f}R | Train={r.get('is_expectancy_r', 0):+.3f}R | Val={r.get('val_expectancy_r', 0):+.3f}R | Holdout={r.get('holdout_expectancy_r', 0):+.3f}R | Score={r.get('research_score', 0):+.3f} | Status={r.get('status')}")

    # 2. RUN DEEP REGIME & EXCURSION PROFILING
    print("\n[STEP 2] Running Deep Regime, Excursion & Persistence Profiling...")
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

    trades_raw = bt_res.get("trades", [])
    df_r = research_analytics.calculate_trade_r_multiples(trades_raw)

    excursion_res = USDJPYDeepExcursionAnalyzer.profile_deep_excursion(df_r)
    holding_time_res = USDJPYHoldingTimeAnalyzer.profile_holding_time(df_r)
    dow_res = USDJPYDayOfWeekAnalyzer.profile_days_and_transitions(df_r)
    persistence_map = USDJPYTrendPersistenceAnalyzer.profile_trend_persistence()
    stress_res = research_analytics.stress_test_execution_sensitivity(trades_raw)

    # Summary
    print(f"\n[EXCURSION & DURATION SUMMARY]")
    print(f"  Reached +0.5R: {excursion_res['pct_reached_0_5r']}% | Reached +1.0R: {excursion_res['pct_reached_1_0r']}% | Reached +2.0R: {excursion_res['pct_reached_2_0r']}%")
    print(f"  Immediate Invalidations: {excursion_res['immediate_invalidations_pct']}%")

    results_payload = {
        "symbol": "USDJPY",
        "timeframe": "15m",
        "total_hypotheses_tested": tracker.total_hypotheses_tested,
        "experiments": exp_results,
        "deep_excursion": excursion_res,
        "holding_time_buckets": holding_time_res,
        "day_of_week_and_transitions": dow_res,
        "trend_persistence_map": persistence_map,
        "execution_stress_test": stress_res
    }

    os.makedirs("scratch", exist_ok=True)
    with open("scratch/usdjpy_edge_discovery_results.json", "w") as f:
        json.dump(results_payload, f, indent=2)

    print("\n" + "=" * 75)
    print("PHASE 17 — USDJPY EDGE DISCOVERY COMPLETED")
    print(f"Total Hypotheses Logged: {tracker.total_hypotheses_tested}")
    print("Results saved to scratch/usdjpy_edge_discovery_results.json")
    print("=" * 75)


if __name__ == "__main__":
    run_phase17_edge_discovery()
