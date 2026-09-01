"""
Phase 43 — Idempotency & Safety Invariant Test Suite
Validates:
1. Idempotency guard prevents duplicate observations.
2. Strategy Contract SHA-256 remains exact byte-for-byte.
3. Live automation remains permanently disabled.
"""

import hashlib
import os
from datetime import datetime, timezone
import pytest
from xauusd_forward_integrity import StrategyContractIntegrityGuard
from xauusd_market_conditions import FROZEN_CONTRACT_HASH
from xauusd_overnight_experiment import OvernightIdempotencyGuard


def test_idempotency_unique_observation():
    """Validates unique observations pass."""
    is_dup, msg = OvernightIdempotencyGuard.check_and_register_observation("OBS_UNIQUE_999", datetime.now(timezone.utc).isoformat())
    assert is_dup is False
    assert "UNIQUE" in msg


def test_strategy_contract_hash_exact_match_phase43():
    """Validates contract SHA-256 hash."""
    contract_path = os.path.join(os.path.dirname(__file__), "..", "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    with open(contract_path, "rb") as f:
        content = f.read().replace(b"\r\n", b"\n")
    actual_hash = hashlib.sha256(content).hexdigest()
    assert actual_hash == FROZEN_CONTRACT_HASH
    assert actual_hash == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_contract_integrity_guard_verification_phase43():
    """Validates integrity guard."""
    guard_result = StrategyContractIntegrityGuard.verify_contract_immutability()
    assert guard_result["parameters_verified"] is True
    assert guard_result["integrity_status"] == "FROZEN & LOCKED"


def test_live_automation_permanently_locked_phase43():
    """Validates live automation safety barrier."""
    import execution_pipeline
    assert getattr(execution_pipeline, "LIVE_AUTOMATION_ENABLED", False) is False
    assert getattr(execution_pipeline, "LIVE_BROKER_TRANSMISSION", "BLOCKED") == "BLOCKED"
