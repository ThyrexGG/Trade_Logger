"""
Phase 46 — UI DataFrame Conversion & Component Model Test Suite
Validates that all tables and metrics in the Forward Evidence Gate UI convert into DataFrames cleanly.
"""

import pandas as pd
import pytest
from xauusd_forward_decision_gate import (
    EvidenceTierClassifier,
    SampleMilestoneEngineV2,
    ResearchDecisionGateEngine,
    HistoricalVsForwardComparativeEngine,
    WhatCanWeSaySynthesizer,
)


def test_phase46_ui_tables_conversion():
    """Validates DataFrame conversion for Phase 46 UI components."""
    # Milestones
    m_res = SampleMilestoneEngineV2.evaluate_milestones(0)
    df_m = pd.DataFrame(m_res["milestone_cards"])
    assert isinstance(df_m, pd.DataFrame)
    assert len(df_m) == 14

    # Statements
    stmt = WhatCanWeSaySynthesizer.synthesize_statements(0, 0.0)
    assert "permitted_statements" in stmt
    assert "prohibited_claims" in stmt

    # Comparative
    comp = HistoricalVsForwardComparativeEngine.compare_historical_vs_forward()
    assert "consistency" in comp
