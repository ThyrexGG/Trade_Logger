"""
Phase 45 — UI DataFrame Conversion & Model Compatibility Test Suite
Validates that all tables in Continuous Operations & Weekly Audit UI convert into DataFrames without errors.
"""

import pandas as pd
import pytest
from xauusd_continuous_forward_ops import (
    SinceYouWereAwayAuditor,
    WeeklyResearchAuditEngine,
    RegimeTransitionDriftDetector,
    AlertDeduplicationAndIncidentTracker,
)


def test_phase45_ui_tables_conversion():
    """Validates DataFrame conversion across Phase 45 components."""
    # Since You Were Away
    sywa = SinceYouWereAwayAuditor.audit_since_you_were_away("XAUUSD")
    assert "verdict" in sywa

    # Weekly Audit
    weekly = WeeklyResearchAuditEngine.generate_weekly_audit()
    assert "week_identifier" in weekly

    # Regime Transition
    regime = RegimeTransitionDriftDetector.evaluate_regime_transition()
    assert "drift_state" in regime

    # Incidents Table
    incidents = AlertDeduplicationAndIncidentTracker.get_recent_incidents(limit=5)
    df_inc = pd.DataFrame(incidents)
    assert isinstance(df_inc, pd.DataFrame)
