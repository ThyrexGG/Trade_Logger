"""
Phase 58 — Tests for Unified Market Intelligence Command Center
"""

import pytest
from datetime import datetime, timezone
from market_intelligence_command_center import (
    COMMAND_CENTER_VERSION,
    UnifiedMarketIntelligenceAggregator,
    AssetContextProfileEngine
)


def test_command_center_aggregator_structure():
    as_of = datetime(2026, 9, 1, 14, 0, 0, tzinfo=timezone.utc)
    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state(as_of=as_of)

    assert snap.as_of == as_of
    assert snap.regime_snapshot is not None
    assert snap.market_breadth["total_assets"] >= 20
    assert len(snap.ranked_assets) >= 20
    assert len(snap.what_matters) > 0
    assert "usd_strength_score" in snap.macro_environment
    assert snap.data_health["overall_quality_score"] > 0
    assert "20D" in snap.correlation_matrices
    assert snap.model_versions["command_center"] == COMMAND_CENTER_VERSION
    assert len(snap.payload_fingerprint) == 64


def test_asset_context_profile_engine():
    as_of = datetime(2026, 9, 1, 14, 0, 0, tzinfo=timezone.utc)
    prof = AssetContextProfileEngine.build_asset_profile("XAUUSD", as_of=as_of)

    assert prof["symbol"] == "XAUUSD"
    assert "edge_snapshot" in prof
    assert "macro_profile" in prof
    assert "recent_surprises" in prof
    assert "conflict_analysis" in prof
    assert len(prof["why_points"]) > 0
