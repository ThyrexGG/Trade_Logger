"""
Phase 32 — Market Conditions UI & Pre-Flight Integration Test Suite
Validates that pre-flight intelligence, economic event timeline,
holiday matrix, and attribution panels are structured cleanly for UI rendering.
"""

import pytest
from xauusd_market_conditions import MarketPreFlightEngine, MarketHolidayDetector, EconomicCalendarProvider


def test_market_preflight_summary_structure():
    """Validates that MarketPreFlightEngine generates all required UI card fields."""
    summary = MarketPreFlightEngine.get_preflight_summary()
    assert isinstance(summary, dict)
    assert "master_state" in summary
    assert summary["master_state"] in [
        "NORMAL", "CAUTION", "HIGH IMPACT", "HOLIDAY AFFECTED", "MAJOR MARKET CLOSURE", "NEWS DATA UNAVAILABLE"
    ]
    assert "state_color" in summary
    assert "date" in summary
    assert "current_session" in summary
    assert "active_financial_centers" in summary
    assert len(summary["active_financial_centers"]) >= 1
    assert "trading_day_classification" in summary
    assert "liquidity_condition" in summary
    assert "high_impact_events_count" in summary
    assert "xauusd_relevant_events_count" in summary
    assert "usd_events_count" in summary
    assert "events_timeline" in summary
    assert "financial_centers_matrix" in summary
    assert "explanation" in summary
    assert "research_action" in summary


def test_economic_timeline_dataframe_compatibility():
    """Validates that events timeline contains necessary fields for pandas DataFrame rendering."""
    summary = MarketPreFlightEngine.get_preflight_summary()
    timeline = summary["events_timeline"]
    assert isinstance(timeline, list)
    if timeline:
        first_evt = timeline[0]
        required_cols = ["event_name", "currency", "impact_level", "scheduled_time", "proximity_bucket", "potential_effect"]
        for col in required_cols:
            assert col in first_evt, f"Missing required column in event: {col}"


def test_financial_centers_matrix_completeness():
    """Validates financial center liquidity matrix covering London, New York, Frankfurt, Tokyo, Shanghai, Sydney, Zurich."""
    summary = MarketPreFlightEngine.get_preflight_summary()
    matrix = summary["financial_centers_matrix"]
    assert len(matrix) == 7
    for row in matrix:
        assert "center" in row
        assert "country" in row
        assert "status" in row
        assert "detail" in row
