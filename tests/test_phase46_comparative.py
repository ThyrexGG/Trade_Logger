"""
Phase 46 — Historical vs Forward Comparative Engine Test Suite
Validates side-by-side comparison against locked holdout (N = 82) and consistency classification.
"""

import pandas as pd
import pytest
from xauusd_forward_decision_gate import HistoricalVsForwardComparativeEngine


def test_comparative_engine_empty_dataset():
    """Validates comparative output when forward dataset is empty."""
    res = HistoricalVsForwardComparativeEngine.compare_historical_vs_forward(pd.DataFrame())

    assert res["historical_baseline"]["trades_n"] == 82
    assert res["historical_baseline"]["expectancy_r"] == 0.637
    assert res["forward_stats"]["trades_n"] == 0
    assert "INSUFFICIENT DATA" in res["consistency"]


def test_comparative_engine_synthetic_sample():
    """Validates comparative metrics with sample observations."""
    data = [
        {"r_multiple": 1.5 if i % 2 == 0 else -0.5, "signal_id": f"OBS_{i}"}
        for i in range(12)
    ]
    df = pd.DataFrame(data)

    res = HistoricalVsForwardComparativeEngine.compare_historical_vs_forward(df)
    assert res["forward_stats"]["trades_n"] == 12
    assert res["forward_stats"]["expectancy_r"] == 0.5
    assert "CONSISTENT WITH HISTORICAL" in res["consistency"]
