"""
Phase 34 — Daily Pre-Flight & News UI Integration Test Suite
Validates that Daily Pre-Flight hero card, 10-point checklist, event timeline,
and "What Did I Miss Today?" card are properly structured for Streamlit UI rendering.
"""

import pytest
import pandas as pd
from xauusd_daily_preflight import DailyPreFlightEngine, SessionHolidayInteractionMatrix, HistoricalDailyNewsAuditor
from datetime import date


def test_daily_preflight_ui_payload():
    """Validates that DailyPreFlightEngine output has all required fields for UI rendering."""
    pf = DailyPreFlightEngine.get_daily_preflight()
    required_keys = [
        "date", "master_state", "state_color", "reason", "research_meaning",
        "research_guidance", "strategy_status", "calendar_source", "calendar_status",
        "forex_factory_status", "calendar_last_updated", "holiday_status",
        "liquidity_expectation", "next_high_impact_event", "time_until_event",
        "high_impact_count", "xau_relevant_count", "usd_events_count",
        "events_timeline", "session_matrix", "checklist"
    ]
    for k in required_keys:
        assert k in pf, f"Missing key in daily_preflight: {k}"


def test_checklist_dataframe_compatibility():
    """Validates that 10-point checklist is compatible with pd.DataFrame."""
    pf = DailyPreFlightEngine.get_daily_preflight()
    df_chk = pd.DataFrame(pf["checklist"])
    assert len(df_chk) == 10
    assert "item" in df_chk.columns
    assert "status" in df_chk.columns
    assert "detail" in df_chk.columns


def test_session_matrix_dataframe_compatibility():
    """Validates that session interaction matrix is compatible with pd.DataFrame."""
    matrix = SessionHolidayInteractionMatrix.evaluate_session_matrix()
    df_sess = pd.DataFrame(matrix)
    assert len(df_sess) == 7
    expected_cols = ["financial_center", "country", "open_closed", "session_status", "holiday_name", "expected_liquidity_effect"]
    for c in expected_cols:
        assert c in df_sess.columns


def test_historical_audit_ui_compatibility():
    """Validates that 'What Did I Miss Today?' audit card generates clean data for UI."""
    audit = HistoricalDailyNewsAuditor.audit_historical_day(date(2026, 8, 28))
    assert isinstance(audit, dict)
    assert "date" in audit
    assert "day_type" in audit
    assert "explanation" in audit
    assert "forward_trades_on_date" in audit
