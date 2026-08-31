"""
Tests for Phase 29 Independent Reproducibility & Metric Reconstruction.
Ensures forward analytical statistics can be 100% reconstructed from raw journal records.
"""

import pytest
from xauusd_forward_reproducibility import ForwardReproducibilityAuditor


def test_independent_reproducibility_audit():
    rep = ForwardReproducibilityAuditor.audit_reproducibility(mode="PAPER")
    
    assert rep["verdict"] in {"REPRODUCIBLE", "REPRODUCTION DIFFERENCE", "REPRODUCTION FAILED"}
    assert rep["verdict"] == "REPRODUCIBLE"
    assert len(rep["discrepancies"]) == 0
    assert "fingerprint" in rep
    assert rep["fingerprint"]["is_valid"] is True
