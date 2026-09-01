"""
Test Suite: Phase 56 Economic Surprise Engine
=============================================
Validates surprise calculation (actual - forecast), unit-aware normalization,
z-score deviations, qualitative market implications, and aggregate surprise momentum.
"""

import pytest
from macro_intelligence_engine import (
    MacroReleaseRecord,
    EconomicSurpriseEngine
)


def test_positive_and_negative_surprises():
    """Verifies basic actual - forecast calculation and state assignment."""
    # 1. Inflation downside surprise (CPI forecast 3.4%, actual 3.2%)
    cpi_rec = MacroReleaseRecord(
        metric="CPI", country="USD", period="2026-08",
        release_timestamp="2026-08-14T12:30:00Z",
        forecast=3.4, actual=3.2, previous=3.3, unit="%",
        source="BLS", source_timestamp="2026-08-14T12:30:05Z"
    )
    res = EconomicSurpriseEngine.evaluate_release_surprise(cpi_rec)
    assert res["raw_surprise"] == -0.2
    assert "NEGATIVE SURPRISE" in res["surprise_state"]
    assert "DOVISH" in res["direction"]
    assert res["z_score"] < 0

    # 2. Growth upside surprise (GDP forecast 2.0%, actual 3.0%)
    gdp_rec = MacroReleaseRecord(
        metric="GDP", country="USD", period="2026-Q2",
        release_timestamp="2026-08-27T12:30:00Z",
        forecast=2.0, actual=3.0, previous=1.8, unit="%",
        source="BEA", source_timestamp="2026-08-27T12:30:05Z"
    )
    res_gdp = EconomicSurpriseEngine.evaluate_release_surprise(gdp_rec)
    assert res_gdp["raw_surprise"] == 1.0
    assert "POSITIVE SURPRISE" in res_gdp["surprise_state"]
    assert "BULLISH GROWTH" in res_gdp["direction"]


def test_inline_and_missing_values():
    """Verifies inline and missing/pending economic releases."""
    inline_rec = MacroReleaseRecord(
        metric="CORE_PCE", country="USD", period="2026-07",
        release_timestamp="2026-08-28T12:30:00Z",
        forecast=2.6, actual=2.6, previous=2.7, unit="%",
        source="BEA", source_timestamp="2026-08-28T12:30:05Z"
    )
    res_in = EconomicSurpriseEngine.evaluate_release_surprise(inline_rec)
    assert res_in["raw_surprise"] == 0.0
    assert res_in["surprise_state"] == "INLINE"

    pending_rec = MacroReleaseRecord(
        metric="CPI", country="USD", period="2026-09",
        release_timestamp="2026-09-15T12:30:00Z",
        forecast=3.0, actual=None, previous=2.9, unit="%",
        source="BLS", source_timestamp="2026-09-15T12:30:05Z"
    )
    res_pen = EconomicSurpriseEngine.evaluate_release_surprise(pending_rec)
    assert res_pen["surprise_state"] == "UNAVAILABLE"


def test_country_surprise_aggregation():
    """Verifies country-wide aggregate surprise momentum."""
    agg = EconomicSurpriseEngine.evaluate_country_surprises(country="USD")
    assert "surprise_score" in agg
    assert "surprise_momentum" in agg
    assert isinstance(agg["surprises"], list)
    assert len(agg["surprises"]) > 0
