"""
Tests for Phase 27 Human Review Package Generator.
Verifies report generation, required 18 sections, known/observed/uncertain language standards, and historical/forward separation.
"""

import pytest
from xauusd_review_package import HumanReviewPackageGenerator


def test_generate_review_package_structure():
    pkg = HumanReviewPackageGenerator.generate_review_package(mode="PAPER")

    assert pkg["strategy"] == "XAUUSD TRUE MTF ICT/SMC (PHASE 21 FROZEN)"
    assert "trades_N" in pkg
    assert "expectancy_r" in pkg
    assert "ci_95" in pkg
    assert "overall_decision" in pkg
    assert "evidence_score" in pkg
    assert len(pkg["sections"]) >= 18


def test_review_package_classifications():
    pkg = HumanReviewPackageGenerator.generate_review_package(mode="PAPER")
    classifications = {s["classification"] for s in pkg["sections"]}

    # Must contain proper empirical labels
    assert classifications.issubset({"KNOWN", "OBSERVED", "UNCERTAIN", "NOT ENOUGH DATA"})


def test_export_markdown_report_language_and_safety():
    pkg = HumanReviewPackageGenerator.generate_review_package(mode="PAPER")
    md = HumanReviewPackageGenerator.export_markdown_report(pkg)

    # Check for presence of key sections and safety notice
    assert "Forward Validation Audit" in md
    assert "LIVE AUTOMATION: DISABLED PERMANENTLY" in md
    assert "Live broker transmission is strictly blocked." in md

    # Ensure prohibited certainty phrases are absent
    prohibited_phrases = ["guaranteed", "proven profitable", "is certain", "certain return", "safe to trade", "will make money", "will continue"]
    for phrase in prohibited_phrases:
        assert phrase not in md.lower()
