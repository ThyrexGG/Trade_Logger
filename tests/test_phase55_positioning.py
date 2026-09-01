"""
Phase 55 — Tests for Sentiment & COT Positioning
"""

import pytest
from asset_edge_intelligence import PositioningSentimentFactorEngine


def test_cot_positioning_for_gold():
    res = PositioningSentimentFactorEngine.evaluate("XAUUSD")
    assert res["data_available"] is True
    assert res["cot_status"] == "HEALTHY"


def test_cot_positioning_honest_unavailable():
    # Crypto or instruments without CFTC report must return COT DATA UNAVAILABLE
    res = PositioningSentimentFactorEngine.evaluate("BTCUSD")
    assert res["data_available"] is False
    assert res["cot_status"] == "COT DATA UNAVAILABLE"
    assert res["score"] == 0.0
