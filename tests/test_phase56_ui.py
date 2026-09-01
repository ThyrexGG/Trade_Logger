"""
Test Suite: Phase 56 UI Components & Render Functions
=====================================================
Validates that UI rendering functions and table structures compile,
accept appropriate symbols, and produce expected data structures.
"""

from asset_edge_scorecard import (
    render_economic_surprise_table,
    AssetEdgeScorecardUI
)
from macro_intelligence_engine import MacroIntelligenceEngine
from asset_edge_intelligence import AssetEdgeIntelligenceEngine


def test_ui_data_structures():
    """Verifies that snapshots passed to UI contain all required keys for 8-tab rendering."""
    edge_snap = AssetEdgeIntelligenceEngine.evaluate_asset_edge("XAUUSD")
    macro_snap = MacroIntelligenceEngine.evaluate_macro_context("XAUUSD")

    # Verify hero keys
    assert "overall_score" in edge_snap
    assert "macro_score" in macro_snap
    assert "factor_breakdown" in edge_snap
    assert "contribution_matrix" in macro_snap
    assert "surprise_summary" in macro_snap
    assert "factor_groups" in macro_snap
    assert "conflict_analysis" in macro_snap
    assert "freshness_audit" in macro_snap
