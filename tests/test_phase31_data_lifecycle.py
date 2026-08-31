"""
Phase 31 — Forward Data Lifecycle & Observation Provenance Test Suite
Validates observation lifecycle tracking, execution separation (trades vs timeouts vs rejections),
provenance verification, and rejection of corrupted/malformed observations.
"""

import pytest
import time
from datetime import datetime, timezone
from xauusd_operational_monitor import (
    ForwardDataLifecycleTracker,
    ObservationProvenanceAuditor,
    FROZEN_CONTRACT_HASH,
)


def test_forward_data_lifecycle_metrics():
    """Validates lifecycle metrics separation between completed trades, timeouts, and rejections."""
    lifecycle = ForwardDataLifecycleTracker.get_lifecycle_metrics("XAUUSD")
    assert isinstance(lifecycle, dict)
    assert "evaluations_total" in lifecycle
    assert "valid_completed_trades_n" in lifecycle
    assert "paper_observations" in lifecycle
    assert "shadow_observations" in lifecycle
    assert lifecycle["execution_separation_verified"] is True
    assert lifecycle["unfilled_limits_counted_as_loss"] is False

    paper = lifecycle["paper_observations"]
    assert "total_recorded" in paper
    assert "completed_trades" in paper
    assert "timeouts" in paper
    assert "invalidations" in paper
    assert "rejected_setups" in paper


def test_observation_provenance_valid_record():
    """Validates that a correctly structured forward observation passes provenance auditing."""
    valid_obs = {
        "signal_id": "SIG_VALID_20260831_001",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": "XAUUSD",
        "execution_mode": "PAPER",
        "requested_entry": 2415.50,
        "stop_loss": 2410.00,
        "take_profit": 2430.00,
        "planned_rr": 2.64,
        "status": "FILLED",
    }
    is_valid, errors = ObservationProvenanceAuditor.validate_observation_dict(valid_obs)
    assert is_valid is True
    assert len(errors) == 0


def test_observation_provenance_rejects_missing_fields():
    """Validates that observations missing observation_id or timestamp are rejected."""
    bad_obs_no_id = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": "XAUUSD",
        "execution_mode": "PAPER",
    }
    is_valid, errors = ObservationProvenanceAuditor.validate_observation_dict(bad_obs_no_id)
    assert is_valid is False
    assert "MISSING_OBSERVATION_ID" in errors

    bad_obs_no_ts = {
        "signal_id": "SIG_TEST_002",
        "symbol": "XAUUSD",
        "execution_mode": "PAPER",
    }
    is_valid, errors = ObservationProvenanceAuditor.validate_observation_dict(bad_obs_no_ts)
    assert is_valid is False
    assert "MISSING_TIMESTAMP" in errors


def test_observation_provenance_rejects_future_timestamp():
    """Validates that observations with future timestamps (>5m ahead) are rejected."""
    future_time = datetime.fromtimestamp(time.time() + 3600, tz=timezone.utc).isoformat()
    future_obs = {
        "signal_id": "SIG_FUTURE_003",
        "timestamp": future_time,
        "symbol": "XAUUSD",
        "execution_mode": "PAPER",
        "requested_entry": 2420.00,
        "stop_loss": 2415.00,
        "take_profit": 2430.00,
    }
    is_valid, errors = ObservationProvenanceAuditor.validate_observation_dict(future_obs)
    assert is_valid is False
    assert "FUTURE_TIMESTAMP_DETECTED" in errors


def test_observation_provenance_rejects_invalid_prices():
    """Validates that non-positive entry, stop, or target prices are rejected."""
    invalid_price_obs = {
        "signal_id": "SIG_INVALID_PRICE_004",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": "XAUUSD",
        "execution_mode": "PAPER",
        "requested_entry": -2400.00,
        "stop_loss": -2405.00,
        "take_profit": -2390.00,
    }
    is_valid, errors = ObservationProvenanceAuditor.validate_observation_dict(invalid_price_obs)
    assert is_valid is False
    assert any("INVALID_ENTRY_PRICE" in e for e in errors)


def test_all_persisted_forward_provenance_audit():
    """Audits all existing forward observation database rows for provenance integrity."""
    audit_res = ObservationProvenanceAuditor.audit_all_forward_provenance()
    assert isinstance(audit_res, dict)
    assert "total_observations_audited" in audit_res
    assert "duplicates_detected" in audit_res
    assert len(audit_res["duplicates_detected"]) == 0
    assert audit_res["contract_verified"] is True
    assert audit_res["status"] == "PASS"
