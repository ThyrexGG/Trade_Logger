"""
Phase 34 — No Lookahead Protection & "What Did I Miss Today?" Historical Audit Test Suite
Validates that future economic events cannot leak into past observation records,
and tests the historical date audit engine.
"""

import pytest
from datetime import date, datetime, timezone, timedelta
from xauusd_daily_preflight import HistoricalDailyNewsAuditor
from xauusd_market_conditions import MarketConditionProvenance, EventProximityEngine


def test_historical_daily_news_auditor():
    """Validates that HistoricalDailyNewsAuditor inspects past market conditions accurately."""
    test_date = date(2026, 8, 25)
    audit = HistoricalDailyNewsAuditor.audit_historical_day(test_date)
    assert isinstance(audit, dict)
    assert audit["date"] == "2026-08-25"
    assert "day_type" in audit
    assert "trading_day_classification" in audit
    assert "liquidity_condition" in audit
    assert "holidays_list" in audit
    assert "total_events_count" in audit
    assert "forward_trades_on_date" in audit
    assert "explanation" in audit


def test_no_future_leakage_in_event_proximity():
    """Validates that proximity calculation strictly respects observation reference time."""
    ref_time = datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc)
    future_event_iso = (ref_time + timedelta(hours=3)).isoformat()
    
    prox = EventProximityEngine.calculate_proximity(future_event_iso, current_time=ref_time)
    assert prox["proximity_bucket"] == "1-6h"
    assert prox["minutes_to_event"] == 180.0
    assert prox["caution_window"] is False
