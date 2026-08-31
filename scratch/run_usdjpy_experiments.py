"""
Phase 15 — USDJPY Empirical Edge Investigation Script
Executes all 12 controlled ablation experiments (A-L), diagnostic attributions (Liquidity, Session, Direction, Day-of-Week),
MAE/MFE profiling, mechanical baseline comparisons, and execution sensitivity stress testing on USDJPY.
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
from usdjpy_research import USDJPYAblationRunner, USDJPYDiagnosticProfiler

def run_usdjpy_investigation():
    print("=" * 70)
    print("STARTING PHASE 15 — USDJPY DEDICATED ICT/SMC RESEARCH EXPERIMENTS")
    print("=" * 70)

    tracker = research_engine.MultipleTestingTracker()
    tracker.reset()

    # 1. RUN 12 CONTROLLED ABLATION EXPERIMENTS
    print("\n[STEP 1] Executing 12 Controlled SMC/ICT Ablation Experiments on USDJPY (15m)...")
    ablation_results = USDJPYAblationRunner.run_all_ablations(timeframe="15m")
    
    for r in ablation_results:
        print(f"  --> {r['name']} | N={r['trades_N']} | Expectancy={r.get('expectancy_r', 0):+.3f}R | IS={r.get('is_expectancy_r', 0):+.3f}R | OOS Val={r.get('val_expectancy_r', 0):+.3f}R | Holdout={r.get('holdout_expectancy_r', 0):+.3f}R | Status={r.get('status')}")

    # 2. RUN FULL DIAGNOSTIC PROFILING ON BASE ICT 2022 USDJPY
    print("\n[STEP 2] Running Deep Diagnostic Profiling on Base ICT 2022 (USDJPY 15m)...")
    bt_res = backtester.run_backtest(
        symbol="USDJPY",
        timeframe="15m",
        strategy="ICT 2022 Model",
        risk_pct=1.0,
        capital=10000.0,
        slippage=0.005,
        commission_pct=0.005,
        fixed_spread=0.01,
        train_split=0.60
    )

    trades_raw = bt_res.get("trades", [])
    df_r = research_analytics.calculate_trade_r_multiples(trades_raw)

    # Profiling Modules
    liq_df = research_analytics.analyze_liquidity_sources(df_r)
    sess_res = research_analytics.analyze_sessions(df_r)
    time_res = research_analytics.analyze_time_and_day(df_r)
    dir_res = USDJPYDiagnosticProfiler.profile_direction(df_r)
    mae_mfe_res = USDJPYDiagnosticProfiler.profile_mae_mfe(df_r)
    baselines = USDJPYDiagnosticProfiler.compare_mechanical_baselines(df_r)
    stress_res = research_analytics.stress_test_execution_sensitivity(trades_raw)
    conf_res = research_analytics.analyze_confluence_calibration(df_r)
    drift_res = research_analytics.monitor_expectancy_drift(df_r)

    print(f"\n[DIAGNOSTICS SUMMARY]")
    print(f"  Total Trades: {len(df_r)}")
    print(f"  Long Expectancy: {dir_res['long_expectancy_r']:+.3f}R ({dir_res['long_trades']} trades) | Short Expectancy: {dir_res['short_expectancy_r']:+.3f}R ({dir_res['short_trades']} trades)")
    print(f"  Directional Bias: {dir_res['directional_bias_verdict']}")
    print(f"  MAE/MFE Stopped-out after +1R: {mae_mfe_res['reached_1r_stopout_pct']}% ({mae_mfe_res['reached_1r_loss_count']} trades)")
    print(f"  MAE/MFE Stopped-out after +2R: {mae_mfe_res['reached_2r_stopout_pct']}% ({mae_mfe_res['reached_2r_loss_count']} trades)")
    print(f"  Immediate Invalidations: {mae_mfe_res['immediate_invalidations_pct']}%")
    print(f"  Structural Diagnosis: {mae_mfe_res['structural_diagnosis']}")

    # Assemble Final Results Object
    results_payload = {
        "symbol": "USDJPY",
        "timeframe": "15m",
        "total_hypotheses_tested": tracker.total_hypotheses_tested,
        "ablation_experiments": ablation_results,
        "directional_profile": dir_res,
        "mae_mfe_profile": mae_mfe_res,
        "liquidity_attribution": liq_df.to_dict(orient="records") if not liq_df.empty else [],
        "session_breakdown": sess_res.get("session_breakdown", pd.DataFrame()).to_dict(orient="records"),
        "liquidity_session_matrix": sess_res.get("liquidity_session_matrix", pd.DataFrame()).to_dict(orient="records"),
        "day_of_week_breakdown": time_res.get("daily", pd.DataFrame()).to_dict(orient="records"),
        "hourly_breakdown": time_res.get("hourly", pd.DataFrame()).to_dict(orient="records"),
        "mechanical_baselines": baselines,
        "execution_stress_test": stress_res,
        "confluence_calibration": {
            "calibration_status": conf_res.get("calibration_status"),
            "buckets": conf_res.get("buckets", pd.DataFrame()).to_dict(orient="records") if isinstance(conf_res.get("buckets"), pd.DataFrame) else [],
            "quality_curve": conf_res.get("quality_curve", [])
        },
        "expectancy_drift": drift_res
    }

    os.makedirs("scratch", exist_ok=True)
    with open("scratch/usdjpy_empirical_results.json", "w") as f:
        json.dump(results_payload, f, indent=2)

    print("\n" + "=" * 70)
    print("PHASE 15 — USDJPY RESEARCH EXPERIMENTS COMPLETED")
    print(f"Total Hypotheses Logged: {tracker.total_hypotheses_tested}")
    print("Results saved to scratch/usdjpy_empirical_results.json")
    print("=" * 70)

if __name__ == "__main__":
    run_usdjpy_investigation()
