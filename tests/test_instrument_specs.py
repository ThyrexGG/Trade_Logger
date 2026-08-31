"""
Tests for Broker Instrument Specification Registry (Phase 12B)
"""

import pytest
import instrument_specs

def test_get_forex_spec():
    spec = instrument_specs.get_instrument_spec("MT5", "EURUSD")
    assert spec is not None
    assert spec.canonical_symbol == "EURUSD"
    assert spec.asset_class == "FOREX"
    assert spec.contract_size == 100000.0
    assert spec.digits == 5
    assert spec.min_qty == 0.01

def test_get_metals_spec():
    spec = instrument_specs.get_instrument_spec("CAPITAL", "GOLD")
    assert spec is not None
    assert spec.canonical_symbol == "XAUUSD"
    assert spec.broker_symbol == "GOLD"
    assert spec.asset_class == "METALS"
    assert spec.contract_size == 100.0

def test_validate_order_volume_valid():
    ok, err = instrument_specs.validate_order_volume("MT5", "EURUSD", 0.05)
    assert ok is True
    assert err is None

def test_validate_order_volume_below_min():
    ok, err = instrument_specs.validate_order_volume("MT5", "EURUSD", 0.005)
    assert ok is False
    assert "MIN_VOLUME_VIOLATION" in err

def test_validate_order_volume_above_max():
    ok, err = instrument_specs.validate_order_volume("MT5", "EURUSD", 500.0)
    assert ok is False
    assert "MAX_VOLUME_VIOLATION" in err

def test_validate_order_volume_step_alignment():
    # Indices require step 0.1
    ok, err = instrument_specs.validate_order_volume("MT5", "NAS100", 0.15)
    assert ok is False
    assert "VOLUME_STEP_VIOLATION" in err

def test_fail_closed_unsupported_instrument():
    spec = instrument_specs.get_instrument_spec("MT5", "FAKE_ASSET")
    assert spec is None
    ok, err = instrument_specs.validate_order_volume("MT5", "FAKE_ASSET", 1.0)
    assert ok is False
    assert "UNSUPPORTED_INSTRUMENT" in err
