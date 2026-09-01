"""
Phase 44 — UI DataFrame Conversion & Model Compatibility Test Suite
Validates that all tables in Long-Term Forward Research UI convert into DataFrames without errors.
"""

import pandas as pd
import pytest
from xauusd_forward_accumulation import (
    ForwardAccumulationEngine,
    SampleMilestoneEngine,
    RollingWindowAnalysisEngine,
    HistoricalVsForwardComparator,
)
from xauusd_alpha_decay_monitor import (
    AlphaDecayMonitor,
    SequentialBlockStabilityEngine,
    RegimeSpecificAlphaDecayEngine,
)


def test_phase44_ui_tables_conversion():
    """Validates DataFrame conversion across Phase 44 components."""
    # Milestones
    milestones = SampleMilestoneEngine.evaluate_all_milestones("XAUUSD")
    df_m = pd.DataFrame(milestones)
    assert not df_m.empty
    assert "target_n" in df_m.columns

    # Rolling Windows
    rolling = RollingWindowAnalysisEngine.compute_rolling_windows()
    df_r = pd.DataFrame(rolling)
    assert not df_r.empty
    assert "window_name" in df_r.columns

    # Alpha Decay Snapshot
    alpha_res = AlphaDecayMonitor.evaluate_alpha_decay("XAUUSD")
    assert "decay_state" in alpha_res

    # Regime Subgroups
    regime = RegimeSpecificAlphaDecayEngine.evaluate_regime_decay()
    df_reg = pd.DataFrame(regime["subgroups"])
    assert not df_reg.empty
    assert "subgroup_name" in df_reg.columns
