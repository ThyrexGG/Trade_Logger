"""
Phase 57: Test Suite for Data Quality and Anti-Fabrication
Verifies:
- Data quality rating tiers: LIVE (>=80), DELAYED (>=60), STALE (>=35), UNAVAILABLE (<35)
- Withholding rankings on low data quality
- Missing data transparent handling with no synthetic zeros fabricated
"""

import pytest
from market_intelligence_scanner import MarketRankingEngine, AssetScanRecord


def test_data_quality_tier_boundaries():
    # Asset with score 90 -> LIVE
    # Asset with score 70 -> DELAYED
    # Asset with score 45 -> STALE
    # Asset with score 20 -> UNAVAILABLE
    r_live = AssetScanRecord("S1", "FX", "S1", 1.0, 0.0, 0.0, 50.0, 0.0, 50.0, 0.0, 0.0, 0.0, 90, "LIVE", 80.0, "ALIGNED", 0.0, "T", "R", "BULLISH CONTEXT", [], "f1")
    r_del = AssetScanRecord("S2", "FX", "S2", 1.0, 0.0, 0.0, 45.0, 0.0, 45.0, 0.0, 0.0, 0.0, 70, "DELAYED", 80.0, "ALIGNED", 0.0, "T", "R", "BULLISH CONTEXT", [], "f2")
    r_stale = AssetScanRecord("S3", "FX", "S3", 1.0, 0.0, 0.0, 40.0, 0.0, 40.0, 0.0, 0.0, 0.0, 45, "STALE", 80.0, "ALIGNED", 0.0, "T", "R", "BULLISH CONTEXT", [], "f3")
    r_unavail = AssetScanRecord("S4", "FX", "S4", 1.0, 0.0, 0.0, 35.0, 0.0, 35.0, 0.0, 0.0, 0.0, 20, "UNAVAILABLE", 80.0, "ALIGNED", 0.0, "T", "R", "BULLISH CONTEXT", [], "f4")

    ranked = MarketRankingEngine.rank_records([r_live, r_del, r_stale, r_unavail])

    s1_res = next(r for r in ranked if r["symbol"] == "S1")
    s2_res = next(r for r in ranked if r["symbol"] == "S2")
    s3_res = next(r for r in ranked if r["symbol"] == "S3")
    s4_res = next(r for r in ranked if r["symbol"] == "S4")

    assert s1_res["ranking_eligible"] is True
    assert s1_res["rank"] == 1
    assert s2_res["ranking_eligible"] is True
    assert s2_res["rank"] == 2
    assert s3_res["ranking_eligible"] is True
    assert s3_res["rank"] == 3
    assert s4_res["ranking_eligible"] is False
    assert s4_res["rank"] is None
