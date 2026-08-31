"""
Phase 34 — Financial Center Holidays & Session Interaction Test Suite
Validates financial-center holiday tracking, open/closed session detection,
and liquidity implications across London, NY, Frankfurt, Tokyo, Shanghai, Sydney, and Zurich.
"""

import pytest
from datetime import date, datetime, timezone
from xauusd_daily_preflight import SessionHolidayInteractionMatrix
from xauusd_market_conditions import MarketHolidayDetector


def test_session_interaction_matrix_covers_seven_centers():
    """Validates that session interaction matrix evaluates all 7 global financial centers."""
    matrix = SessionHolidayInteractionMatrix.evaluate_session_matrix()
    assert len(matrix) == 7
    centers = {row["financial_center"] for row in matrix}
    expected = {"London", "New York", "Frankfurt", "Tokyo", "Shanghai", "Sydney", "Zurich"}
    assert centers == expected
    for row in matrix:
        assert "financial_center" in row
        assert "country" in row
        assert "open_closed" in row
        assert row["open_closed"] in ["OPEN", "CLOSED"]
        assert "session_status" in row
        assert "holiday_name" in row
        assert "expected_liquidity_effect" in row


def test_london_bank_holiday_session_interaction():
    """Validates session behavior during a UK bank holiday (e.g. Early May Bank Holiday)."""
    uk_bank_holiday = date(2026, 5, 6)
    matrix = SessionHolidayInteractionMatrix.evaluate_session_matrix(target_date=uk_bank_holiday)
    london_row = [r for r in matrix if r["financial_center"] == "London"][0]
    assert london_row["open_closed"] == "CLOSED"
    assert london_row["session_status"] == "BANK HOLIDAY"
    assert "reduced" in london_row["expected_liquidity_effect"].lower() or "wide spreads" in london_row["expected_liquidity_effect"].lower()
