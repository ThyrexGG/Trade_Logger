"""
Phase 42 — Comprehensive Observation Inspector Test Suite
Validates deep 360-degree forensic inspection of forward observation records.
"""

from datetime import datetime, timezone, date
import pytest
from xauusd_master_research_command import ComprehensiveObservationInspector


def test_observation_inspector_complete_payload():
    """Validates observation inspector output structure."""
    sample_obs = {
        "signal_id": "OBS_INSPECT_001",
        "execution_mode": "PAPER",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "requested_entry": 2405.50,
        "stop_loss": 2395.00,
        "take_profit": 2425.00,
        "mtf_layers": {"1d": "BULLISH", "4h": "BULLISH"},
        "session": "LONDON",
        "nearest_event_name": "US PPI"
    }

    inspect_res = ComprehensiveObservationInspector.inspect_observation(sample_obs)

    assert "identity" in inspect_res
    assert "temporal_audit" in inspect_res
    assert "evidence_quality_score" in inspect_res
    assert "information_horizon" in inspect_res
    assert "context_attribution" in inspect_res
    assert inspect_res["identity"]["observation_id"] == "OBS_INSPECT_001"
    assert inspect_res["evidence_quality_score"]["total_score"] >= 70
