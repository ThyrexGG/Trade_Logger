"""
Tests for Phase 29 Explainability, Prohibited Phrases, and 28-Section Dossier.
Ensures zero fake certainty words, scientific humility, and presence of all 28 dossier sections.
"""

import pytest
from xauusd_review_package import HumanReviewPackageGenerator


def test_review_package_28_sections():
    pkg = HumanReviewPackageGenerator.generate_review_package(mode="PAPER")
    
    assert len(pkg["sections"]) == 28
    titles = [s["title"] for s in pkg["sections"]]
    assert any("21. Regime Coverage" in t for t in titles)
    assert any("22. Regime Concentration" in t for t in titles)
    assert any("23. Rolling Stability" in t for t in titles)
    assert any("24. Chronological Stability" in t for t in titles)
    assert any("25. Execution Stress" in t for t in titles)
    assert any("26. Drawdown & Recovery" in t for t in titles)
    assert any("27. Reproducibility Audit" in t for t in titles)
    assert any("28. Evidence Invalidation Conditions" in t for t in titles)


def test_prohibited_certainty_phrases_in_dossier():
    pkg = HumanReviewPackageGenerator.generate_review_package(mode="PAPER")
    md = HumanReviewPackageGenerator.export_markdown_report(pkg)
    
    prohibited_phrases = ["guaranteed", "proven profitable", "is certain", "certain return", "safe to trade", "will make money"]
    for phrase in prohibited_phrases:
        assert phrase not in md.lower()
        
    assert "LIVE AUTOMATION: DISABLED PERMANENTLY" in md
    assert "Live broker transmission is strictly blocked." in md
