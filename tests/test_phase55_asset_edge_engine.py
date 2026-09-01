"""
Phase 55 — Tests for Asset Edge Intelligence Engine
"""

import pytest
from asset_edge_intelligence import (
    EDGE_MODEL_VERSION,
    AssetEdgeIntelligenceEngine
)


def test_asset_edge_engine_snapshot_structure():
    snapshot = AssetEdgeIntelligenceEngine.evaluate_asset_edge("XAUUSD")
    assert snapshot["symbol"] == "XAUUSD"
    assert snapshot["edge_model_version"] == EDGE_MODEL_VERSION
    assert -100.0 <= snapshot["overall_score"] <= 100.0
    assert snapshot["directional_bias"] in [
        "EXTREME BULLISH", "VERY BULLISH", "BULLISH", "LEAN BULLISH",
        "NEUTRAL", "LEAN BEARISH", "BEARISH", "VERY BEARISH", "EXTREME BEARISH", "UNAVAILABLE"
    ]
    assert "data_quality" in snapshot
    assert "conflict_analysis" in snapshot
    assert "factor_breakdown" in snapshot
    assert "why_this_score" in snapshot
    assert "payload_fingerprint" in snapshot
    assert len(snapshot["payload_fingerprint"]) == 64


def test_evaluate_all_assets_returns_10_instruments():
    all_assets = AssetEdgeIntelligenceEngine.evaluate_all_assets()
    assert len(all_assets) == 10
    symbols = [a["symbol"] for a in all_assets]
    assert "XAUUSD" in symbols
    assert "USDJPY" in symbols
    assert "EURUSD" in symbols
    assert "SPX500" in symbols
    assert "BTCUSD" in symbols
