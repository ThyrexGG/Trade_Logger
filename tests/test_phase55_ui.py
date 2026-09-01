"""
Phase 55 — Tests for Scorecard UI Rendering
"""

import pytest
from asset_edge_intelligence import AssetEdgeIntelligenceEngine
from asset_edge_scorecard import AssetEdgeScorecardUI


def test_scorecard_ui_render_methods():
    snap = AssetEdgeIntelligenceEngine.evaluate_asset_edge("XAUUSD")
    # Must execute with zero unhandled exceptions
    AssetEdgeScorecardUI.render_single_asset_scorecard(snap)
    AssetEdgeScorecardUI.render_market_ranking_view()
    AssetEdgeScorecardUI.render_historical_timeline("XAUUSD")
    AssetEdgeScorecardUI.render_methodology_panel("XAUUSD")
