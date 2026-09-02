"""
Phase 57: Test Suite for Market Breadth Engine
Verifies:
- Breadth calculation: % Bullish, % Bearish, % Neutral, % Factor Aligned
- Sector / Asset class breakdown accuracy
- Math invariants: Bullish + Bearish + Neutral = 100%
"""

import pytest
from market_intelligence_scanner import MarketBreadthEngine, AssetScanRecord


def _make_sample_records():
    # 4 Bullish, 4 Bearish, 2 Neutral = 10 total
    records = []
    for i in range(4):
        records.append(AssetScanRecord(
            symbol=f"BULL_{i}", asset_class="FX", display_name=f"Bull {i}",
            price=1.0, price_change_24h_pct=1.0, volatility_atr_pct=0.5,
            edge_score=40.0, macro_score=20.0, technical_score=50.0,
            positioning_score=10.0, seasonality_score=0.0, regime_score=10.0,
            data_quality_score=90, data_quality_rating="LIVE",
            factor_agreement_pct=80.0, conflict_state="ALIGNED", conflict_score=10.0,
            dominant_driver="MOMENTUM", dominant_risk="NONE",
            context_state="BULLISH CONTEXT", why_bullets=[], data_fingerprint="f1"
        ))
    for i in range(4):
        records.append(AssetScanRecord(
            symbol=f"BEAR_{i}", asset_class="INDICES", display_name=f"Bear {i}",
            price=1.0, price_change_24h_pct=-1.0, volatility_atr_pct=0.5,
            edge_score=-40.0, macro_score=-20.0, technical_score=-50.0,
            positioning_score=-10.0, seasonality_score=0.0, regime_score=-10.0,
            data_quality_score=90, data_quality_rating="LIVE",
            factor_agreement_pct=80.0, conflict_state="ALIGNED", conflict_score=10.0,
            dominant_driver="MOMENTUM", dominant_risk="NONE",
            context_state="BEARISH CONTEXT", why_bullets=[], data_fingerprint="f2"
        ))
    for i in range(2):
        records.append(AssetScanRecord(
            symbol=f"NEU_{i}", asset_class="METALS", display_name=f"Neu {i}",
            price=1.0, price_change_24h_pct=0.0, volatility_atr_pct=0.5,
            edge_score=2.0, macro_score=0.0, technical_score=0.0,
            positioning_score=0.0, seasonality_score=0.0, regime_score=0.0,
            data_quality_score=90, data_quality_rating="LIVE",
            factor_agreement_pct=40.0, conflict_state="MIXED", conflict_score=30.0,
            dominant_driver="NONE", dominant_risk="NONE",
            context_state="NEUTRAL", why_bullets=[], data_fingerprint="f3"
        ))
    return records


def test_breadth_percentages_sum():
    records = _make_sample_records()
    breadth = MarketBreadthEngine.calculate_breadth(records)

    assert breadth["total_assets"] == 10
    assert breadth["bullish_count"] == 4
    assert breadth["bearish_count"] == 4
    assert breadth["neutral_count"] == 2

    assert pytest.approx(breadth["bullish_pct"], abs=1e-1) == 40.0
    assert pytest.approx(breadth["bearish_pct"], abs=1e-1) == 40.0
    assert pytest.approx(breadth["neutral_pct"], abs=1e-1) == 20.0

    total_sum = breadth["bullish_pct"] + breadth["bearish_pct"] + breadth["neutral_pct"]
    assert pytest.approx(total_sum, abs=1e-1) == 100.0


def test_sector_breadth_breakdown():
    records = _make_sample_records()
    breadth = MarketBreadthEngine.calculate_breadth(records)

    by_class = breadth["by_asset_class"]
    assert "FX" in by_class
    assert by_class["FX"]["total"] == 4
    assert by_class["FX"]["bullish"] == 4

    assert "INDICES" in by_class
    assert by_class["INDICES"]["total"] == 4
    assert by_class["INDICES"]["bearish"] == 4

    assert "METALS" in by_class
    assert by_class["METALS"]["total"] == 2
    assert by_class["METALS"]["neutral"] == 2
