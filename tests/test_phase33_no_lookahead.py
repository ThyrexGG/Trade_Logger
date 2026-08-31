"""
Phase 33 — No Lookahead Protection & Provenance Integrity Test Suite
Validates that forward observations preserve exact timestamps and cannot
retroactively absorb future economic events or news data.
"""

import pytest
from datetime import datetime, timezone, timedelta
from xauusd_market_conditions import MarketConditionProvenance, EventProximityEngine


def test_observation_provenance_preserves_timestamp():
    """Validates that provenance generator preserves exact observation timestamp."""
    obs_time = datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc)
    meta = MarketConditionProvenance.generate_observation_metadata(obs_time)
    assert meta["observation_timestamp"] == obs_time.isoformat()
    assert "market_condition_id" in meta
    assert "market_condition_fingerprint" in meta


def test_future_event_proximity_relative_to_observation_time():
    """Validates that proximity is calculated relative to observation timestamp, not current real time."""
    obs_time = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)
    future_event_time = (obs_time + timedelta(hours=2)).isoformat()

    prox = EventProximityEngine.calculate_proximity(future_event_time, current_time=obs_time)
    assert prox["proximity_bucket"] == "1-6h"
    assert prox["minutes_to_event"] == 120.0
