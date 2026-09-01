"""
Phase 58 — Tests for Data Quality & Anti-Fabrication in Command Center
"""

import pytest
from datetime import datetime, timezone
from market_intelligence_command_center import UnifiedMarketIntelligenceAggregator


def test_command_center_data_health():
    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state()
    dh = snap.data_health

    assert 0 <= dh["overall_quality_score"] <= 100
    assert dh["total_feeds"] > 0
    assert dh["quality_rating"] in ["HIGH INTEGRITY", "MODERATE", "DEGRADED"]
    assert dh["live_fresh_feeds"] >= 0


def test_ranking_withheld_for_low_quality():
    snap = UnifiedMarketIntelligenceAggregator.aggregate_market_state()
    for r in snap.ranked_assets:
        dq_val = r.get("data_quality_score", 0) if isinstance(r, dict) else r.data_quality_score
        ctx_st = r.get("context_state", "") if isinstance(r, dict) else r.context_state
        if dq_val < 40:
            assert ctx_st == "RANKING WITHHELD"
