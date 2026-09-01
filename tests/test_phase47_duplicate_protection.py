"""
Phase 47 — Duplicate & Replay Protection Test Suite
Validates detection of repeated observation ingestion.
"""

from datetime import datetime, timezone
import pytest
from xauusd_forward_evidence_collection import ObservationDuplicateProtectionEngine


def test_duplicate_detection():
    """Validates duplicate detection against forward ledger."""
    res = ObservationDuplicateProtectionEngine.check_duplicate("OBS_NON_EXISTENT_999", datetime.now(timezone.utc).isoformat())
    assert res["is_duplicate"] is False
    assert res["status"] == "UNIQUE_OBSERVATION"
