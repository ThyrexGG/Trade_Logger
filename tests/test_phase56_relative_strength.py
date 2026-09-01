"""
Test Suite: Phase 56 Forex Relative Strength Engine
===================================================
Validates currency pair economic strength differentials, directional bias labeling,
and mandatory contextual intelligence disclaimers.
"""

from macro_intelligence_engine import (
    EconomicStrengthEngine,
    ForexRelativeStrengthEngine
)


def test_country_economic_strength_calculation():
    """Verifies country-wide economic strength scores [-100, 100]."""
    usd_res = EconomicStrengthEngine.evaluate_economic_strength("USD")
    assert -100.0 <= usd_res["economic_strength_score"] <= 100.0
    assert "classification" in usd_res
    assert "growth" in usd_res["component_scores"]

    eur_res = EconomicStrengthEngine.evaluate_economic_strength("EUR")
    assert -100.0 <= eur_res["economic_strength_score"] <= 100.0

    jpy_res = EconomicStrengthEngine.evaluate_economic_strength("JPY")
    assert -100.0 <= jpy_res["economic_strength_score"] <= 100.0


def test_forex_relative_strength_differentials():
    """Verifies relative economic strength for major FX pairs."""
    usdjpy = ForexRelativeStrengthEngine.evaluate_relative_strength("USDJPY")
    assert usdjpy["is_forex"] is True
    assert usdjpy["base_currency"] == "USD"
    assert usdjpy["quote_currency"] == "JPY"
    assert -100.0 <= usdjpy["relative_score"] <= 100.0
    assert "CONTEXT ONLY — NOT AN ENTRY SIGNAL" in usdjpy["disclaimer"]

    eurusd = ForexRelativeStrengthEngine.evaluate_relative_strength("EURUSD")
    assert eurusd["is_forex"] is True
    assert eurusd["base_currency"] == "EUR"
    assert eurusd["quote_currency"] == "USD"

    # Non-forex fallback
    xau = ForexRelativeStrengthEngine.evaluate_relative_strength("XAUUSD")
    assert xau["is_forex"] is False
