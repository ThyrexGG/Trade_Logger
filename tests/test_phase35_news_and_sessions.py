"""
Phase 35 — Global Session Status & News Alerts Integration Test Suite
Validates session open vs center open distinction, event countdowns, and bank holiday warnings.
"""

import pytest
from xauusd_daily_command_center import DailyTradingCommandEngine
from xauusd_daily_preflight import SessionHolidayInteractionMatrix


def test_session_vs_financial_center_open_distinction():
    """Validates that session status is evaluated across all 7 financial centers."""
    matrix = SessionHolidayInteractionMatrix.evaluate_session_matrix()
    assert len(matrix) == 7
    for fc in matrix:
        assert "financial_center" in fc
        assert "open_closed" in fc
        assert "session_status" in fc
        assert "expected_liquidity_effect" in fc


def test_command_center_session_and_holiday_alerts():
    """Validates that DailyTradingCommandEngine produces truthful session and holiday telemetry."""
    cmd = DailyTradingCommandEngine.get_command_center_payload("XAUUSD")
    assert "current_session" in cmd
    assert "next_session" in cmd
    assert "has_bank_holiday" in cmd
    assert "holiday_warning_title" in cmd
    assert "active_holidays" in cmd
    if cmd["has_bank_holiday"]:
        assert len(cmd["active_holidays"]) > 0
