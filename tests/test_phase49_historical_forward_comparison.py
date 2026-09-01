"""
Phase 49 — Tests for Historical vs Forward Side-by-Side Comparison
"""

import pytest
from xauusd_forward_statistical_monitoring import (
    HistoricalVsForwardComparativeMonitor,
    HISTORICAL_BASELINE,
)


def test_comparison_empty_state():
    """Validates comparison at N=0 returns locked baseline and unpooled status."""
    fwd_metrics = {"trades_n": 0, "expectancy_r": 0.0, "win_rate_pct": 0.0, "profit_factor": 0.0, "max_drawdown_r": 0.0}
    comp = HistoricalVsForwardComparativeMonitor.compare_historical_vs_forward(fwd_metrics)

    assert comp["historical"]["trades_n"] == 82
    assert comp["historical"]["expectancy_r"] == 0.637
    assert comp["historical"]["win_rate_pct"] == 58.6
    assert comp["historical"]["profit_factor"] == 2.52
    assert comp["forward"]["trades_n"] == 0
    assert "UNPOOLED" in comp["pooling_prevention_check"]
    assert comp["comparison_verdict"] == "NO FORWARD EVIDENCE (N = 0)"


def test_comparison_deltas_calculated_correctly():
    """Validates deltas calculation when forward metrics exist."""
    fwd_metrics = {"trades_n": 15, "expectancy_r": 0.700, "win_rate_pct": 60.0, "profit_factor": 2.60, "max_drawdown_r": 3.0}
    comp = HistoricalVsForwardComparativeMonitor.compare_historical_vs_forward(fwd_metrics)

    assert comp["deltas"]["expectancy_delta"] == round(0.700 - 0.637, 4)
    assert comp["deltas"]["win_rate_delta_pct"] == round(60.0 - 58.6, 2)
    assert comp["deltas"]["profit_factor_delta"] == round(2.60 - 2.52, 2)
    assert comp["deltas"]["drawdown_divergence_r"] == round(3.0 - 4.0, 2)
    assert "CONSISTENT" in comp["comparison_verdict"]
