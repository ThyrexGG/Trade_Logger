"""
Phase 41 — Independent Metric Reconstruction & Reproducibility Test Suite
Validates that raw trade returns can be independently recomputed with 0 numerical deviation.
"""

from datetime import datetime, timezone, date
import pandas as pd
import pytest
from xauusd_evidence_reproducibility import IndependentMetricReconstructor


def test_reconstruct_metrics_exact_values():
    """Validates mathematical correctness of independent metric recalculation."""
    raw_trades = pd.DataFrame([
        {"signal_id": "T1", "realized_r": 1.5},
        {"signal_id": "T2", "realized_r": -1.0},
        {"signal_id": "T3", "realized_r": 2.0},
        {"signal_id": "T4", "realized_r": -1.0},
    ])

    res = IndependentMetricReconstructor.reconstruct_metrics_from_raw_ledger(raw_trades)

    assert res["trades_n"] == 4
    assert res["win_rate_pct"] == 50.0
    assert res["total_r"] == 1.5
    assert res["expectancy_r"] == 0.375
    assert res["profit_factor"] == 1.75  # 3.5 / 2.0
    assert res["reconstruction_status"] == "RECONSTRUCTION MATCH"


def test_reconstruct_metrics_empty_dataframe():
    """Validates graceful handling of zero trades."""
    empty_df = pd.DataFrame(columns=["signal_id", "realized_r"])
    res = IndependentMetricReconstructor.reconstruct_metrics_from_raw_ledger(empty_df)

    assert res["trades_n"] == 0
    assert res["expectancy_r"] == 0.0
    assert "RECONSTRUCTION MATCH" in res["reconstruction_status"]
