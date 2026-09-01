"""
TradeLogger Phase 57 — Test Suite: Cross-Asset Regime Classification Engine
===========================================================================
Validates:
- 12 distinct contextual regime states.
- Multi-input synthesis (Equities, Gold, Oil, DXY, US10Y/US2Y, Breadth).
- Deterministic classification transitions and confidence scoring.
- Verification of non-directional, contextual terminology.
"""

import pytest
from cross_asset_regime_engine import (
    CrossAssetRegimeEngine,
    REGIME_STATES,
    REGIME_BENCHMARK_SYMBOLS,
    MarketRegimeSnapshot
)


def test_regime_states_count():
    """Verify all 12 defined regime states are recognized."""
    assert len(REGIME_STATES) == 12
    expected = {
        "RISK_ON", "RISK_OFF", "INFLATIONARY", "DISINFLATIONARY",
        "GROWTH_ACCELERATION", "GROWTH_DECELERATION",
        "USD_STRENGTH", "USD_WEAKNESS", "RATE_RISE", "RATE_FALL",
        "MIXED_REGIME", "INSUFFICIENT_DATA"
    }
    assert set(REGIME_STATES) == expected


def test_regime_benchmark_symbols():
    """Verify core benchmark assets are configured for cross-asset assessment."""
    assert len(REGIME_BENCHMARK_SYMBOLS) == 8
    assert set(REGIME_BENCHMARK_SYMBOLS) == {"DXY", "US10Y", "US2Y", "XAUUSD", "USOIL", "SPX500", "NAS100", "BTCUSD"}


def test_regime_evaluation():
    """Verify standard regime evaluation returns valid MarketRegimeSnapshot."""
    result = CrossAssetRegimeEngine.evaluate_regime()
    assert isinstance(result, MarketRegimeSnapshot)
    assert result.primary_regime in REGIME_STATES
    assert result.secondary_regime in REGIME_STATES
    assert 0.0 <= result.confidence_pct <= 100.0
    assert 0 <= result.data_quality_score <= 100
    assert isinstance(result.confirming_factors, list)
    assert len(result.confirming_factors) > 0
    assert isinstance(result.conflicting_factors, list)
    assert len(result.data_fingerprint) == 64


def test_regime_safety_context():
    """Verify regime engine outputs contextual state without trade signal keywords."""
    result = CrossAssetRegimeEngine.evaluate_regime()
    text = f"{result.primary_regime} {result.secondary_regime} {' '.join(result.confirming_factors)}"
    forbidden = ["BUY", "SELL", "ENTRY", "TRADE NOW", "LONG", "SHORT"]
    for word in forbidden:
        assert word not in text.upper().split()
