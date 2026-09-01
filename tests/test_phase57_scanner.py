"""
TradeLogger Phase 57 — Test Suite: Market Intelligence Scanner Engine
======================================================================
Validates:
- Execution of single and multi-asset market scans.
- AssetScanRecord data structures, types, and mathematical boundaries.
- Contextual label adherence (no trade execution/signal generation words).
- Factor alignment integration within scan records.
"""

import pytest
from market_intelligence_scanner import (
    MarketScannerEngine,
    AssetScanRecord,
    SCANNER_MODEL_VERSION
)


def test_scanner_version():
    """Verify scanner engine version is defined."""
    assert SCANNER_MODEL_VERSION == "1.0.0"


def test_scan_single_asset():
    """Verify single asset scan returns valid AssetScanRecord."""
    rec = MarketScannerEngine.scan_symbol("XAUUSD")
    assert isinstance(rec, AssetScanRecord)
    assert rec.symbol == "XAUUSD"
    assert rec.asset_class == "METALS"
    assert -100.0 <= rec.edge_score <= 100.0
    assert -100.0 <= rec.macro_score <= 100.0
    assert 0.0 <= rec.factor_agreement_pct <= 100.0
    assert 0 <= rec.data_quality_score <= 100
    assert rec.context_state in {"BULLISH CONTEXT", "BEARISH CONTEXT", "NEUTRAL", "MIXED", "DIVERGING", "INSUFFICIENT DATA"}
    assert rec.context_state not in {"BUY", "SELL", "LONG", "SHORT", "TRADE NOW"}


def test_scan_all_assets_count():
    """Verify full universe scan processes all 23 instruments."""
    records = MarketScannerEngine.scan_universe("ALL")
    assert len(records) == 23
    symbols = {r.symbol for r in records}
    assert "XAUUSD" in symbols
    assert "SPX500" in symbols
    assert "EURUSD" in symbols
    assert "BTCUSD" in symbols
    assert "USOIL" in symbols
    assert "DXY" in symbols


def test_scan_asset_class_filter():
    """Verify scanning by specific asset class."""
    fx_records = MarketScannerEngine.scan_universe("FX")
    assert len(fx_records) == 8
    for r in fx_records:
        assert r.asset_class == "FX"

    metal_records = MarketScannerEngine.scan_universe("METALS")
    assert len(metal_records) == 3
    for r in metal_records:
        assert r.asset_class == "METALS"


def test_scan_record_to_dict():
    """Verify AssetScanRecord serialization to dictionary format."""
    rec = MarketScannerEngine.scan_symbol("EURUSD")
    d = rec.to_dict()
    assert isinstance(d, dict)
    assert d["symbol"] == "EURUSD"
    assert "edge_score" in d
    assert "macro_score" in d
    assert "factor_agreement_pct" in d
    assert "dominant_driver" in d
    assert "conflict_state" in d
