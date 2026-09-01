"""
Phase 55 — Tests for Multi-Factor Scoring Models
"""

import pytest
from asset_edge_intelligence import (
    TechnicalStructureFactorEngine,
    SmartMoneyStructureFactorEngine,
    SessionLiquidityFactorEngine,
    DollarYieldsCrossAssetFactorEngine
)


def test_technical_structure_scoring():
    res = TechnicalStructureFactorEngine.evaluate("XAUUSD")
    assert -100.0 <= res["score"] <= 100.0
    assert res["direction"] in ["BULLISH", "BEARISH", "NEUTRAL"]
    assert len(res["evidence"]) > 0


def test_smc_structure_scoring():
    res = SmartMoneyStructureFactorEngine.evaluate("XAUUSD")
    assert -100.0 <= res["score"] <= 100.0
    assert res["direction"] in ["BULLISH", "BEARISH", "NEUTRAL"]
    assert len(res["evidence"]) > 0


def test_session_liquidity_scoring():
    res = SessionLiquidityFactorEngine.evaluate("XAUUSD")
    assert -100.0 <= res["score"] <= 100.0
    assert "session_name" in res
    assert "liquidity_state" in res


def test_dollar_yields_scoring():
    res = DollarYieldsCrossAssetFactorEngine.evaluate("XAUUSD")
    assert -100.0 <= res["score"] <= 100.0
    assert len(res["evidence"]) > 0
