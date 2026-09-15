"""
Test Suite: Phase 56 Data Quality & Source Provenance
=====================================================
Validates overall data quality scoring, timestamp verification,
and truthful provider reporting.
"""
from datetime import datetime, timedelta, timezone

from macro_intelligence_engine import (
    EconomicDataRegistry,
    DataFreshnessAuditor,
    MacroReleaseRecord,
)


def _record(age_days: float, *, revised: bool = False) -> MacroReleaseRecord:
    """A synthetic release exactly `age_days` old. No `metric` in
    INDICATOR_METADATA means the auditor falls back to MONTHLY thresholds
    (FRESH <=14d, AGING <=45d, STALE >45d) -- exactly what this test wants
    full control over."""
    ts = (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
    return MacroReleaseRecord(
        metric="TEST_METRIC", country="USD", period="2026-08",
        release_timestamp=ts, forecast=None, actual=1.0, previous=1.0,
        unit="pct", source="Test Source", source_timestamp=ts,
        revision_status="REVISED" if revised else "INITIAL",
    )


def test_data_quality_scoring_against_known_feed_states():
    """The scoring in audit_releases_freshness is a deterministic function of
    each release's age and revision status (see macro_intelligence_engine.py)
    -- so exercise it with synthetic, controlled-age records rather than
    whatever the real registry's live release calendar happens to look like
    today. A fixed "must score >= 80" assertion against real data flakes with
    the calendar: a batch of legitimately-aging monthly releases (e.g. FOMC,
    whose ~6-8 week cadence routinely exceeds the 45-day MONTHLY threshold)
    correctly, and appropriately, drags the score down on some days and not
    others -- that's the auditor doing its job, not a bug to assert away.
    """
    releases = [
        _record(1),              # MONTHLY, <=14d -> FRESH (95)
        _record(40),              # MONTHLY, <=45d -> AGING (80)
        _record(60),              # MONTHLY, >45d -> STALE (0 credit)
        _record(60, revised=True),  # revision_status wins regardless of age -> REVISED (90)
    ]
    audit = DataFreshnessAuditor.audit_releases_freshness(releases)

    assert audit["total_indicators_tracked"] == 4
    assert len(audit["audited_records"]) == 4
    assert audit["freshness_breakdown"] == {
        "LIVE": 0, "FRESH": 1, "AGING": 1, "STALE": 1,
        "DELAYED": 0, "REVISED": 1, "UNAVAILABLE": 0, "INVALID": 0,
    }
    # (95 + 80 + 0 + 90) / 4 = 66.25 -> truncated to 66 by the auditor's int()
    assert audit["overall_data_quality"] == 66

    for rec in audit["audited_records"]:
        assert "source" in rec
        assert "quality_score" in rec
        assert "age_days" in rec


def test_live_registry_audit_is_well_formed():
    """Smoke-checks the real registry -> auditor path still returns a
    well-formed, internally-consistent result. Deliberately does not assert
    a quality floor -- see test_data_quality_scoring_against_known_feed_states
    for that, against synthetic data the test controls."""
    releases = EconomicDataRegistry.get_releases_as_of()
    audit = DataFreshnessAuditor.audit_releases_freshness(releases)

    assert 0 <= audit["overall_data_quality"] <= 100
    assert audit["total_indicators_tracked"] >= 10
    assert len(audit["audited_records"]) == audit["total_indicators_tracked"]
    assert sum(audit["freshness_breakdown"].values()) == audit["total_indicators_tracked"]
    for rec in audit["audited_records"]:
        assert "source" in rec
        assert "quality_score" in rec
        assert "age_days" in rec
        assert rec["age_days"] >= 0
