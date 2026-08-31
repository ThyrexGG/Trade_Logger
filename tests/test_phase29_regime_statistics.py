"""
Tests for Phase 29 Regime Statistical Protections & Concentration Audit.
Ensures small regime buckets are explicitly protected from premature conclusions.
"""

import pytest
import pandas as pd
from xauusd_forward_regime_coverage import RegimeStatisticalProtector, RegimeConcentrationAuditor


def test_regime_sample_size_protections():
    p_tiny = RegimeStatisticalProtector.get_sample_protection(n=8)
    assert p_tiny["tier"] == "INSUFFICIENT DATA"
    assert "too few observations" in p_tiny["human_meaning"].lower()

    p_limited = RegimeStatisticalProtector.get_sample_protection(n=15)
    assert p_limited["tier"] == "LIMITED OBSERVATIONS"

    p_early = RegimeStatisticalProtector.get_sample_protection(n=25)
    assert p_early["tier"] == "EARLY REGIME EVIDENCE"

    p_full = RegimeStatisticalProtector.get_sample_protection(n=35)
    assert p_full["tier"] == "REGIME SAMPLE"


def test_regime_concentration_auditor():
    # Synthetic session aggregates with extreme concentration
    session_aggs_heavy = [
        {"regime_name": "LONDON/NY OVERLAP", "trade_pct": 65.0, "r_contribution_pct": 85.0},
        {"regime_name": "LONDON", "trade_pct": 25.0, "r_contribution_pct": 10.0},
        {"regime_name": "NEW YORK", "trade_pct": 10.0, "r_contribution_pct": 5.0}
    ]
    df_dummy = pd.DataFrame({"realized_r": [1.0] * 10})

    audit_res = RegimeConcentrationAuditor.audit_concentration(df_dummy, session_aggs_heavy)
    assert audit_res["concentration_level"] == "HIGH CONTRIBUTION CONCENTRATION"
    assert audit_res["dominant_session"] == "LONDON/NY OVERLAP"
    assert audit_res["dominant_r_pct"] == 85.0
    assert "large portion" in audit_res["interpretation"].lower()
