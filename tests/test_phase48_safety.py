"""
Phase 48 — Tests for Safety Invariants, Contract SHA-256 Immutability & Live Barriers
"""

import pytest
import os
import hashlib
from xauusd_forward_lifecycle import (
    ForwardExecutionLifecycleEngine,
    ForwardDatasetIsolationGuard,
    FROZEN_CONTRACT_HASH
)


def test_frozen_contract_hash_integrity():
    contract_path = os.path.join(os.path.dirname(__file__), "..", "PHASE_21_XAUUSD_STRATEGY_CONTRACT.md")
    assert os.path.exists(contract_path)
    with open(contract_path, "rb") as f:
        content = f.read().replace(b"\r\n", b"\n")
        computed_hash = hashlib.sha256(content).hexdigest()
    assert computed_hash == FROZEN_CONTRACT_HASH
    assert computed_hash == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_permanent_live_broker_barrier():
    assert ForwardExecutionLifecycleEngine.LIVE_AUTOMATION_ENABLED is False
    assert ForwardExecutionLifecycleEngine.LIVE_BROKER_TRANSMISSION == "BLOCKED"
    safety = ForwardExecutionLifecycleEngine.assert_live_safety()
    assert safety["live_automation_enabled"] is False
    assert safety["live_broker_transmission"] == "BLOCKED"
