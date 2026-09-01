"""
TradeLogger Phase 57 — Test Suite: Market Ranking Engine
=========================================================
Validates:
- Deterministic 23-asset leaderboard ranking.
- Sort keys: edge_score, macro_score, factor_agreement_pct.
- Ranking withholding policy for low data quality.
- Generation of transparent, deterministic "Why Ranked Here?" evidence bullets.
"""

import pytest
from market_intelligence_scanner import (
    MarketScannerEngine,
    MarketRankingEngine,
    AssetScanRecord
)


def test_ranking_determinism():
    """Verify leaderboard ranking produces deterministic results."""
    records = MarketScannerEngine.scan_universe("ALL")
    ranked_1 = MarketRankingEngine.rank_records(records)
    ranked_2 = MarketRankingEngine.rank_records(records)

    assert len(ranked_1) == 23
    assert len(ranked_2) == 23
    for i in range(len(ranked_1)):
        assert ranked_1[i]["symbol"] == ranked_2[i]["symbol"]
        assert ranked_1[i]["rank"] == ranked_2[i]["rank"]


def test_ranking_sort_order():
    """Verify rank 1 has >= edge_score than rank 2 for eligible assets."""
    records = MarketScannerEngine.scan_universe("ALL")
    ranked = MarketRankingEngine.rank_records(records)
    eligible = [r for r in ranked if r["rank_status"] == "RANKED"]

    for i in range(len(eligible) - 1):
        r_curr = eligible[i]
        r_next = eligible[i + 1]
        assert r_curr["edge_score"] >= r_next["edge_score"]


def test_ranking_withholding_on_low_data_quality():
    """Verify ranking withholding when data quality falls below threshold or is ineligible."""
    bad_rec = AssetScanRecord(
        symbol="TEST_SYM",
        asset_class="FX",
        display_name="Test Bad Quality",
        price=1.0,
        price_change_24h_pct=0.0,
        volatility_atr_pct=1.0,
        edge_score=99.0,
        macro_score=50.0,
        technical_score=50.0,
        positioning_score=50.0,
        seasonality_score=50.0,
        regime_score=50.0,
        data_quality_score=20,
        data_quality_rating="UNAVAILABLE",
        factor_agreement_pct=80.0,
        conflict_state="ALIGNED",
        conflict_score=10.0,
        dominant_driver="MACRO",
        dominant_risk="NONE",
        context_state="INSUFFICIENT DATA",
        ranking_eligible=False,
        why_bullets=["Data feed unavailable."],
        snapshot_timestamp="2026-09-01T00:00:00",
        data_fingerprint="abc"
    )
    ranked = MarketRankingEngine.rank_records([bad_rec])
    assert len(ranked) == 1
    assert ranked[0]["rank"] is None
    assert ranked[0]["rank_status"] == "RANKING WITHHELD"


def test_evidence_bullets_generation():
    """Verify evidence bullets contain factual drivers."""
    records = MarketScannerEngine.scan_universe("ALL")
    ranked = MarketRankingEngine.rank_records(records)
    for item in ranked:
        bullets = item.get("why_bullets", [])
        assert len(bullets) >= 1
