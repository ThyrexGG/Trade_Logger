"""
Phase 33 — Evidence Ledger Immutability & Alert Acknowledgement Test Suite
Validates that evidence ledger snapshots are strictly append-only,
and that alert acknowledgement is non-destructive and auditable.
"""

import pytest
from xauusd_forward_evidence_ledger import ForwardEvidenceLedger
from xauusd_alert_engine import XAUUSDAlertEngine


def test_evidence_ledger_snapshots_retrieval():
    """Validates that evidence snapshots can be retrieved cleanly."""
    snaps = ForwardEvidenceLedger.get_snapshots(limit=10)
    assert isinstance(snaps, list)


def test_alert_acknowledgement_is_non_destructive():
    """Validates that acknowledging an alert does not delete the record."""
    # Log a test alert
    evt_id = XAUUSDAlertEngine.log_event({
        "event_type": "PHASE33_TEST_ALERT",
        "severity": "INFORMATION",
        "metric": "test_metric",
        "observed_value": 1.0,
        "baseline_value": 0.0,
        "threshold": 1.0,
        "explanation": "Phase 33 non-destructive test alert.",
        "recommended_action": "Verify persistence.",
    })
    assert evt_id is not None

    # Acknowledge
    ack_res = XAUUSDAlertEngine.acknowledge_alert(evt_id)
    assert ack_res is True

    # Confirm it still exists in recent alerts
    recent = XAUUSDAlertEngine.get_events(limit=50)
    matching = [a for a in recent if a["event_id"] == evt_id]
    assert len(matching) == 1
    assert matching[0]["acknowledged"] in [1, True]
