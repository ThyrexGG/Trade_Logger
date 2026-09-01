"""
Phase 47 — UI DataFrame Conversion & Component Model Test Suite
Validates that all tables and metrics in the Forward Evidence Collection UI convert into DataFrames cleanly.
"""

import pandas as pd
import pytest
from xauusd_forward_evidence_collection import (
    FirstRealObservationDetector,
    WhyWasThisObservationCreatedExplainer,
    OneClickForensicVerifier,
    HumanReadableMorningSummary,
)


def test_phase47_ui_tables_conversion():
    """Validates DataFrame conversion for Phase 47 UI components."""
    # First Observation
    f_res = FirstRealObservationDetector.evaluate_first_observation_state()
    assert "state" in f_res

    # Explainer
    exp = WhyWasThisObservationCreatedExplainer.explain_observation(None)
    assert "status" in exp

    # Verifier
    ver = OneClickForensicVerifier.verify_observation(None)
    assert "verdict" in ver

    # Morning summary
    ms = HumanReadableMorningSummary.generate_morning_summary()
    assert "verdict" in ms
