"""
Unit Tests for Phase 22 — XAUUSD Drift Detection & Drawdown Monitoring
Tests:
- Drawdown classification against historical 95th-percentile stress
- Distribution drift detection on MAE / MFE excursion profiles
- Multi-component edge consistency scoring (0 to 100)
"""

import pytest
import numpy as np
import pandas as pd
from xauusd_drift_detector import XAUUSDDriftDetector


def test_drawdown_classification_thresholds():
    # Normal <= 4.0R
    d1 = XAUUSDDriftDetector.evaluate_drawdown_status(2.50)
    assert d1["status"] == "NORMAL"
    assert d1["color"] == "#00ffcc"

    # Elevated 4.0R to 7.15R
    d2 = XAUUSDDriftDetector.evaluate_drawdown_status(5.80)
    assert d2["status"] == "ELEVATED"
    assert d2["color"] == "#bef264"

    # Stress 7.15R to 12.00R
    d3 = XAUUSDDriftDetector.evaluate_drawdown_status(8.50)
    assert d3["status"] == "STRESS"
    assert d3["color"] == "#f59e0b"

    # Severe > 12.00R
    d4 = XAUUSDDriftDetector.evaluate_drawdown_status(14.20)
    assert d4["status"] == "SEVERE"
    assert d4["color"] == "#ff5555"


def test_distribution_drift_evaluation():
    dist = XAUUSDDriftDetector.evaluate_distribution_drift(mode="PAPER")
    assert "distribution_status" in dist
    assert "verdict" in dist
    assert dist["distribution_status"] in ["INSUFFICIENT DATA", "DISTRIBUTIONALLY CONSISTENT", "DISTRIBUTIONALLY DRIFTING"]


def test_edge_consistency_score_components():
    score_res = XAUUSDDriftDetector.calculate_edge_consistency_score(mode="PAPER")
    assert "total_score" in score_res
    assert 0.0 <= score_res["total_score"] <= 100.0
    assert "components" in score_res
    assert len(score_res["components"]) == 5
    assert "tier" in score_res
