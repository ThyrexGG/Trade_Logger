"""
Phase 49 — Tests for Forward Metrics Calculations & Metric Maturity Classification
"""

import pytest
import pandas as pd
from xauusd_forward_statistical_monitoring import ForwardMetricsEngine


def test_metrics_empty_df():
    """Validates metrics on empty dataframe returns zero metrics with truthful interpretation."""
    res = ForwardMetricsEngine.calculate_forward_metrics(pd.DataFrame())
    assert res["trades_n"] == 0
    assert res["win_rate_pct"] == 0.0
    assert res["expectancy_r"] == 0.0
    assert res["maturity_tier"] == "NO_FORWARD_DATA"
    assert "No synthetic metrics" in res["interpretation"]


def test_metrics_small_sample_tier():
    """Validates small sample (N=2) yields OBSERVED_METRIC tier."""
    sample_df = pd.DataFrame([
        {"signal_id": "SIG_1", "r_multiple": 2.0, "status": "COMPLETED"},
        {"signal_id": "SIG_2", "r_multiple": -1.0, "status": "COMPLETED"}
    ])
    res = ForwardMetricsEngine.calculate_forward_metrics(sample_df)
    assert res["trades_n"] == 2
    assert res["win_rate_pct"] == 50.0
    assert res["expectancy_r"] == 0.5
    assert res["profit_factor"] == 2.0
    assert res["maturity_tier"] == "OBSERVED_METRIC"
    assert "INSUFFICIENT SAMPLE" in res["interpretation"]


def test_metrics_large_sample_tier():
    """Validates N=100 sample yields DECISION_ELIGIBLE_METRIC tier."""
    r_list = [2.0 if i % 2 == 0 else -1.0 for i in range(100)]
    df_100 = pd.DataFrame([{"signal_id": f"SIG_{i}", "r_multiple": r_list[i], "status": "COMPLETED"} for i in range(100)])
    res = ForwardMetricsEngine.calculate_forward_metrics(df_100)
    assert res["trades_n"] == 100
    assert res["maturity_tier"] == "DECISION_ELIGIBLE_METRIC"
