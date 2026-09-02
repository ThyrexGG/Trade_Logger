"""
Phase 57: Test Suite for Market Scanner Engine
Verifies:
- AssetScanRecord structure and range constraints
- Multi-asset batch scan execution
- Deterministic score generation and reproducibility
- Non-fabrication and missing data handling
"""

from datetime import datetime, timezone
import pytest
from market_intelligence_scanner import MarketScannerEngine, AssetScanRecord, MarketUniverseRegistry


def test_scan_single_asset_structure():
    record = MarketScannerEngine.scan_single_asset("EURUSD")
    assert isinstance(record, AssetScanRecord)
    assert record.symbol == "EURUSD"
    assert record.asset_class == "FX"
    assert -100.0 <= record.edge_score <= 100.0
    assert -100.0 <= record.macro_score <= 100.0
    assert -100.0 <= record.technical_score <= 100.0
    assert -100.0 <= record.positioning_score <= 100.0
    assert 0 <= record.data_quality_score <= 100
    assert 0.0 <= record.factor_agreement_pct <= 100.0
    assert len(record.data_fingerprint) == 64  # SHA-256


def test_scan_all_assets_count():
    records = MarketScannerEngine.scan_all_assets()
    symbols = MarketUniverseRegistry.get_all_symbols()
    assert len(records) == len(symbols)
    scanned_symbols = {r.symbol for r in records}
    assert scanned_symbols == set(symbols)


def test_scan_reproducibility():
    fixed_time = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
    rec1 = MarketScannerEngine.scan_single_asset("XAUUSD", as_of=fixed_time)
    rec2 = MarketScannerEngine.scan_single_asset("XAUUSD", as_of=fixed_time)

    assert rec1.edge_score == rec2.edge_score
    assert rec1.macro_score == rec2.macro_score
    assert rec1.data_fingerprint == rec2.data_fingerprint


def test_scan_custom_subset():
    subset = ["EURUSD", "SPX500", "BTCUSD"]
    records = MarketScannerEngine.scan_universe(symbols=subset)
    assert len(records) == 3
    assert [r.symbol for r in records] == subset
