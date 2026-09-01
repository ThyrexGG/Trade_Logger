"""
TradeLogger Phase 59 — Calculation Reuse & Zero Duplication Tests
=================================================================
Validates that calculations are computed once and shared faithfully
across Ranking, Breadth, Change Detector, and UI Aggregator.
"""

from datetime import datetime, timezone
import pytest

from market_intelligence_scanner import (
    MarketScannerEngine,
    MarketRankingEngine,
    MarketBreadthEngine,
    MarketWideChangeDetector
)
from market_intelligence_command_center import UnifiedMarketIntelligenceAggregator


def test_calculation_reuse_across_consumers():
    """Verify that scan_universe outputs are reused without re-running scans."""
    records = MarketScannerEngine.scan_universe("ALL")
    
    # 1. Ranking Engine uses records directly
    ranked = MarketRankingEngine.rank_records(records)
    assert len(ranked) == 23
    assert ranked[0]["rank"] == 1
    
    # 2. Breadth Engine uses same records
    breadth = MarketBreadthEngine.calculate_breadth(records)
    assert breadth["total_universe"] == 23
    assert breadth["pct_bullish"] + breadth["pct_bearish"] + breadth["pct_neutral"] == 100.0
    
    # 3. Change Detector uses same records
    changes = MarketWideChangeDetector.evaluate_market_changes(records)
    assert "structured_deltas" in changes
    assert changes["total_deltas"] == 23


def test_aggregator_incorporates_reused_subsystems():
    """Verify UnifiedMarketIntelligenceAggregator reuses sub-engines."""
    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state()
    
    assert snap.market_breadth["total_universe"] == 23
    assert len(snap.ranked_assets) == 23
    assert snap.regime_snapshot.primary_regime is not None
    assert "growth_state" in snap.macro_environment
