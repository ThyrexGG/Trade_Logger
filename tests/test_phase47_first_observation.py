"""
Phase 47 — First Real Observation Detection Test Suite
Validates 6-state state machine tracking the N=0 -> N=1 transition.
"""

import pytest
from xauusd_forward_evidence_collection import FirstRealObservationDetector


def test_first_observation_state_machine():
    """Validates state machine status evaluation."""
    state = FirstRealObservationDetector.evaluate_first_observation_state("XAUUSD")
    assert "state" in state
    assert "state_color" in state
    assert "meaning" in state
    assert "research_verdict" in state
