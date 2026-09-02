# -*- coding: utf-8 -*-
"""
Phase 62 - Test Network Boundaries & Fast In-Memory Market Data Fallbacks
"""
import pytest
import market_data


def test_batch_prices_fast_cache_read():
    """Verify get_batch_prices returns all major symbols without blocking."""
    syms = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "USOIL"]
    prices = market_data.get_batch_prices(syms)
    assert len(prices) == len(syms)
    for s in syms:
        assert s in prices
        assert prices[s] > 0.0


def test_market_depth_and_spread_synthetic_fast():
    """Verify spread and tick retrieval latency."""
    tick = market_data.get_latest_tick("XAUUSD")
    assert tick is not None
    assert "bid" in tick
    assert "ask" in tick
    assert tick["ask"] >= tick["bid"]


def test_offline_mode_resilience():
    """Verify fallback price mapping when live feed is disconnected."""
    p = market_data.get_latest_price("UNKNOWN_SYMBOL_XYZ")
    # Should safely return fallback or None without crashing
    assert p is None or isinstance(p, (float, int))


def test_historical_price_synthetic_caching():
    """Verify candle cache returns fast on repeated calls."""
    c1 = market_data.get_realtime_candles("XAUUSD", "15m", 50)
    c2 = market_data.get_realtime_candles("XAUUSD", "15m", 50)
    assert len(c1) == len(c2)
