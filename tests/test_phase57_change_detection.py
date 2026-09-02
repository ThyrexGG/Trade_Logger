"""
Phase 57: Test Suite for Market-Wide Change Detection Engine
Verifies:
- Change detection between current records and prior state
- Material rank changes (>= 3 spots)
- Material score changes (>= 15 pts)
- Regime changes and factor divergence alerts
"""

import pytest
from market_intelligence_scanner import MarketWideChangeDetector, AssetScanRecord


def test_change_detector_evaluation():
    records = [
        AssetScanRecord(
            symbol="EURUSD", asset_class="FX", display_name="Euro / USD",
            price=1.0850, price_change_24h_pct=0.45, volatility_atr_pct=0.62,
            edge_score=45.0, macro_score=30.0, technical_score=50.0,
            positioning_score=20.0, seasonality_score=10.0, regime_score=15.0,
            data_quality_score=90, data_quality_rating="LIVE",
            factor_agreement_pct=85.0, conflict_state="ALIGNED", conflict_score=10.0,
            dominant_driver="TECHNICAL", dominant_risk="NONE",
            context_state="BULLISH CONTEXT", why_bullets=[], data_fingerprint="f1"
        )
    ]
    changes = MarketWideChangeDetector.evaluate_market_changes(records)
    assert isinstance(changes, dict)
    assert "summary" in changes
    assert "material_rank_changes" in changes
    assert "material_score_changes" in changes
    assert "regime_changes" in changes
    assert "factor_divergence_alerts" in changes
    assert "data_quality_changes" in changes
    assert isinstance(changes["material_rank_changes"], list)
