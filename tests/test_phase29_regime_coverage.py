"""
Tests for Phase 29 Regime Coverage & Subgroup Classification.
Verifies pre-trade information boundaries, classification versions, and session/weekday/trend/volatility/structure buckets.
"""

import pytest
from xauusd_forward_regime_coverage import RegimeClassifier, RegimeCoverageEngine


def test_regime_classifier_trend_and_volatility():
    # Bullish Trend: Close > EMA20 > EMA50
    assert RegimeClassifier.classify_trend(ema20=2400.0, ema50=2380.0, close=2410.0) == "STRONG BULL"
    # Bearish Trend: Close < EMA20 < EMA50
    assert RegimeClassifier.classify_trend(ema20=2380.0, ema50=2400.0, close=2370.0) == "STRONG BEAR"
    
    # Volatility ATR ratio
    assert RegimeClassifier.classify_volatility(current_atr=10.0, baseline_atr=18.5) == "LOW"
    assert RegimeClassifier.classify_volatility(current_atr=18.5, baseline_atr=18.5) == "NORMAL"
    assert RegimeClassifier.classify_volatility(current_atr=30.0, baseline_atr=18.5) == "ELEVATED"
    assert RegimeClassifier.classify_volatility(current_atr=45.0, baseline_atr=18.5) == "EXTREME"


def test_regime_classifier_session_and_weekday():
    # Session UTC hours
    assert RegimeClassifier.classify_session(hour_utc=3) == "ASIA"
    assert RegimeClassifier.classify_session(hour_utc=8) == "LONDON"
    assert RegimeClassifier.classify_session(hour_utc=13) == "LONDON/NY OVERLAP"
    assert RegimeClassifier.classify_session(hour_utc=18) == "NEW YORK"
    assert RegimeClassifier.classify_session(hour_utc=22) == "ROLLOVER"

    # Weekdays
    assert RegimeClassifier.classify_weekday(0) == "MONDAY"
    assert RegimeClassifier.classify_weekday(4) == "FRIDAY"


def test_regime_coverage_engine_structure():
    cov = RegimeCoverageEngine.evaluate_regime_coverage(mode="PAPER")
    assert "trades_n" in cov
    assert "contract_hash" in cov
    assert cov["classification_version"] == "v1.0_FROZEN"
    assert "sessions" in cov
    assert "weekdays" in cov
    assert "concentration_audit" in cov
