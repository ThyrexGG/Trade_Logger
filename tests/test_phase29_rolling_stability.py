"""
Tests for Phase 29 Rolling Forward & Time-Split Chronological Stability.
Verifies rolling window evaluations, baseline retention, and chronological un-shuffled partitions.
"""

import pytest
from xauusd_forward_stability import RollingStabilityEngine


def test_rolling_stability_engine_windows():
    # 25 trades with positive expectancy
    returns = [1.0, -1.0, 2.0, -1.0, 3.0] * 5  # 25 trades
    res = RollingStabilityEngine.evaluate_rolling_stability(returns, window_sizes=[10, 20, 30])

    assert res["total_trades_n"] == 25
    assert len(res["windows"]) == 3
    
    w10 = res["windows"][0]
    assert w10["window_size"] == 10
    assert w10["status"] == "VALIDATED"
    assert w10["classification"] in {"STABLE", "MILD VARIATION"}

    w30 = res["windows"][2]
    assert w30["window_size"] == 30
    assert w30["status"] == "INSUFFICIENT DATA"


def test_time_split_chronological_stability():
    # 15 trades chronological sequence
    returns = [0.5, 0.5, 0.5, 0.5, 0.5, 1.0, 1.0, 1.0, 1.0, 1.0, 1.5, 1.5, 1.5, 1.5, 1.5]
    split_res = RollingStabilityEngine.evaluate_time_split_stability(returns)

    assert split_res["status"] == "VALIDATED"
    assert len(split_res["periods"]) == 3
    assert split_res["periods"][0]["period"] == "Early"
    assert split_res["periods"][1]["period"] == "Middle"
    assert split_res["periods"][2]["period"] == "Recent"
    assert split_res["overall_stability"] == "IMPROVING"
