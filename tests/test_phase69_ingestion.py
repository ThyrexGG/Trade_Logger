# -*- coding: utf-8 -*-
"""Phase 69 — ingestion layer (offline: yfinance is monkeypatched / absent)."""
from datetime import datetime, timezone

import pandas as pd
import pytest

import database
import historical_data_store as store
import market_data_ingest as ing
import research_universe


def _clean(asset):
    database.init_db()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(f"DELETE FROM historical_candles WHERE asset={ph}", (asset,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _isolate():
    for a in ("XAUUSD", "EURUSD"):
        _clean(a)
    yield
    for a in ("XAUUSD", "EURUSD"):
        _clean(a)


def _fake_frame(n, start="2024-01-01", freq="1h"):
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    base = 2000.0
    return pd.DataFrame({
        "Open": [base + i for i in range(n)],
        "High": [base + i + 2 for i in range(n)],
        "Low": [base + i - 2 for i in range(n)],
        "Close": [base + i + 1 for i in range(n)],
        "Volume": [100] * n,
    }, index=idx)


def test_frame_to_candles_drops_nan_and_normalizes():
    df = _fake_frame(5)
    df.iloc[2, df.columns.get_loc("Close")] = float("nan")
    candles = ing._frame_to_candles(df)
    assert len(candles) == 4
    assert all(c["time"] % 3600 == 0 for c in candles)


def test_resample_1h_to_4h_drops_partial_bucket():
    src = ing._frame_to_candles(_fake_frame(10))  # 10 hourly bars -> 2 full 4h + partial
    out = ing._resample(src, factor=4, src_tf_sec=3600)
    assert len(out) == 2
    assert out[0]["open"] == src[0]["open"]
    assert out[0]["close"] == src[3]["close"]
    assert out[0]["high"] == max(c["high"] for c in src[:4])


def test_ingest_rejects_symbol_outside_universe():
    res = ing.ingest("DOGEUSD", "1d")
    assert not res.ok
    assert "universe" in res.error


# Phase 74: HISTORICAL_OHLCV_PROVIDER may select a real vendor (mt5); these tests
# exercise the yfinance ingest path, so pin provider="yfinance" explicitly.
def test_ingest_stores_via_monkeypatched_source(monkeypatch):
    monkeypatch.setattr(ing, "yf", object())  # presence check only
    monkeypatch.setattr(ing, "_yf_download", lambda *a, **k: _fake_frame(300))
    res = ing.ingest("XAUUSD", "1h", provider="yfinance")
    assert res.ok
    assert res.stored_report["inserted"] == 300
    assert store.get_coverage("XAUUSD", "1h").count == 300
    assert res.coverage["count"] == 300


def test_ingest_incremental_only_adds_new(monkeypatch):
    monkeypatch.setattr(ing, "yf", object())
    monkeypatch.setattr(ing, "_yf_download", lambda *a, **k: _fake_frame(100))
    ing.ingest("XAUUSD", "1h", provider="yfinance")
    # a longer frame starting at the same point
    monkeypatch.setattr(ing, "_yf_download", lambda *a, **k: _fake_frame(150))
    res = ing.ingest("XAUUSD", "1h", incremental=True, provider="yfinance")
    assert res.mode == "incremental"
    assert store.get_coverage("XAUUSD", "1h").count == 150


def test_ingest_4h_resampled_from_1h(monkeypatch):
    monkeypatch.setattr(ing, "yf", object())
    monkeypatch.setattr(ing, "_yf_download", lambda *a, **k: _fake_frame(400))
    res = ing.ingest("XAUUSD", "4h", provider="yfinance")
    assert res.ok
    assert res.stored_report["source"] == "yahoo"
    cov = store.get_coverage("XAUUSD", "4h")
    assert cov.count == 100  # 400 hourly -> 100 x 4h
    assert store.tf_seconds("4h") == 14400


def test_ingest_reports_missing_yfinance(monkeypatch):
    monkeypatch.setattr(ing, "yf", None)
    res = ing.ingest("EURUSD", "1d", provider="yfinance")
    assert not res.ok
    assert "yfinance" in res.error


def test_timeframe_data_capability_flags():
    assert research_universe.timeframe_is_data_capable("1d")
    assert research_universe.timeframe_is_data_capable("1h")
    assert not research_universe.timeframe_is_data_capable("15m")
    assert not research_universe.timeframe_is_data_capable("1m")
