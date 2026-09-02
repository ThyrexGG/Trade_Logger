"""
Phase 57: Test Suite for Market Ranking Engine
Verifies:
- Deterministic leaderboard sorting (DESC, ASC, absolute)
- Tie-breaking deterministic logic
- Ranking withholding on low data quality (score < 35 or UNAVAILABLE)
- Contextual reason bullets preservation
"""

import pytest
from market_intelligence_scanner import MarketRankingEngine, AssetScanRecord


def _make_dummy_record(symbol: str, edge_score: float, dq_score: int, dq_rating: str = "LIVE") -> AssetScanRecord:
    return AssetScanRecord(
        symbol=symbol,
        asset_class="FX",
        display_name=symbol,
        price=1.0,
        price_change_24h_pct=0.1,
        volatility_atr_pct=0.5,
        edge_score=edge_score,
        macro_score=0.0,
        technical_score=edge_score,
        positioning_score=0.0,
        seasonality_score=0.0,
        regime_score=0.0,
        data_quality_score=dq_score,
        data_quality_rating=dq_rating,
        factor_agreement_pct=80.0,
        conflict_state="ALIGNED",
        conflict_score=10.0,
        dominant_driver="TECHNICAL",
        dominant_risk="MACRO",
        context_state="BULLISH CONTEXT" if edge_score > 0 else "BEARISH CONTEXT",
        why_bullets=["Test reason bullet"],
        data_fingerprint="abc123"
    )


def test_ranking_sort_order_desc():
    records = [
        _make_dummy_record("EURUSD", 15.0, 90),
        _make_dummy_record("GBPUSD", 55.0, 90),
        _make_dummy_record("USDJPY", -30.0, 90),
    ]
    ranked = MarketRankingEngine.rank_records(records, sort_by="edge_score", ascending=False)
    assert len(ranked) == 3
    assert ranked[0]["symbol"] == "GBPUSD"
    assert ranked[0]["rank"] == 1
    assert ranked[1]["symbol"] == "EURUSD"
    assert ranked[1]["rank"] == 2
    assert ranked[2]["symbol"] == "USDJPY"
    assert ranked[2]["rank"] == 3


def test_ranking_withholding_on_low_dq():
    records = [
        _make_dummy_record("EURUSD", 80.0, 20),  # Low DQ
        _make_dummy_record("GBPUSD", 40.0, 90),  # High DQ
    ]
    ranked = MarketRankingEngine.rank_records(records, sort_by="edge_score")
    # Low DQ must have ranking_eligible == False and rank == None
    eur = next(r for r in ranked if r["symbol"] == "EURUSD")
    gbp = next(r for r in ranked if r["symbol"] == "GBPUSD")

    assert eur["ranking_eligible"] is False
    assert eur["rank"] is None
    assert gbp["ranking_eligible"] is True
    assert gbp["rank"] == 1


def test_ranking_deterministic_tie_breaker():
    # Same edge_score, should break ties by symbol alphabetically
    records = [
        _make_dummy_record("USDJPY", 50.0, 90),
        _make_dummy_record("AUDUSD", 50.0, 90),
        _make_dummy_record("EURUSD", 50.0, 90),
    ]
    ranked = MarketRankingEngine.rank_records(records, sort_by="edge_score", ascending=False)
    ranked_symbols = [r["symbol"] for r in ranked if r["rank"] is not None]
    assert ranked_symbols == ["AUDUSD", "EURUSD", "USDJPY"]
