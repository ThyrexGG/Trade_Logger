"""
Phase 43 — Zero-Observation Explanation Test Suite
Validates deterministic reasoning hierarchy when forward N = 0.
"""

from datetime import datetime, timezone, date
import pytest
from xauusd_overnight_experiment import ZeroObservationExplanationEngine


def test_explain_zero_observations_weekend():
    """Validates weekend closure explanation."""
    weekend_dt = date(2026, 9, 6)  # Sunday
    exp = ZeroObservationExplanationEngine.explain_zero_observations(weekend_dt)

    assert exp["reason_code"] == "MARKET_CLOSED_WEEKEND"
    assert "MARKET CLOSED (WEEKEND)" in exp["title"]
    assert exp["strategy_contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_explain_zero_observations_weekday_open():
    """Validates weekday open explanation when no setups occurred."""
    weekday_dt = date(2026, 9, 1)  # Tuesday
    exp = ZeroObservationExplanationEngine.explain_zero_observations(weekday_dt)

    assert "title" in exp
    assert "explanation" in exp
    assert exp["reason_code"] in [
        "MARKET_OPEN_NO_VALID_SETUPS",
        "SETUPS_DETECTED_BUT_INVALIDATED",
        "PENDING_LIMITS_TIMED_OUT",
        "MARKET_DATA_INTERRUPTION"
    ]
