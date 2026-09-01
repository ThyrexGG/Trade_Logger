"""
Phase 54 — Tests for Stability & Alpha Decay Monitoring
"""

import pytest
from forward_evidence_cockpit import ForwardEvidenceCockpit


def test_alpha_decay_monitor_structure():
    state = ForwardEvidenceCockpit.load_cockpit_state()
    alpha = state["p49"].get("alpha_decay", {})
    assert "decay_state" in alpha
    assert "decay_color" in alpha
    assert "action_required" in alpha
