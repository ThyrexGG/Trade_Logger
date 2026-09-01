"""
Phase 44 — Rolling Windows & Expanding Curve Test Suite
Validates rolling metrics across 10, 20, 30, 50, 75, 100 windows and expanding cumulative curve.
"""

import pandas as pd
import pytest
from xauusd_forward_accumulation import (
    RollingWindowAnalysisEngine,
    ExpandingWindowCurveEngine,
)


def test_rolling_windows_structure():
    """Validates rolling windows for empty/insufficient dataset."""
    results = RollingWindowAnalysisEngine.compute_rolling_windows(pd.DataFrame())

    assert len(results) == 6
    window_sizes = [r["window_size"] for r in results]
    assert window_sizes == [10, 20, 30, 50, 75, 100]

    for r in results:
        assert r["has_enough_data"] is False
        assert "INSUFFICIENT DATA" in r["interpretation"]


def test_rolling_windows_with_synthetic_sample():
    """Validates rolling calculation with 15 trades."""
    data = [{"r_multiple": 1.5 if i % 2 == 0 else -1.0, "entry_time": f"2026-09-01T{i:02d}:00:00Z", "signal_id": f"S_{i}"} for i in range(15)]
    df = pd.DataFrame(data)

    results = RollingWindowAnalysisEngine.compute_rolling_windows(df)
    w10 = [r for r in results if r["window_size"] == 10][0]
    assert w10["has_enough_data"] is True
    assert w10["expectancy_r"] is not None
    assert w10["win_rate_pct"] == 50.0

    w20 = [r for r in results if r["window_size"] == 20][0]
    assert w20["has_enough_data"] is False


def test_expanding_curve_generation():
    """Validates expanding cumulative curve without curve-smoothing."""
    data = [{"r_multiple": 1.0, "entry_time": f"2026-09-01T0{i}:00:00Z", "signal_id": f"OBS_{i}"} for i in range(1, 5)]
    df = pd.DataFrame(data)

    curve = ExpandingWindowCurveEngine.compute_expanding_curve(df)
    assert len(curve) == 4
    assert curve[-1]["cumulative_r"] == 4.0
    assert curve[-1]["cumulative_expectancy"] == 1.0
