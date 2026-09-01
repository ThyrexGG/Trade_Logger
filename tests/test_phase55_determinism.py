"""
Phase 55 — Tests for Scoring Determinism (No Random / No LLM Scores)
"""

import pytest
from datetime import datetime, timezone
from asset_edge_intelligence import AssetEdgeIntelligenceEngine


def test_identical_inputs_produce_identical_scores():
    dt = datetime(2026, 9, 1, 15, 30, 0, tzinfo=timezone.utc)
    snap1 = AssetEdgeIntelligenceEngine.evaluate_asset_edge("XAUUSD", as_of=dt)
    snap2 = AssetEdgeIntelligenceEngine.evaluate_asset_edge("XAUUSD", as_of=dt)

    assert snap1["overall_score"] == snap2["overall_score"]
    assert snap1["directional_bias"] == snap2["directional_bias"]
    assert snap1["confidence"] == snap2["confidence"]
    assert snap1["data_quality"]["score"] == snap2["data_quality"]["score"]
    assert snap1["conflict_analysis"]["factor_agreement_pct"] == snap2["conflict_analysis"]["factor_agreement_pct"]
