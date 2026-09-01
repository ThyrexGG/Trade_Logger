"""
Phase 48 — Tests for Paper/Shadow Execution Lifecycle & Live Safety Invariants
"""

import pytest
from xauusd_forward_lifecycle import ForwardExecutionLifecycleEngine


def test_live_automation_permanent_lock():
    safety = ForwardExecutionLifecycleEngine.assert_live_safety()
    assert safety["status"] == "FAIL-CLOSED ACTIVE"
    assert safety["live_automation_enabled"] is False
    assert safety["live_broker_transmission"] == "BLOCKED"
    assert safety["paper_enabled"] is True
    assert safety["shadow_enabled"] is True


def test_execution_mode_validation():
    assert ForwardExecutionLifecycleEngine.validate_execution_mode("paper") == "PAPER"
    assert ForwardExecutionLifecycleEngine.validate_execution_mode("shadow") == "SHADOW"
    assert ForwardExecutionLifecycleEngine.validate_execution_mode("PAPER") == "PAPER"

    with pytest.raises(ValueError):
        ForwardExecutionLifecycleEngine.validate_execution_mode("LIVE")

    with pytest.raises(ValueError):
        ForwardExecutionLifecycleEngine.validate_execution_mode("REAL")
