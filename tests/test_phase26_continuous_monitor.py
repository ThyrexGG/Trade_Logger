"""
Unit tests for Phase 26 — Continuous Forward Monitor, CUSUM Drift Detector, and Delta Evaluations.
"""

import pytest
from xauusd_continuous_monitor import XAUUSDContinuousMonitor, CUSUMDriftDetector


def test_cusum_drift_detector_normal_variation():
    # Sequence of returns close to baseline +0.637R
    returns = [0.8, 0.5, 1.2, -1.0, 2.0, 0.6, 0.4, 0.7, -1.0, 1.5, 0.6, 0.7, 0.5, 0.8, 0.9, 0.6]
    res = CUSUMDriftDetector.detect_cusum_drift(returns)
    assert res["trades_n"] == len(returns)
    assert res["status"] in ["NORMAL VARIATION", "EARLY WARNING"]
    assert "rolling_cusum_series" in res
    assert len(res["rolling_cusum_series"]) == len(returns)


def test_cusum_drift_detector_persistent_degradation():
    # Sequence of losses creating cumulative drag <= -7.0R
    returns = [-1.0] * 20
    res = CUSUMDriftDetector.detect_cusum_drift(returns)
    assert res["trades_n"] == 20
    assert res["status"] == "PERSISTENT DEGRADATION"
    assert res["cumulative_deviation_r"] < -7.0
    assert "critical threshold" in res["explanation"].lower()


def test_cusum_drift_detector_insufficient_data():
    returns = [0.5, -1.0, 2.0]
    res = CUSUMDriftDetector.detect_cusum_drift(returns)
    assert res["status"] == "INSUFFICIENT DATA"


def test_continuous_monitor_telemetry_fields():
    tel = XAUUSDContinuousMonitor.get_full_monitoring_telemetry(mode="PAPER")
    assert "trades_N" in tel
    assert "expectancy_r" in tel
    assert "win_rate_pct" in tel
    assert "rolling_20_exp_r" in tel
    assert "rolling_30_exp_r" in tel
    assert "rolling_50_exp_r" in tel
    assert "hist_exp_diff" in tel
    assert "cusum" in tel


def test_evaluate_what_changed_deltas():
    curr = {
        "trades_N": 35,
        "expectancy_r": 0.55,
        "win_rate_pct": 57.1,
        "max_drawdown_r": 3.2,
        "timeout_rate_pct": 10.0
    }
    prev = {
        "trades_N": 30,
        "expectancy_r": 0.50,
        "win_rate_pct": 56.6,
        "max_drawdown_r": 3.0,
        "timeout_rate_pct": 9.5
    }
    delta = XAUUSDContinuousMonitor.evaluate_what_changed(curr, prev)
    assert "5 NEW FORWARD OBSERVATIONS" in delta["status"]
    assert delta["deltas"]["new_trades"] == 5
    assert delta["deltas"]["expectancy_change"] == 0.05
