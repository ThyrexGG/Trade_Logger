"""
Phase 50 — Tests for N=0 -> N=1 First Genuine Observation Supervisor
"""

import pytest
from xauusd_forward_end_to_end_proof import FirstGenuineObservationSupervisor


def test_first_observation_supervisor_evaluation():
    """Validates truthful supervisor evaluation without synthetic manufacturing."""
    state = FirstGenuineObservationSupervisor.evaluate_first_observation_state(mode="PAPER")
    assert isinstance(state, dict)
    assert state["actual_n"] >= 0
    assert "disclaimer" in state
    if state["actual_n"] == 0:
        assert state["milestone_state"] in [
            "WAITING_FOR_GENUINE_FORWARD_OBSERVATION",
            "GENUINE_FORWARD_POSITION_OPEN"
        ]
        assert state["is_n1_captured"] is False
    else:
        assert state["is_n1_captured"] is True
        assert "NOT STRATEGY VALIDATION" in state["disclaimer"]
