"""
Tests for Canonical Symbol Mapping Layer (Phase 12B)
"""

import pytest
import symbol_mapping

def test_normalize_standard_symbols():
    assert symbol_mapping.normalize_symbol("EURUSD") == "EURUSD"
    assert symbol_mapping.normalize_symbol("eurusd") == "EURUSD"
    assert symbol_mapping.normalize_symbol("GBP/USD") == "GBPUSD"
    assert symbol_mapping.normalize_symbol("USD-JPY") == "USDJPY"
    assert symbol_mapping.normalize_symbol("XAUUSD") == "XAUUSD"

def test_normalize_aliases():
    assert symbol_mapping.normalize_symbol("GOLD") == "XAUUSD"
    assert symbol_mapping.normalize_symbol("SILVER") == "XAGUSD"
    assert symbol_mapping.normalize_symbol("BITCOIN") == "BTCUSD"
    assert symbol_mapping.normalize_symbol("BTC") == "BTCUSD"
    assert symbol_mapping.normalize_symbol("US100") == "NAS100"
    assert symbol_mapping.normalize_symbol("NDX") == "NAS100"
    assert symbol_mapping.normalize_symbol("DE40") == "GER40"
    assert symbol_mapping.normalize_symbol("DAX") == "GER40"

def test_normalize_suffixes():
    assert symbol_mapping.normalize_symbol("EURUSD.raw") == "EURUSD"
    assert symbol_mapping.normalize_symbol("GBPUSD.m") == "GBPUSD"
    assert symbol_mapping.normalize_symbol("USDJPY+") == "USDJPY"

def test_broker_symbol_translation():
    assert symbol_mapping.get_broker_symbol("EURUSD", "MT5") == "EURUSD"
    assert symbol_mapping.get_broker_symbol("XAUUSD", "CAPITAL") == "GOLD"
    assert symbol_mapping.get_broker_symbol("NAS100", "CAPITAL") == "US100"
    assert symbol_mapping.get_broker_symbol("GER40", "CAPITAL") == "DE40"

def test_fail_closed_unknown_symbol():
    assert symbol_mapping.normalize_symbol("UNKNOWN_COIN_XYZ") is None
    assert symbol_mapping.normalize_symbol("") is None
    assert symbol_mapping.normalize_symbol(None) is None
    assert symbol_mapping.is_symbol_supported("UNKNOWN_COIN_XYZ") is False
