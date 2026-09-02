"""
TradeLogger Phase 57 — Test Suite: Market Breadth Engine
=========================================================
Validates:
- Universe-wide directional breadth calculation (% Bullish, % Bearish, % Neutral).
- Mathematical sum constraint (pct_bullish + pct_bearish + pct_neutral == 100.0).
- Factor alignment participation breadth (% Factor Aligned).
- Asset-class specific breadth slices.
"""

import pytest
from market_intelligence_scanner import (
    MarketScannerEngine,
    MarketBreadthEngine
)


def test_market_breadth_calculation():
    """Verify universe breadth metrics and percentage sum invariant."""
    records = MarketScannerEngine.scan_universe("ALL")
    breadth = MarketBreadthEngine.calculate_breadth(records)

    assert isinstance(breadth, dict)
    assert breadth["total_universe"] == 23

    # Check sum of percentages equals 100% within floating point tolerance
    total_pct = breadth["pct_bullish"] + breadth["pct_bearish"] + breadth["pct_neutral"]
    assert abs(total_pct - 100.0) < 0.2

    assert 0.0 <= breadth["pct_aligned"] <= 100.0
    assert 0.0 <= breadth["avg_data_quality"] <= 100.0


def test_market_breadth_by_asset_class():
    """Verify breadth calculation when filtered by asset class."""
    fx_records = MarketScannerEngine.scan_universe("FX")
    fx_breadth = MarketBreadthEngine.calculate_breadth(fx_records)

    assert fx_breadth["total_universe"] == 8
    assert abs((fx_breadth["pct_bullish"] + fx_breadth["pct_bearish"] + fx_breadth["pct_neutral"]) - 100.0) < 0.2
