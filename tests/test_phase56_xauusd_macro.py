"""
Test Suite: Phase 56 XAUUSD Macro Context Model
===============================================
Validates gold-specific macro driver modeling: Real Rates, USD Pressure,
2Y/10Y Yield Trajectory, Central Bank Demand, and COT Positioning.
"""

from macro_intelligence_engine import (
    XAUUSDMacroContextModel,
    MacroIntelligenceEngine
)


def test_gold_macro_model_drivers():
    """Verifies all required gold macro drivers and output format."""
    model = XAUUSDMacroContextModel.evaluate_gold_macro_context()
    assert model["symbol"] == "XAUUSD"
    assert -100.0 <= model["macro_context_score"] <= 100.0
    assert model["direction"] in ["BULLISH", "BEARISH", "NEUTRAL"]
    assert "CONTEXT ONLY — NOT AN ENTRY SIGNAL" in model["disclaimer"]

    drivers = model["drivers"]
    assert "usd_pressure" in drivers
    assert "real_rate_proxy" in drivers
    assert "yield_trajectory" in drivers
    assert "safe_haven_demand" in drivers
    assert "institutional_cot" in drivers
    assert "inflation_support" in drivers


def test_master_engine_xauusd_integration():
    """Verifies that MacroIntelligenceEngine coordinates gold macro context seamlessly."""
    snap = MacroIntelligenceEngine.evaluate_macro_context("XAUUSD")
    assert snap["symbol"] == "XAUUSD"
    assert "macro_score" in snap
    assert "contribution_matrix" in snap
    assert len(snap["contribution_matrix"]) >= 5
    assert "conflict_analysis" in snap
    assert "freshness_audit" in snap
