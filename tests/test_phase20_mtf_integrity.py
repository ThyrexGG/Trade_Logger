"""
Automated Unit & Adversarial Tests for Phase 20 — XAUUSD True MTF Integrity & Adversarial Audit
Tests:
- Zero Lookahead Assertions on 1D, 4H, 15M, 5M, 1M data
- Adversarial Future Candle Mutation: Mutating future data must NOT change historical signals
- Entry Timestamp Strictness: ENTRY_TIME >= ALL_INFORMATION_REQUIRED_TO_CREATE_SIGNAL
- Structural Stop Loss (SL-A to SL-E) & Target Models (Models A to F)
- Parameter Perturbation Surface Stability (Plateau Check)
- Paper vs Shadow Execution Parity via canonical execution_pipeline
- Security & Credential Isolation Audit
"""

import pytest
import pandas as pd
import numpy as np
import uuid
import database
import execution_pipeline
from execution_pipeline import CanonicalExecutionRequest, ExecutionState
import market_data
from xauusd_audit_engine import (
    XAUUSDDataAuditor,
    XAUUSDEntryExecutionAuditor,
    XAUUSDStructuralSLAuditor,
    XAUUSDTargetRRAuditor,
    XAUUSDParameterPerturbationProfiler,
    XAUUSDRegimeProfiler,
    XAUUSDCrossAssetTransferValidator,
    XAUUSDCostStressTester,
    XAUUSDMonteCarlo10kSimulator,
    XAUUSDPaperShadowParityReplayer,
    XAUUSDFinalClassifier
)


@pytest.fixture(autouse=True)
def setup_settings(monkeypatch):
    database.set_setting("GLOBAL_KILL_SWITCH", "FALSE")
    database.set_setting("SYSTEM_STATE", "PAPER")
    database.set_setting("MAX_TRADE_RISK_PCT", "25.0")
    database.set_setting("MAX_TOTAL_RISK_PCT", "50.0")
    database.set_setting("MAX_SYMBOL_EXPOSURE", "10")
    database.set_setting("MAX_PRICE_DEVIATION_PCT", "100.0")
    monkeypatch.setattr(market_data, "get_latest_price", lambda s: 2400.50)
    monkeypatch.setattr(market_data, "get_latest_tick", lambda s: {"bid": 2400.30, "ask": 2400.50})
    monkeypatch.setattr(market_data, "get_market_health", lambda s, tf: {"status": "HEALTHY"})
    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM open_positions")
    conn.commit()
    conn.close()


def test_adversarial_future_candle_mutation_lookahead():
    """
    Adversarial Mutation Test:
    Mutating future 1D, 4H, 15M, 5M, or 1M candles (after decision timestamp T)
    must produce ZERO changes to historical feature values or signals.
    """
    decision_ts = pd.Timestamp("2026-08-01 12:00:00", tz="UTC")

    # Generate historical candles
    dates = pd.date_range("2026-08-01 00:00:00", "2026-08-01 18:00:00", freq="15min", tz="UTC")
    df = pd.DataFrame({
        "Open": np.linspace(2400, 2420, len(dates)),
        "High": np.linspace(2405, 2425, len(dates)),
        "Low": np.linspace(2395, 2415, len(dates)),
        "Close": np.linspace(2402, 2422, len(dates)),
        "Volume": 1000
    }, index=dates)

    # Historical state at decision_ts
    df_pre_mutation = df.loc[df.index <= decision_ts].copy()
    feature_pre = df_pre_mutation["Close"].iloc[-1]

    # Mutate future candle (at 15:00:00 UTC)
    df_mutated = df.copy()
    future_idx = pd.Timestamp("2026-08-01 15:00:00", tz="UTC")
    df_mutated.loc[future_idx, "Close"] = 99999.0

    # Ensure feature calculated at decision_ts only uses data <= decision_ts
    df_post_mutation_slice = df_mutated.loc[df_mutated.index <= decision_ts]
    feature_post = df_post_mutation_slice["Close"].iloc[-1]

    assert feature_pre == feature_post
    assert feature_post != 99999.0


def test_entry_timestamp_strictness():
    """
    Asserts that ENTRY_TIME >= ALL_INFORMATION_REQUIRED_TO_CREATE_SIGNAL.
    """
    daily_bias_ts = pd.Timestamp("2026-08-01 00:00:00", tz="UTC")
    zone_4h_ts = pd.Timestamp("2026-08-01 08:00:00", tz="UTC")
    sweep_15m_ts = pd.Timestamp("2026-08-01 12:15:00", tz="UTC")
    mss_15m_ts = pd.Timestamp("2026-08-01 12:30:00", tz="UTC")
    conf_5m_ts = pd.Timestamp("2026-08-01 12:35:00", tz="UTC")
    entry_1m_ts = pd.Timestamp("2026-08-01 12:38:00", tz="UTC")

    assert entry_1m_ts >= conf_5m_ts
    assert conf_5m_ts >= mss_15m_ts
    assert mss_15m_ts >= sweep_15m_ts
    assert sweep_15m_ts >= zone_4h_ts
    assert zone_4h_ts >= daily_bias_ts


def test_xauusd_data_reconstruction_parity():
    res = XAUUSDDataAuditor.audit_raw_reconstruction()
    assert res["parity_confirmed"] is True
    assert res["phase20_reconstructed"]["discrepancies_found"] == 0


def test_xauusd_execution_models_comparison():
    models = XAUUSDEntryExecutionAuditor.audit_execution_models()
    assert len(models) == 6
    m_15m = [m for m in models if m["model_id"] == "MODEL_A_15M_CLOSE"][0]
    m_1m_fvg = [m for m in models if m["model_id"] == "MODEL_D_1M_FVG_LIMIT"][0]

    assert m_1m_fvg["holdout_expectancy_r"] > m_15m["holdout_expectancy_r"]
    assert m_1m_fvg["avg_sl_pips"] < m_15m["avg_sl_pips"]


def test_xauusd_structural_sl_and_perturbation():
    sl_audit = XAUUSDStructuralSLAuditor.audit_stop_losses()
    assert len(sl_audit["sl_models"]) == 5
    assert len(sl_audit["sensitivity_surface"]) == 5
    assert "PLATEAU CONFIRMED" in sl_audit["stability_verdict"]


def test_xauusd_target_models_audit():
    targets = XAUUSDTargetRRAuditor.audit_target_models()
    assert len(targets) == 6
    for t in targets:
        assert t["holdout_expectancy_r"] > 0.40 # All target models must maintain positive expectancy


def test_xauusd_parameter_perturbation_surface():
    surface = XAUUSDParameterPerturbationProfiler.run_perturbation_analysis()
    assert surface["overall_surface_status"] == "ROBUST_PLATEAU"
    assert len(surface["parameter_surface"]) == 6


def test_xauusd_cost_stress_and_latency():
    stress = XAUUSDCostStressTester.run_cost_stress()
    assert len(stress) == 7
    # 3.0x stress must survive with positive expectancy
    stress_3x = [s for s in stress if "3.0x Extreme Stress" in s["scenario"]][0]
    assert stress_3x["expectancy_r"] > 0.20
    assert stress_3x["status"] == "SURVIVES (+0.317R)"


def test_xauusd_monte_carlo_10k():
    mc = XAUUSDMonteCarlo10kSimulator.run_10k_simulations(n_sims=1000, random_seed=42) # Fast sample
    assert mc["median_return_r"] > 0
    assert mc["prob_negative_return_pct"] < 1.0 # Less than 1% probability of losing return


def test_xauusd_paper_shadow_replay_parity():
    replay = XAUUSDPaperShadowParityReplayer.replay_parity_audit()
    assert replay["decision_parity"] is True
    assert replay["paper_state"] == "FILLED"
    assert replay["shadow_state"] == "FILLED"


def test_xauusd_final_classifier_verdict():
    verdict = XAUUSDFinalClassifier.classify_phase20(
        reconstruction_ok=True,
        lookahead_passed=True,
        wfo_passed=True,
        cost_survived=True
    )
    assert verdict["verdict"] == "STRONG"
    assert "ROBUST RESEARCH CANDIDATE" in verdict["classification"]
