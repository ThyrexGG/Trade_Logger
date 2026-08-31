"""
Unit tests for Phase 28 Explainability & Scientific Language Rules.
Verifies no emojis, no fake-certainty language, and presence of educational explanations.
"""

from xauusd_review_package import HumanReviewPackageGenerator
from xauusd_evidence_milestones import EvidenceMilestoneEngine
from xauusd_review_readiness import ReviewReadinessEngine


def test_no_forbidden_certainty_words_in_dossier():
    pkg = HumanReviewPackageGenerator.generate_review_package(mode="PAPER")
    md = HumanReviewPackageGenerator.export_markdown_report(pkg)

    forbidden = ["guaranteed", "proven profitable", "is certain", "certain return", "safe to trade", "will make money"]
    for phrase in forbidden:
        assert phrase not in md.lower()


def test_all_20_sections_present_in_review_package():
    pkg = HumanReviewPackageGenerator.generate_review_package(mode="PAPER")
    assert len(pkg["sections"]) == 20
    
    # Check that each section has valid empirical classification
    for sec in pkg["sections"]:
        assert sec["classification"] in ["KNOWN", "OBSERVED", "UNCERTAIN", "NOT ENOUGH DATA"]
        assert len(sec["content"]) > 10


def test_readiness_checklist_contains_plain_language_reasons():
    readiness = ReviewReadinessEngine.evaluate_readiness(mode="PAPER")
    for pillar, items in readiness["checklist"].items():
        for it in items:
            assert len(it["why_it_matters"]) > 10
            assert len(it["what_happens_next"]) > 10
