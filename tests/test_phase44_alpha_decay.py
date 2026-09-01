"""
Phase 44 — Alpha Decay Monitor & Data Quality Gate Test Suite
Validates conservative multi-factor alpha decay state evaluation and data quality filtering.
"""

import pandas as pd
import pytest
from xauusd_alpha_decay_monitor import (
    AlphaDecayMonitor,
    DataQualityGate,
    ResearchInterpretationSynthesizer,
)


def test_alpha_decay_evaluation_empty_dataset():
    """Validates alpha decay evaluation for N = 0."""
    eval_res = AlphaDecayMonitor.evaluate_alpha_decay("XAUUSD")

    assert "snapshot_id" in eval_res
    assert "decay_state" in eval_res
    assert eval_res["forward_n"] == 0
    assert "INSUFFICIENT FORWARD EVIDENCE" in eval_res["decay_state"]
    assert eval_res["contract_hash"] == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    assert eval_res["live_automation"] == "DISABLED_PERMANENTLY"


def test_data_quality_gate_exclusion():
    """Validates data quality gate excludes malformed/non-numeric rows."""
    raw_data = [
        {"signal_id": "OBS_VALID_1", "status": "COMPLETED", "r_multiple": 1.5},
        {"signal_id": "OBS_BAD_1", "status": "TIMEOUT", "r_multiple": 0.0},
        {"signal_id": "OBS_BAD_2", "status": "COMPLETED", "r_multiple": "INVALID_TEXT"},
    ]
    df_raw = pd.DataFrame(raw_data)
    clean_df, excluded = DataQualityGate.filter_observations_for_alpha_monitoring(df_raw)

    assert len(clean_df) == 1
    assert len(excluded) == 2
    assert clean_df.iloc[0]["signal_id"] == "OBS_VALID_1"


def test_research_interpretation_synthesizer_n_bounded():
    """Validates that plain-language interpretation is bounded strictly by sample size."""
    assert "N = 0" in ResearchInterpretationSynthesizer.synthesize_interpretation(0, "INSUFFICIENT DATA")
    assert "N = 8" in ResearchInterpretationSynthesizer.synthesize_interpretation(8, "EARLY OBSERVATIONS")
    assert "N = 37" in ResearchInterpretationSynthesizer.synthesize_interpretation(37, "DEVELOPING")
    assert "N = 120" in ResearchInterpretationSynthesizer.synthesize_interpretation(120, "SUBSTANTIAL")
