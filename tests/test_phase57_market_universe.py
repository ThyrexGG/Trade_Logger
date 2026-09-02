"""
TradeLogger Phase 57 — Test Suite: Market Universe Registry
============================================================
Validates:
- 23-asset normalized universe integrity.
- Asset class partitioning (FX, METALS, INDICES, ENERGY, MACRO, CRYPTO).
- Base/Quote currency mapping and benchmark rate association.
- Non-empty metadata and pip size validation.
"""

import pytest
from market_intelligence_scanner import MarketUniverseRegistry, MARKET_UNIVERSE_CATALOG


def test_market_universe_total_count():
    """Verify universe contains exactly 23 normalized instruments."""
    universe = MarketUniverseRegistry.get_all_assets()
    assert len(universe) == 23
    assert len(MARKET_UNIVERSE_CATALOG) == 23


def test_market_universe_asset_classes():
    """Verify all 6 required asset classes are present with correct instruments."""
    classes = MarketUniverseRegistry.get_available_asset_classes()
    assert "ALL" in classes
    assert set(classes[1:]) == {"CRYPTO", "ENERGY", "FX", "INDICES", "MACRO", "METALS"}

    fx_assets = MarketUniverseRegistry.get_assets_by_class("FX")
    assert len(fx_assets) == 8
    fx_syms = {a["symbol"] for a in fx_assets}
    assert fx_syms == {"EURUSD", "GBPUSD", "USDJPY", "GBPJPY", "NZDUSD", "AUDUSD", "USDCHF", "USDCAD"}

    metals = MarketUniverseRegistry.get_assets_by_class("METALS")
    assert len(metals) == 3
    assert {a["symbol"] for a in metals} == {"XAUUSD", "XAGUSD", "PLATINUM"}

    indices = MarketUniverseRegistry.get_assets_by_class("INDICES")
    assert len(indices) == 6
    assert {a["symbol"] for a in indices} == {"SPX500", "NAS100", "US30", "RUSSELL", "UK100", "NIKKEI"}

    energy = MarketUniverseRegistry.get_assets_by_class("ENERGY")
    assert len(energy) == 2
    assert {a["symbol"] for a in energy} == {"USOIL", "NATGAS"}

    macro = MarketUniverseRegistry.get_assets_by_class("MACRO")
    assert len(macro) == 3
    assert {a["symbol"] for a in macro} == {"DXY", "US10Y", "US2Y"}

    crypto = MarketUniverseRegistry.get_assets_by_class("CRYPTO")
    assert len(crypto) == 1
    assert crypto[0]["symbol"] == "BTCUSD"


def test_asset_metadata_completeness():
    """Verify every asset has complete metadata fields with valid data types."""
    for symbol, meta in MARKET_UNIVERSE_CATALOG.items():
        assert len(meta["display_name"]) > 0
        assert meta["asset_class"] in {"FX", "METALS", "INDICES", "ENERGY", "MACRO", "CRYPTO"}
        assert len(meta["base_currency"]) > 0
        assert len(meta["quote_currency"]) > 0
        assert meta["pip_decimal"] >= 1
        assert isinstance(meta["primary_drivers"], list)
        assert len(meta["primary_drivers"]) > 0


def test_get_asset_lookup():
    """Verify lookup functionality for existing and non-existing assets."""
    xau = MarketUniverseRegistry.get_asset_info("XAUUSD")
    assert xau is not None
    assert "Gold" in xau["display_name"]
    assert xau["asset_class"] == "METALS"

    invalid = MarketUniverseRegistry.get_asset_info("NONEXISTENT")
    assert invalid["asset_class"] == "UNKNOWN"
