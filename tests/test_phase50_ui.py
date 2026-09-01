"""
Phase 50 — Tests for UI Data Structures & Component Formats
"""

import pytest
import pandas as pd
from xauusd_forward_end_to_end_proof import Phase50Facade


def test_phase50_ui_data_structures():
    """Validates complete Phase 50 UI payload generation."""
    state = Phase50Facade.get_phase50_full_state(mode="PAPER", symbol="XAUUSD")
    assert isinstance(state, dict)
    assert "pipeline" in state
    assert "supervisor" in state
    assert "heartbeats" in state
    assert "stages" in state
    assert "reconciliation" in state
    assert "dataset" in state
    assert "safety" in state

    # Validate dataframe conversions
    df_stages = pd.DataFrame(state["stages"])
    assert not df_stages.empty
    assert len(df_stages) == 9

    df_hb = pd.DataFrame(state["heartbeats"]["subsystems"])
    assert not df_hb.empty
    assert len(df_hb) == 8
