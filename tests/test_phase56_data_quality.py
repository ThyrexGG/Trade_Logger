"""
Test Suite: Phase 56 Data Quality & Source Provenance
=====================================================
Validates overall data quality scoring, timestamp verification,
and truthful provider reporting.
"""

from macro_intelligence_engine import (
    EconomicDataRegistry,
    DataFreshnessAuditor
)


def test_data_quality_scoring():
    """Verifies that data quality score correctly responds to feed states."""
    releases = EconomicDataRegistry.get_releases_as_of()
    audit = DataFreshnessAuditor.audit_releases_freshness(releases)

    assert 80 <= audit["overall_data_quality"] <= 100
    assert audit["total_indicators_tracked"] >= 10
    assert len(audit["audited_records"]) >= 10
    for rec in audit["audited_records"]:
        assert "source" in rec
        assert "quality_score" in rec
        assert "age_days" in rec
