"""
Phase 43 — UI Compatibility & DataFrame Conversion Test Suite
Validates that all Phase 43 UI models convert into pandas DataFrames without crashing.
"""

from datetime import datetime, timezone, date
import pandas as pd
import pytest
from xauusd_overnight_experiment import (
    HeartbeatAndLivenessAuditor,
    MorningAfterAuditSynthesizer,
    SetupLifecycleReconciler,
    OvernightExperimentSessionEngine,
)


def test_ui_dataframes_conversion():
    """Validates that all tables in Morning-After Audit UI convert cleanly to DataFrames."""
    target_dt = date(2026, 9, 1)
    audit = MorningAfterAuditSynthesizer.synthesize_morning_audit(target_dt)

    # Subsystem Heartbeats
    hb_matrix = HeartbeatAndLivenessAuditor.audit_all_subsystems()
    df_hb = pd.DataFrame(hb_matrix["subsystems"])
    assert not df_hb.empty
    assert "subsystem" in df_hb.columns
    assert "status" in df_hb.columns

    # Timeline
    if audit["timeline"]:
        df_time = pd.DataFrame(audit["timeline"])[["timestamp", "category", "title", "details"]]
        assert not df_time.empty
        assert "timestamp" in df_time.columns

    # Recent Sessions
    sessions = OvernightExperimentSessionEngine.get_recent_sessions(limit=5)
    df_sess = pd.DataFrame(sessions)
    assert isinstance(df_sess, pd.DataFrame)
