"""
Phase 50 — Tests for Simulated Paper & Shadow Execution with Live Isolation
"""

import pytest
from xauusd_forward_lifecycle import ForwardExecutionLifecycleEngine
from xauusd_forward_end_to_end_proof import Phase50SafetyBarrier


def test_execution_mode_validation():
    """Validates that only PAPER and SHADOW execution modes are allowed."""
    assert ForwardExecutionLifecycleEngine.validate_execution_mode("PAPER") == "PAPER"
    assert ForwardExecutionLifecycleEngine.validate_execution_mode("SHADOW") == "SHADOW"
    with pytest.raises(ValueError):
        ForwardExecutionLifecycleEngine.validate_execution_mode("LIVE_BROKER")


def test_live_safety_barrier_fail_closed():
    """Validates fail-closed live execution barrier."""
    safety = Phase50SafetyBarrier.verify_safety_barrier()
    assert safety["is_safe"] is True
    assert safety["live_automation_enabled"] is False
    assert safety["broker_transmission"] == "BLOCKED"
