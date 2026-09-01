"""
Phase 46 — Evidence Tiers Test Suite
Validates all 12 deterministic evidence tiers (N = 0 to N >= 500).
"""

import pytest
from xauusd_forward_decision_gate import EvidenceTierClassifier


def test_evidence_tiers_classification():
    """Validates evidence tiers across full spectrum of sample sizes."""
    # N = 0
    t0 = EvidenceTierClassifier.classify_tier(0)
    assert t0["tier_code"] == "TIER_0_EMPTY"
    assert "NO FORWARD EVIDENCE" in t0["tier_name"]

    # N = 5
    t1 = EvidenceTierClassifier.classify_tier(5)
    assert t1["tier_code"] == "TIER_1_INITIAL"

    # N = 15
    t2 = EvidenceTierClassifier.classify_tier(15)
    assert t2["tier_code"] == "TIER_2_EARLY"

    # N = 25
    t3 = EvidenceTierClassifier.classify_tier(25)
    assert t3["tier_code"] == "TIER_3_LIMITED"

    # N = 35
    t4 = EvidenceTierClassifier.classify_tier(35)
    assert t4["tier_code"] == "TIER_4_REGIME_EARLY"

    # N = 60
    t5 = EvidenceTierClassifier.classify_tier(60)
    assert t5["tier_code"] == "TIER_5_DEVELOPING"

    # N = 85
    t6 = EvidenceTierClassifier.classify_tier(85)
    assert t6["tier_code"] == "TIER_6_SUBSTANTIAL"

    # N = 110
    t7 = EvidenceTierClassifier.classify_tier(110)
    assert t7["tier_code"] == "TIER_7_STRONGER"

    # N = 175
    t8 = EvidenceTierClassifier.classify_tier(175)
    assert t8["tier_code"] == "TIER_8_ROBUSTNESS"

    # N = 250
    t9 = EvidenceTierClassifier.classify_tier(250)
    assert t9["tier_code"] == "TIER_9_HIGH_CONFIDENCE"

    # N = 350
    t10 = EvidenceTierClassifier.classify_tier(350)
    assert t10["tier_code"] == "TIER_10_EXTENSIVE"

    # N = 600
    t11 = EvidenceTierClassifier.classify_tier(600)
    assert t11["tier_code"] == "TIER_11_LARGE"
