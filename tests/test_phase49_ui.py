"""
Phase 49 — Tests for UI Data Structures & Component Formats
"""

import pytest
import pandas as pd
from xauusd_forward_statistical_monitoring import Phase49MonitoringFacade


def test_ui_facade_data_structures():
    """Validates complete Phase 49 UI payload generation."""
    state = Phase49MonitoringFacade.evaluate_full_forward_state(mode="PAPER", symbol="XAUUSD")
    assert isinstance(state, dict)
    assert "dataset" in state
    assert "metrics" in state
    assert "uncertainty" in state
    assert "comparison" in state
    assert "alpha_decay" in state
    assert "milestones" in state
    assert "decision" in state
    assert "live_automation_barrier" in state

    # Test DataFrame conversions
    df_mls = pd.DataFrame(state["milestones"]["milestone_roadmap"])
    assert not df_mls.empty
    assert len(df_mls) == 14

    df_outcomes = pd.DataFrame([state["metrics"]["outcomes"]])
    assert not df_outcomes.empty
