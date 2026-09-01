"""
Phase 47 — Audit Export Test Suite
Validates forensic snapshot creation and reproducibility metadata.
"""

from datetime import datetime, timezone
import pytest
from xauusd_forward_evidence_collection import FirstObservationForensicRecorder


def test_forensic_snapshot_creation():
    """Validates forensic snapshot structure and fingerprinting."""
    obs = {
        "signal_id": "OBS_TEST_FORENSIC_1",
        "entry_time": datetime.now(timezone.utc).isoformat(),
        "entry_price": 2500.0,
        "exit_price": 2515.0,
        "r_multiple": 1.5,
        "session": "NEW YORK",
        "holiday": "NORMAL",
        "news_proximity": "STANDARD"
    }
    snap = FirstObservationForensicRecorder.generate_forensic_snapshot(obs)
    assert "identity" in snap
    assert "market" in snap
    assert "news" in snap
    assert "strategy" in snap
    assert "governance" in snap
    assert "sha256_fingerprint" in snap["governance"]
