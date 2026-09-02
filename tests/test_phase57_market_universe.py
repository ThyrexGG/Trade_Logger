"""
Phase 57: Test Suite for Market Universe Registry
Verifies:
- 23 assets across 6 asset classes
- Required metadata fields per asset
- Normalization and fallback handling
- Filtering by asset class
"""

import pytest
from market_intelligence_scanner import MarketUniverseRegistry, MARKET_UNIVERSE_CATALOG


def test_market_universe_count():
    symbols = MarketUniverseRegistry.get_all_symbols()
    assert len(symbols) == 23, f"Expected exactly 23 universe assets, got {len(symbols)}"
    assert len(MARKET_UNIVERSE_CATALOG) == 23


def test_market_universe_classes():
    classes = MarketUniverseRegistry.get_available_asset_classes()
    expected_classes = {"ALL", "FX", "METALS", "INDICES", "ENERGY", "MACRO", "CRYPTO"}
    assert set(classes) == expected_classes


def test_asset_metadata_completeness():
    required_keys = [
        "display_name", "asset_class", "sub_class", "base_currency",
        "quote_currency", "primary_drivers", "pip_decimal", "default_active"
    ]
    for sym, meta in MARKET_UNIVERSE_CATALOG.items():
        for key in required_keys:
            assert key in meta, f"Asset {sym} missing required metadata key: {key}"
        assert isinstance(meta["primary_drivers"], list), f"{sym} primary_drivers must be a list"
        assert len(meta["primary_drivers"]) > 0, f"{sym} primary_drivers cannot be empty"


def test_get_assets_by_class():
    fx_assets = MarketUniverseRegistry.get_assets_by_class("FX")
    assert len(fx_assets) == 8
    for item in fx_assets:
        assert item["asset_class"] == "FX"

    crypto_assets = MarketUniverseRegistry.get_assets_by_class("CRYPTO")
    assert len(crypto_assets) == 1
    assert crypto_assets[0]["symbol"] == "BTCUSD"


def test_unlisted_symbol_fallback():
    info = MarketUniverseRegistry.get_asset_info("NON_EXISTENT_COIN")
    assert info["symbol"] == "NON_EXISTENT_COIN"
    assert info["asset_class"] == "UNKNOWN"
    assert info["default_active"] is False
