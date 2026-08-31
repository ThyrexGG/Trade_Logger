"""
Tests for Phase 29 Dataset Fingerprinting & Invalidation Conditions.
Ensures cryptographic hash protection and explicit governance invalidation rules.
"""

import pytest
from xauusd_forward_reproducibility import ForwardDatasetFingerprinter, EvidenceInvalidationEngine


def test_dataset_fingerprinting():
    fp = ForwardDatasetFingerprinter.generate_fingerprint(mode="PAPER")
    
    assert "dataset_sha256" in fp
    assert len(fp["dataset_sha256"]) == 64  # SHA-256 hex string
    assert "observation_count" in fp
    assert "contract_sha256" in fp
    assert len(fp["contract_sha256"]) == 64
    assert fp["is_valid"] is True


def test_invalidation_matrix_completeness():
    matrix = EvidenceInvalidationEngine.get_invalidation_matrix()
    
    assert len(matrix) >= 8
    for item in matrix:
        assert "condition_id" in item
        assert "condition" in item
        assert "why_it_matters" in item
        assert "nature" in item
        assert "governance_action" in item


def test_counterfactual_scenarios():
    scenarios = EvidenceInvalidationEngine.get_counterfactual_scenarios()
    
    assert len(scenarios) == 5
    exp_returns = [s["hypothetical_exp_r"] for s in scenarios]
    assert "+0.600 R" in exp_returns
    assert "+0.000 R" in exp_returns
    assert "-0.200 R" in exp_returns
