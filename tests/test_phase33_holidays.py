"""
Phase 33 — Financial Center Bank Holidays & Liquidity Test Suite
Validates bank holiday detection across major centers, trading day classification,
and research explanations without falsely claiming forex is completely closed.
"""

import pytest
from datetime import date
from xauusd_market_conditions import MarketHolidayDetector


def test_bank_holiday_vs_market_closure_distinction():
    """Validates that bank holidays are classified as REDUCED LIQUIDITY, not full closure."""
    # US Labor Day (2026-09-02)
    labor_day = date(2026, 9, 2)
    res = MarketHolidayDetector.get_holiday_status(labor_day)
    assert res["trading_day_classification"] == "HOLIDAY / REDUCED LIQUIDITY DAY"
    assert "reduced" in res["explanation"].lower() or "bank holiday" in res["explanation"].lower()


def test_major_global_closure():
    """Validates that Christmas Day is classified as MAJOR MARKET CLOSURE."""
    xmas = date(2026, 12, 25)
    res = MarketHolidayDetector.get_holiday_status(xmas)
    assert res["trading_day_classification"] == "MAJOR MARKET CLOSURE"


def test_all_seven_financial_centers_evaluated():
    """Validates that matrix includes London, New York, Frankfurt, Tokyo, Shanghai, Sydney, Zurich."""
    res = MarketHolidayDetector.get_holiday_status()
    matrix = res["financial_centers_matrix"]
    assert len(matrix) == 7
    expected = {"UK", "US", "EU", "JP", "CN", "AU", "CH"}
    found = {fc["code"] for fc in matrix}
    assert found == expected
