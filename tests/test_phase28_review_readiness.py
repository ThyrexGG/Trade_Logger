"""
Unit tests for Phase 28 Review Readiness Engine.
Verifies the deterministic 18-point checklist and explicit uncertainty engine.
"""

from xauusd_review_readiness import ReviewReadinessEngine


def test_review_readiness_structure():
    readiness = ReviewReadinessEngine.evaluate_readiness(mode="PAPER")
    
    assert "verdict" in readiness
    assert readiness["verdict"] in ["NOT READY", "READY FOR HUMAN REVIEW", "BLOCKED BY RESEARCH INTEGRITY"]
    assert readiness["total_items"] == 18
    assert readiness["pass_count"] + readiness["waiting_count"] + readiness["blocked_count"] == 18
    assert "statistical_evidence" in readiness["checklist"]
    assert "execution_evidence" in readiness["checklist"]
    assert "distribution_evidence" in readiness["checklist"]
    assert "integrity_evidence" in readiness["checklist"]


def test_uncertainty_analysis_presence_and_completeness():
    readiness = ReviewReadinessEngine.evaluate_readiness(mode="PAPER")
    un = readiness["uncertainty_analysis"]

    assert "what_we_know" in un
    assert "what_we_do_not_know" in un
    assert "what_we_need_next" in un

    assert len(un["what_we_know"]) >= 4
    assert len(un["what_we_do_not_know"]) >= 3
    assert len(un["what_we_need_next"]) >= 3

    # Must contain key scientific humility phrases
    joined_unknown = " ".join(un["what_we_do_not_know"]).lower()
    assert "regime" in joined_unknown or "volatility" in joined_unknown or "confidence interval" in joined_unknown
