"""
Phase 54 — Tests for Canonical Statistics & Conservative Uncertainty
"""

import pytest
from forward_evidence_cockpit import ForwardEvidenceCockpit


def test_statistics_uncertainty_structure():
    state = ForwardEvidenceCockpit.load_cockpit_state()
    unc = state["p49"].get("uncertainty", {})
    assert "ci_90_wr" in unc or "ci_95_wr" in unc
    assert "statistical_status" in unc


def test_wilson_ci_calculations():
    from xauusd_forward_statistical_monitoring import ConservativeUncertaintyEngine
    ci_res = ConservativeUncertaintyEngine.evaluate_uncertainty_state(n=10, win_rate_pct=60.0, expectancy_r=0.50, r_values=[0.5]*10)
    assert ci_res["ci_90_wr"][0] > 0
    assert ci_res["ci_90_wr"][1] <= 100
    assert ci_res["statistical_status"] in ["INSUFFICIENT_SAMPLE", "EARLY_SAMPLE"]
