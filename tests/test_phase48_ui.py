"""
Phase 48 — Tests for UI Lifecycle Helpers and Formats
"""

import pytest
import pandas as pd
from xauusd_forward_lifecycle import (
    ForwardLifecycleReconciliationAudit,
    ForwardAlphaDecayObservationalMonitor,
    ForwardMorningAwaySummaryClassifier
)


def test_ui_data_structures():
    audit = ForwardLifecycleReconciliationAudit.audit_database_integrity()
    df_audit = pd.DataFrame([audit])
    assert not df_audit.empty
    assert "audit_verdict" in df_audit.columns

    alpha = ForwardAlphaDecayObservationalMonitor.calculate_observational_metrics()
    assert "decay_verdict" in alpha
    assert "sample_status" in alpha

    away = ForwardMorningAwaySummaryClassifier.classify_away_reality()
    assert "status_badge" in away
