"""
Phase 53 — Tests for Cockpit UI Integration and Layout
"""

import pytest
from trading_workspace_cockpit import TradingWorkspaceCockpit


def test_market_intelligence_boundary_renders():
    # Calling market context boundary must succeed
    TradingWorkspaceCockpit.render_market_context_intelligence("XAUUSD")


def test_realtime_signal_area_renders():
    TradingWorkspaceCockpit.render_realtime_signal_area("XAUUSD")
    TradingWorkspaceCockpit.render_realtime_signal_area("EURUSD")
