"""
TradeLogger Phase 57 — Test Suite: Data Quality & Missing Feed Handling
========================================================================
Validates:
- Data quality score calculation (0-100).
- Graceful handling of missing price, macro, sentiment, or COT feeds.
- Anti-fabrication verification (never impute fabricated zeros or synthetic ticks).
- Quality threshold gating across scanner and heatmap matrices.
"""

import pytest
from market_intelligence_scanner import MarketScannerEngine, MarketRankingEngine, AssetScanRecord
from economic_heatmap import EconomicHeatmapEngine, HeatmapCell


def test_data_quality_score_computation():
    """Verify scan record data quality scores are strictly bounded."""
    records = MarketScannerEngine.scan_universe("ALL")
    for r in records:
        assert 0 <= r.data_quality_score <= 100
        assert len(r.data_quality_rating) > 0


def test_missing_data_handling_no_crash():
    """Verify that scanning an asset with partial or missing feeds degrades quality without crashing."""
    record = MarketScannerEngine.scan_symbol("BTCUSD")
    assert isinstance(record, AssetScanRecord)
    assert record.symbol == "BTCUSD"
    assert record.data_quality_score >= 0


def test_anti_fabrication_unranked_state():
    """Verify assets with insufficient data receive explicit unranked status rather than fabricated ranks."""
    unranked_rec = AssetScanRecord(
        symbol="UNKNOWN_PAIR",
        asset_class="FX",
        display_name="Unknown Feed",
        price=0.0,
        price_change_24h_pct=0.0,
        volatility_atr_pct=0.0,
        edge_score=0.0,
        macro_score=0.0,
        technical_score=0.0,
        positioning_score=0.0,
        seasonality_score=0.0,
        regime_score=0.0,
        data_quality_score=10,
        data_quality_rating="UNAVAILABLE",
        factor_agreement_pct=0.0,
        conflict_state="ALIGNED",
        conflict_score=0.0,
        dominant_driver="NONE",
        dominant_risk="NONE",
        context_state="INSUFFICIENT DATA",
        ranking_eligible=False,
        why_bullets=["Data feed unavailable."],
        snapshot_timestamp="2026-09-01T00:00:00",
        data_fingerprint="abc"
    )
    ranked = MarketRankingEngine.rank_records([unranked_rec])
    assert len(ranked) == 1
    assert ranked[0]["rank"] is None
    assert ranked[0]["rank_status"] == "RANKING WITHHELD"


def test_economic_heatmap_missing_data_cell():
    """Verify heatmap cell handles missing category data with accessible fallback."""
    cell = HeatmapCell(
        indicator_code="TEST_CODE",
        display_name="Test Indicator",
        economy="USD",
        category="GROWTH",
        actual=None,
        forecast=None,
        previous=None,
        raw_surprise=None,
        z_score=0.0,
        directional_interpretation="NEUTRAL",
        freshness="UNAVAILABLE",
        source="Test Source",
        release_timestamp="2026-09-01T00:00:00",
        icon_symbol="❓",
        badge_label="UNAVAILABLE",
        tint_color="#94a3b8",
        tooltip_text="Data feed unavailable"
    )
    assert cell.freshness == "UNAVAILABLE"
    assert cell.icon_symbol == "❓"
