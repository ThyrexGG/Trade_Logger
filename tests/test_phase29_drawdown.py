"""
Tests for Phase 29 Consecutive Loss, Drawdown & Recovery Audit.
Verifies streak tracking, equity curve drawdown measurements, recovery factors, and classification tiers.
"""

import pytest
from xauusd_forward_drawdown_audit import ForwardDrawdownAuditor


def test_drawdown_auditor_calculations():
    # Sequence: +2R, -1R, -1R, +3R, -1R, -1R, -1R, +4R
    returns = [2.0, -1.0, -1.0, 3.0, -1.0, -1.0, -1.0, 4.0]
    audit = ForwardDrawdownAuditor.audit_drawdown(returns)

    assert audit["trades_n"] == 8
    assert audit["max_consecutive_losses"] == 3
    assert audit["max_consecutive_wins"] == 1
    assert audit["max_drawdown_r"] == 3.0
    assert audit["drawdown_status"] == "NORMAL"
    assert audit["recovery_factor"] > 0


def test_drawdown_classification_tiers():
    # 5 consecutive losses of 1R -> DD = 5R -> ELEVATED
    ret_elevated = [-1.0] * 5
    a_elevated = ForwardDrawdownAuditor.audit_drawdown(ret_elevated)
    assert a_elevated["drawdown_status"] == "ELEVATED"

    # 8 consecutive losses of 1R -> DD = 8R -> STRESS
    ret_stress = [-1.0] * 8
    a_stress = ForwardDrawdownAuditor.audit_drawdown(ret_stress)
    assert a_stress["drawdown_status"] == "STRESS"

    # 13 consecutive losses of 1R -> DD = 13R -> SEVERE
    ret_severe = [-1.0] * 13
    a_severe = ForwardDrawdownAuditor.audit_drawdown(ret_severe)
    assert a_severe["drawdown_status"] == "SEVERE"
