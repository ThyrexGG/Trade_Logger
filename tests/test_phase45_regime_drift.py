"""
Phase 45 — Regime Transition Drift Test Suite
Validates regime shift detection, session concentration analysis, and non-causal attribution.
"""

import pandas as pd
import pytest
from xauusd_continuous_forward_ops import RegimeTransitionDriftDetector


def test_regime_drift_insufficient_data():
    """Validates sample size protection below N = 10."""
    res = RegimeTransitionDriftDetector.evaluate_regime_transition(pd.DataFrame())

    assert "REGIME DATA INSUFFICIENT" in res["drift_state"]
    assert res["total_forward_n"] == 0


def test_regime_drift_balanced_sample():
    """Validates balanced distribution evaluation."""
    data = [
        {"session": "LONDON" if i % 2 == 0 else "NEW YORK", "holiday": "NORMAL", "news_proximity": "STANDARD", "r_multiple": 1.0}
        for i in range(12)
    ]
    df = pd.DataFrame(data)

    res = RegimeTransitionDriftDetector.evaluate_regime_transition(df)
    assert "NO MATERIAL REGIME SHIFT" in res["drift_state"]
    assert res["total_forward_n"] == 12
