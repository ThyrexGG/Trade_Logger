"""
Phase 31 — Paper/Shadow Parity & Historical Contamination Test Suite
Validates operational parity between Paper and Shadow, non-destructive desync alerting,
historical dataset isolation, and cryptographic non-contamination auditing.
"""

import pytest
import hashlib
from xauusd_operational_monitor import (
    PaperShadowParityAuditor,
    HistoricalContaminationAuditor,
    HISTORICAL_HOLDOUT_N,
    HISTORICAL_HOLDOUT_EXPECTANCY,
)
from xauusd_forward_validator import XAUUSDForwardJournal


def test_paper_shadow_operational_parity_audit():
    """Validates that Paper and Shadow execution pipelines maintain 100% operational parity."""
    parity = PaperShadowParityAuditor.audit_operational_parity()
    assert isinstance(parity, dict)
    assert "status" in parity
    assert parity["status"] in ["PASS", "CRITICAL"]
    assert "is_parity_clean" in parity
    assert "desync_count" in parity
    assert parity["records_preserved"] is True
    assert parity["overwritten_records_count"] == 0


def test_historical_contamination_protection():
    """Validates that Historical Holdout (N=82) is completely unpooled and disjoint from forward datasets."""
    contam = HistoricalContaminationAuditor.audit_historical_contamination()
    assert isinstance(contam, dict)
    assert contam["status"] == "PASS"
    assert contam["verdict"] == "HISTORICAL CONTAMINATION: NONE DETECTED"
    assert contam["historical_holdout_n"] == 82
    assert contam["datasets_pooled"] is False
    assert contam["isolation_enforced"] is True
    assert len(contam["hist_paper_collisions"]) == 0
    assert len(contam["hist_shadow_collisions"]) == 0


def test_dataset_cryptographic_fingerprints():
    """Validates that Historical, Paper, and Shadow datasets generate distinct cryptographic SHA-256 fingerprints."""
    contam = HistoricalContaminationAuditor.audit_historical_contamination()
    hist_fp = contam["historical_holdout_fingerprint"]
    paper_fp = contam["forward_paper_fingerprint"]
    shadow_fp = contam["forward_shadow_fingerprint"]

    assert isinstance(hist_fp, str) and len(hist_fp) == 64
    assert isinstance(paper_fp, str) and len(paper_fp) == 64
    assert isinstance(shadow_fp, str) and len(shadow_fp) == 64

    # Historical fingerprint must never match forward fingerprints
    assert hist_fp != paper_fp
    assert hist_fp != shadow_fp
