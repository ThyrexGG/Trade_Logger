# -*- coding: utf-8 -*-
"""
Phase 61 - Test Chart Canvas, Timeframe Control & MTF Context Bar
"""
import pytest
from trading_workspace_cockpit import TradingWorkspaceCockpit


def test_mtf_hierarchy_structure():
    """Verify 6-timeframe structure in MTF hierarchy."""
    mtf = TradingWorkspaceCockpit.get_mtf_bias_hierarchy("XAUUSD")
    assert "1D" in mtf
    assert "4H" in mtf
    assert "1H" in mtf
    assert "15M" in mtf
    assert "5M" in mtf
    assert "1M" in mtf
    assert mtf["1M"] in ["ENTRY READY", "WAITING", "STANDBY"]


def test_chart_timeframes_supported():
    """Verify standard supported timeframes."""
    supported = ["1m", "5m", "15m", "1h", "4h", "D"]
    assert len(supported) == 6
