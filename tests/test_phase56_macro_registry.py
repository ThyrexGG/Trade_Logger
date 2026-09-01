"""
Test Suite: Phase 56 Macro Data Registry
========================================
Validates canonical economic data registration, metric metadata, asset relevance,
and retrieval filters across countries and families.
"""

import pytest
from datetime import datetime, timezone
from macro_intelligence_engine import (
    INDICATOR_METADATA,
    MacroReleaseRecord,
    EconomicDataRegistry
)


def test_indicator_metadata_definitions():
    """Verifies that all core macroeconomic indicators have canonical metadata."""
    expected_metrics = ["CPI", "CORE_CPI", "PPI", "PCE", "CORE_PCE", "GDP", "NFP", "UNEMPLOYMENT", "INTEREST_RATE", "YIELD_10Y"]
    for m in expected_metrics:
        assert m in INDICATOR_METADATA, f"Missing metadata for {m}"
        meta = INDICATOR_METADATA[m]
        assert "family" in meta
        assert "unit" in meta
        assert "std_deviation" in meta
        assert meta["std_deviation"] > 0


def test_economic_data_registry_seeding_and_retrieval():
    """Verifies seeding and filtering by country and family."""
    EconomicDataRegistry.reset_registry()
    EconomicDataRegistry.seed_canonical_registry()

    usd_releases = EconomicDataRegistry.get_releases_as_of(country="USD")
    assert len(usd_releases) >= 10, "Expected at least 10 USD releases"

    eur_releases = EconomicDataRegistry.get_releases_as_of(country="EUR")
    assert len(eur_releases) >= 3, "Expected at least 3 EUR releases"

    gbp_releases = EconomicDataRegistry.get_releases_as_of(country="GBP")
    assert len(gbp_releases) >= 2, "Expected at least 2 GBP releases"

    jpy_releases = EconomicDataRegistry.get_releases_as_of(country="JPY")
    assert len(jpy_releases) >= 2, "Expected at least 2 JPY releases"

    infl_releases = EconomicDataRegistry.get_releases_as_of(family="INFLATION")
    assert len(infl_releases) >= 5, "Expected inflation releases across economies"


def test_custom_release_registration():
    """Verifies custom indicator registration and update."""
    rec = MacroReleaseRecord(
        metric="TEST_METRIC",
        country="USD",
        period="2026-Q3",
        release_timestamp="2026-09-01T12:00:00Z",
        forecast=50.0,
        actual=52.5,
        previous=49.0,
        unit="pts",
        source="Test Source",
        source_timestamp="2026-09-01T12:00:01Z"
    )
    EconomicDataRegistry.register_release(rec)
    fetched = EconomicDataRegistry.get_releases_as_of(metric="TEST_METRIC")
    assert len(fetched) == 1
    assert fetched[0].actual == 52.5
    assert fetched[0].forecast == 50.0
