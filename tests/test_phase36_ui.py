"""
Phase 36 — UI Rendering Compatibility & Component Payload Test Suite
Validates that command center payload with Phase 36 telemetry converts cleanly into DataFrames and UI cards.
"""

import pytest
import pandas as pd
from xauusd_daily_command_center import DailyTradingCommandEngine
from xauusd_news_reliability import MarketClosureAuditor


def test_command_center_phase36_payload():
    """Validates complete Phase 36 command center payload."""
    cmd = DailyTradingCommandEngine.get_command_center_payload("XAUUSD")
    assert "reliability_status" in cmd
    assert "source_classification" in cmd
    assert "freshness_audit" in cmd
    assert "closure_audit" in cmd

    # All centers DataFrame
    df_centers = pd.DataFrame(cmd["closure_audit"]["all_centers"])
    assert len(df_centers) == 7
    assert "center" in df_centers.columns
    assert "closure_type" in df_centers.columns
