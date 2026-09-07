"""
Phase 54 — Tests for Forward Evidence Cockpit Overview & Level 1/2 States
"""

import pytest
from forward_evidence_cockpit import ForwardEvidenceCockpit


def test_cockpit_state_load():
    state = ForwardEvidenceCockpit.load_cockpit_state()
    assert "p49" in state
    assert "p50" in state
    assert "evaluated_at" in state
    assert state["p49"]["contract_valid"] is True


def test_level1_immediate_state_n0_truthful():
    state = ForwardEvidenceCockpit.load_cockpit_state()
    metrics = state["p49"].get("metrics", {})
    n_clean = metrics.get("trades_n", 0)
    assert n_clean >= 0
    # Must not contain fabricated metrics
    if n_clean == 0:
        assert metrics.get("expectancy_r", 0.0) == 0.0
        assert metrics.get("win_rate_pct", 0.0) == 0.0
