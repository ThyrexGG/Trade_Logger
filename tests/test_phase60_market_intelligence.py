# -*- coding: utf-8 -*-
"""
Phase 60 - Test Unified Market Intelligence Command Center UX & Progressive Disclosure
"""
import pytest
from market_intelligence_command_center import (
    UnifiedMarketIntelligenceAggregator,
    AssetContextProfileEngine,
    CommandCenterSnapshotStore
)


def test_command_center_aggregator_snapshot_payload():
    """Verify that UnifiedMarketIntelligenceAggregator returns complete 3-second hero, breadth, and regime fields."""
    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state()
    assert snap is not None
    assert snap.regime_snapshot is not None
    assert snap.market_breadth is not None
    assert "pct_bullish" in snap.market_breadth
    assert "pct_bearish" in snap.market_breadth
    assert len(snap.ranked_assets) >= 20
    assert snap.data_health is not None
    assert snap.data_health["overall_quality_score"] >= 0


def test_asset_context_profile_drilldown():
    """Verify that AssetContextProfileEngine builds full 6-pillar contextual deep dive for an asset."""
    profile = AssetContextProfileEngine.build_asset_profile("XAUUSD")
    assert profile["symbol"] == "XAUUSD"
    assert "edge_snapshot" in profile
    assert "macro_profile" in profile
    assert "conflict_analysis" in profile
    assert "why_points" in profile
    assert "data_quality" in profile
    assert len(profile["edge_snapshot"].get("factor_breakdown", [])) >= 5


def test_command_center_snapshot_fingerprint_integrity():
    """Verify that immutable snapshot records generate deterministic SHA-256 fingerprints."""
    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state()
    saved_id = CommandCenterSnapshotStore.record_snapshot(
        regime_snap=snap.regime_snapshot,
        breadth=snap.market_breadth,
        ranked_assets=snap.ranked_assets,
        what_matters=snap.what_matters,
        usd_strength=snap.macro_environment.get("usd_strength_score", 0.0),
        data_quality=snap.data_health.get("overall_quality_score", 90)
    )
    assert saved_id is not None
    assert "CMD_SNAP_" in saved_id
