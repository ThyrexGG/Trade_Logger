"""
Test Suite: Phase 56 Data Freshness & Quality
=============================================
Validates data freshness classification (LIVE, FRESH, AGING, STALE, REVISED),
frequency-aware thresholds, and overall data quality index.
"""

from datetime import datetime, timezone, timedelta
from macro_intelligence_engine import (
    MacroReleaseRecord,
    DataFreshnessAuditor
)


def test_freshness_classification_by_frequency():
    """Verifies that daily, weekly, and monthly releases are audited with appropriate thresholds."""
    now_utc = datetime.now(timezone.utc)

    # 1. Daily release (1 hour old -> LIVE)
    r_live = MacroReleaseRecord(
        metric="YIELD_10Y", country="USD", period="2026-09-01",
        release_timestamp=(now_utc - timedelta(hours=1)).isoformat(),
        forecast=3.90, actual=3.92, previous=3.88, unit="%",
        source="Treasury", source_timestamp=now_utc.isoformat()
    )

    # 2. Monthly release (5 days old -> FRESH)
    r_fresh = MacroReleaseRecord(
        metric="CPI", country="USD", period="2026-08",
        release_timestamp=(now_utc - timedelta(days=5)).isoformat(),
        forecast=3.0, actual=2.9, previous=3.1, unit="%",
        source="BLS", source_timestamp=now_utc.isoformat()
    )

    # 3. Monthly release (20 days old -> AGING)
    r_aging = MacroReleaseRecord(
        metric="NFP", country="USD", period="2026-08",
        release_timestamp=(now_utc - timedelta(days=20)).isoformat(),
        forecast=160.0, actual=145.0, previous=170.0, unit="k",
        source="BLS", source_timestamp=now_utc.isoformat()
    )

    # 4. Monthly release (60 days old -> STALE)
    r_stale = MacroReleaseRecord(
        metric="GDP", country="USD", period="2026-Q1",
        release_timestamp=(now_utc - timedelta(days=60)).isoformat(),
        forecast=2.0, actual=2.1, previous=1.9, unit="%",
        source="BEA", source_timestamp=now_utc.isoformat()
    )

    audit = DataFreshnessAuditor.audit_releases_freshness([r_live, r_fresh, r_aging, r_stale])
    breakdown = audit["freshness_breakdown"]

    assert breakdown["LIVE"] >= 1
    assert breakdown["FRESH"] >= 1
    assert breakdown["AGING"] >= 1
    assert breakdown["STALE"] >= 1
    assert 0 <= audit["overall_data_quality"] <= 100
