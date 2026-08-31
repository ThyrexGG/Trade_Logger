"""
Phase 32 — Market Conditions, Economic News & Trading-Day Pre-Flight Test Suite
Validates economic calendar ingestion, financial-center holiday detection,
XAUUSD event relevance mapping, event proximity windows, and lookahead-free metadata generation.
"""

import pytest
from datetime import datetime, timezone, date
from xauusd_market_conditions import (
    MarketHolidayDetector,
    XAUUSDNewsRelevanceClassifier,
    EventProximityEngine,
    EconomicCalendarProvider,
    MarketConditionProvenance,
    MarketPreFlightEngine,
    FROZEN_CONTRACT_HASH,
)


def test_holiday_detector_normal_day():
    """Validates holiday detector output for a standard non-holiday trading weekday."""
    # Test on a known standard Wednesday (e.g. 2026-03-11)
    normal_date = date(2026, 3, 11)
    res = MarketHolidayDetector.get_holiday_status(normal_date)
    assert isinstance(res, dict)
    assert res["trading_day_classification"] == "NORMAL TRADING DAY"
    assert res["is_weekend"] is False
    assert res["holidays_count"] == 0
    assert len(res["financial_centers_matrix"]) == 7


def test_holiday_detector_major_market_closure():
    """Validates major market closure detection on Christmas and New Year."""
    xmas = date(2026, 12, 25)
    res_xmas = MarketHolidayDetector.get_holiday_status(xmas)
    assert res_xmas["trading_day_classification"] == "MAJOR MARKET CLOSURE"
    assert res_xmas["holidays_count"] >= 1

    ny = date(2026, 1, 1)
    res_ny = MarketHolidayDetector.get_holiday_status(ny)
    assert res_ny["trading_day_classification"] == "MAJOR MARKET CLOSURE"


def test_holiday_detector_bank_holiday_reduced_liquidity():
    """Validates bank holiday detection for UK and US holidays."""
    # UK Early May Bank Holiday
    uk_holiday = date(2026, 5, 6)
    res_uk = MarketHolidayDetector.get_holiday_status(uk_holiday)
    assert res_uk["trading_day_classification"] == "HOLIDAY / REDUCED LIQUIDITY DAY"
    assert "UK" in res_uk["liquidity_condition"] or "REDUCED" in res_uk["liquidity_condition"]


def test_holiday_detector_financial_centers_coverage():
    """Validates that all 7 major financial centers are covered in matrix."""
    res = MarketHolidayDetector.get_holiday_status()
    matrix = res["financial_centers_matrix"]
    assert len(matrix) == 7
    centers = [fc["center"] for fc in matrix]
    for c in ["London", "New York", "Frankfurt", "Tokyo", "Shanghai", "Sydney", "Zurich"]:
        assert c in centers


def test_xauusd_news_relevance_classification():
    """Validates deterministic relevance mapping for US macro releases and Fed announcements."""
    # Direct high-relevance US event
    cpi_event = {
        "event_name": "US Core CPI (MoM / YoY)",
        "currency": "USD",
        "impact_level": "HIGH IMPACT",
    }
    res_cpi = XAUUSDNewsRelevanceClassifier.classify_event_relevance(cpi_event)
    assert res_cpi["is_xauusd_relevant"] is True
    assert res_cpi["relevance_tier"] == "DIRECT HIGH RELEVANCE"
    assert res_cpi["impact_level"] == "HIGH IMPACT"

    # Routine non-relevant event
    aud_event = {
        "event_name": "Australia Westpac Consumer Confidence",
        "currency": "AUD",
        "impact_level": "INFORMATION",
    }
    res_aud = XAUUSDNewsRelevanceClassifier.classify_event_relevance(aud_event)
    assert res_aud["is_xauusd_relevant"] is False
    assert res_aud["relevance_tier"] == "GENERAL MACRO"


def test_event_proximity_engine_buckets():
    """Validates event proximity window bucket assignments."""
    now = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)

    # 15 minutes before event -> 0-30m window
    evt_15m = datetime(2026, 8, 31, 12, 15, tzinfo=timezone.utc).isoformat()
    prox_15m = EventProximityEngine.calculate_proximity(evt_15m, current_time=now)
    assert prox_15m["proximity_bucket"] == "0-30m"
    assert prox_15m["caution_window"] is True

    # 45 minutes before event -> 30-60m window
    evt_45m = datetime(2026, 8, 31, 12, 45, tzinfo=timezone.utc).isoformat()
    prox_45m = EventProximityEngine.calculate_proximity(evt_45m, current_time=now)
    assert prox_45m["proximity_bucket"] == "30-60m"
    assert prox_45m["caution_window"] is True

    # 2 hours before event -> 1-6h window
    evt_2h = datetime(2026, 8, 31, 14, 0, tzinfo=timezone.utc).isoformat()
    prox_2h = EventProximityEngine.calculate_proximity(evt_2h, current_time=now)
    assert prox_2h["proximity_bucket"] == "1-6h"
    assert prox_2h["caution_window"] is False

    # Concluded 10m ago -> POST-EVENT
    evt_past = datetime(2026, 8, 31, 11, 50, tzinfo=timezone.utc).isoformat()
    prox_past = EventProximityEngine.calculate_proximity(evt_past, current_time=now)
    assert "POST-EVENT" in prox_past["proximity_bucket"]


def test_economic_calendar_provider_ingestion():
    """Validates economic calendar provider ingestion and event enrichment."""
    cal = EconomicCalendarProvider.get_todays_calendar()
    assert isinstance(cal, dict)
    assert "events" in cal
    assert len(cal["events"]) >= 3
    assert "dataset_fingerprint" in cal
    assert len(cal["dataset_fingerprint"]) == 64

    for ev in cal["events"]:
        assert "event_name" in ev
        assert "currency" in ev
        assert "impact_level" in ev
        assert "scheduled_time" in ev
        assert "is_xauusd_relevant" in ev
        assert "proximity_bucket" in ev


def test_market_condition_provenance_lookahead_free():
    """Validates that observation metadata records exact conditions without lookahead."""
    obs_time = datetime(2026, 8, 31, 13, 0, tzinfo=timezone.utc)
    meta = MarketConditionProvenance.generate_observation_metadata(obs_time)
    assert isinstance(meta, dict)
    assert "market_condition_id" in meta
    assert "observation_timestamp" in meta
    assert meta["observation_timestamp"] == obs_time.isoformat()
    assert "trading_day_classification" in meta
    assert "liquidity_condition" in meta
    assert "news_condition" in meta
    assert "market_condition_fingerprint" in meta
    assert len(meta["market_condition_fingerprint"]) == 64
