"""
Phase 54 — Tests for Historical Holdout vs Genuine Forward Separation
"""

import pytest
from forward_evidence_cockpit import ForwardEvidenceCockpit
from xauusd_forward_statistical_monitoring import HISTORICAL_BASELINE


def test_historical_baseline_unpooled_invariants():
    assert HISTORICAL_BASELINE["trades_n"] == 82
    assert HISTORICAL_BASELINE["expectancy_r"] == 0.637
    assert HISTORICAL_BASELINE["win_rate_pct"] == 58.6
    assert HISTORICAL_BASELINE["profit_factor"] == 2.52
    assert HISTORICAL_BASELINE["status"] == "LOCKED_AND_UNPOOLED"


def test_comparison_unpooled_datasets():
    state = ForwardEvidenceCockpit.load_cockpit_state()
    comp = state["p49"].get("comparison", {})
    assert "historical" in comp
    assert "forward" in comp
    assert comp["historical"]["trades_n"] == 82
