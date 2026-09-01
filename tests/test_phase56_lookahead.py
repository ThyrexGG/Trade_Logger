"""
Test Suite: Phase 56 Lookahead Protection
=========================================
Validates that economic releases with release_timestamp > as_of are strictly
inaccessible during historical reconstruction.
"""

from datetime import datetime, timezone
from macro_intelligence_engine import (
    MacroReleaseRecord,
    EconomicDataRegistry
)


def test_strict_lookahead_filtering():
    """Verifies that future economic releases are never returned for historical query timestamps."""
    EconomicDataRegistry.reset_registry()

    # Past release (August 14)
    past_rec = MacroReleaseRecord(
        metric="CPI", country="USD", period="2026-08",
        release_timestamp="2026-08-14T12:30:00Z",
        forecast=3.1, actual=2.9, previous=3.2, unit="%",
        source="BLS", source_timestamp="2026-08-14T12:30:05Z"
    )
    # Future release (September 15)
    future_rec = MacroReleaseRecord(
        metric="CPI", country="USD", period="2026-09",
        release_timestamp="2026-09-15T12:30:00Z",
        forecast=3.0, actual=2.8, previous=2.9, unit="%",
        source="BLS", source_timestamp="2026-09-15T12:30:05Z"
    )

    EconomicDataRegistry.register_release(past_rec)
    EconomicDataRegistry.register_release(future_rec)

    # Query as of August 20, 2026
    as_of_aug20 = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    releases_aug20 = EconomicDataRegistry.get_releases_as_of(as_of=as_of_aug20, metric="CPI")

    assert len(releases_aug20) == 1
    assert releases_aug20[0].period == "2026-08"
    assert releases_aug20[0].actual == 2.9

    # Query as of September 20, 2026 (after future release)
    as_of_sep20 = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    releases_sep20 = EconomicDataRegistry.get_releases_as_of(as_of=as_of_sep20, metric="CPI")
    assert len(releases_sep20) == 2
