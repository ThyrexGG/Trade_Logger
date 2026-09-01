"""
Test Suite: Phase 56 Economic Revision Awareness
================================================
Validates that economic data revisions are tracked with initial values,
revised values, delta calculation, and immutable observation logging.
"""

from macro_intelligence_engine import (
    MacroReleaseRecord,
    EconomicDataRegistry,
    EconomicSurpriseEngine
)


def test_economic_revision_tracking():
    """Verifies that an update with a revised actual computes delta and marks REVISED."""
    EconomicDataRegistry.reset_registry()

    initial_rec = MacroReleaseRecord(
        metric="GDP", country="USD", period="2026-Q2",
        release_timestamp="2026-08-01T12:30:00Z",
        forecast=2.8, actual=2.8, previous=2.5, unit="%",
        source="BEA Initial", source_timestamp="2026-08-01T12:30:05Z",
        revision_status="INITIAL"
    )
    EconomicDataRegistry.register_release(initial_rec)

    # Subsequent second estimate / revised release
    revised_rec = MacroReleaseRecord(
        metric="GDP", country="USD", period="2026-Q2",
        release_timestamp="2026-08-27T12:30:00Z",
        forecast=2.8, actual=3.0, previous=2.5, unit="%",
        source="BEA Second Estimate", source_timestamp="2026-08-27T12:30:05Z"
    )
    EconomicDataRegistry.register_release(revised_rec)

    releases = EconomicDataRegistry.get_releases_as_of(metric="GDP", country="USD")
    assert len(releases) == 1
    r = releases[0]
    assert r.revision_status == "REVISED"
    assert r.initial_actual == 2.8
    assert r.revised_actual == 3.0
    assert r.revision_delta == 0.2
    assert r.actual == 3.0

    # Surprise engine evaluation reflects revision
    surp = EconomicSurpriseEngine.evaluate_release_surprise(r)
    assert surp["revision_status"] == "REVISED"
    assert surp["initial_actual"] == 2.8
    assert surp["revision_delta"] == 0.2
