# -*- coding: utf-8 -*-
"""
Phase 68 — as-of candle window truncation (historical_market_data).

The window must contain only candles that have CLOSED at or before as_of, must
drop the still-forming candle, and must never treat the synthetic offline
fallback as real market data.
"""
import math
from datetime import datetime, timezone

import pytest

import historical_market_data as hmd


def _series(as_of_epoch, tf_sec, n):
    out = []
    for i in range(n):
        t = as_of_epoch - (n - i) * tf_sec
        px = 100.0 + i * 0.1 + math.sin(i / 5.0)
        out.append({"time": int(t), "open": px, "high": px + 0.5, "low": px - 0.5,
                    "close": px + 0.05, "volume": 1000 + i})
    return out


@pytest.fixture(autouse=True)
def _clean():
    hmd._reset_live_feed_state()
    hmd.set_test_provider(None)
    yield
    hmd.set_test_provider(None)
    hmd._reset_live_feed_state()


def test_no_provider_returns_none_for_historical():
    w = hmd.get_candle_window("XAUUSD", "1h", datetime(2025, 1, 1, tzinfo=timezone.utc))
    assert w is None  # repo ships no historical OHLCV store — honest gap


def test_truncation_excludes_future_and_forming_candle():
    tf_sec = 3600
    T = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    T_epoch = T.timestamp()

    def prov(asset, tf, as_of_epoch, lookback):
        # candles every hour, INCLUDING several that open/close after T
        base = T_epoch - 100 * tf_sec
        return [
            {"time": int(base + k * tf_sec), "open": 1, "high": 2, "low": 0, "close": 1, "volume": 1}
            for k in range(140)
        ]

    hmd.set_test_provider(prov)
    w = hmd.get_candle_window("XAUUSD", "1h", T, lookback=200)
    assert w is not None
    for c in w.candles:
        assert c["time"] + tf_sec <= T_epoch + 1e-6      # every candle has closed by T
    # the candle closing exactly at T is allowed; the one closing at T+1h is not
    last_close = w.candles[-1]["time"] + tf_sec
    assert last_close <= T_epoch
    assert last_close == pytest.approx(T_epoch)          # boundary inclusive


def test_latest_input_timestamp_never_after_as_of():
    T = datetime(2026, 3, 10, 9, 30, tzinfo=timezone.utc)
    hmd.set_test_provider(lambda a, tf, e, lb: _series(e, hmd.tf_seconds(tf), lb + 40))
    w = hmd.get_candle_window("EURUSD", "15m", T, lookback=120)
    assert w is not None
    lit = datetime.fromisoformat(w.latest_input_timestamp)
    assert lit <= T


def test_insufficient_candles_returns_none():
    hmd.set_test_provider(lambda a, tf, e, lb: _series(e, hmd.tf_seconds(tf), 1))
    assert hmd.get_candle_window("XAUUSD", "1h", datetime(2026, 1, 1, tzinfo=timezone.utc)) is None


def test_synthetic_fallback_is_not_real_data(monkeypatch):
    import market_data
    monkeypatch.setattr(market_data, "get_candles_with_source",
                        lambda *a, **k: ([{"time": 1, "open": 1, "high": 1, "low": 1, "close": 1,
                                           "volume": 100.0}] * 300, "synthetic_fallback"))
    hmd._reset_live_feed_state()
    assert hmd.get_candle_window("XAUUSD", "1h", None) is None
    # and the feed is now marked down so we don't keep hammering the network
    assert hmd._live_feed_is_down()


def test_live_feed_marked_down_short_circuits(monkeypatch):
    import market_data
    calls = {"n": 0}

    def _src(*a, **k):
        calls["n"] += 1
        return ([], "synthetic_fallback")

    monkeypatch.setattr(market_data, "get_candles_with_source", _src)
    hmd._reset_live_feed_state()
    hmd.get_candle_window("XAUUSD", "1h", None)
    hmd.get_candle_window("EURUSD", "1h", None)
    hmd.get_candle_window("BTCUSD", "1h", None)
    assert calls["n"] == 1  # only the first attempt hit the (mocked) feed


def test_window_provenance_and_meta():
    T = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    hmd.set_test_provider(lambda a, tf, e, lb: _series(e, hmd.tf_seconds(tf), lb + 40))
    w = hmd.get_candle_window("XAUUSD", "1h", T, lookback=100)
    assert w.provenance == "historical_ohlcv"
    assert w.source_id == "provider:test"
    assert "1h candles" in w.calculation_window
    assert w.n <= 100
