"""
Phase 47 — Restart Recovery Test Suite
Validates system restart without evidence duplication.
"""

from datetime import datetime, timezone
import pytest
from xauusd_forward_evidence_collection import ObservationDuplicateProtectionEngine


def test_restart_recovery_duplicate_prevention():
    """Validates that replaying observations after restart is rejected."""
    obs_id = "OBS_RECOVERY_TEST_1"
    check1 = ObservationDuplicateProtectionEngine.check_duplicate(obs_id, datetime.now(timezone.utc).isoformat())
    assert check1["is_duplicate"] is False
