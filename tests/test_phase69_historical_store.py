# -*- coding: utf-8 -*-
"""
Phase 69 — persistent historical OHLCV store.

Covers §54: duplicate candles, invalid OHLC, timezone normalization, gaps,
ordering, data sufficiency, provider provenance, as-of filtering, partial-candle
exclusion, historical/live separation.
"""
from datetime import datetime, timezone

import pytest

import database
import historical_data_store as store

TF = "1h"
TF_SEC = 3600
BASE = 1704067200  # 2024-01-01T00:00:00Z
ASSETS = ("ZZTESTA", "ZZTESTB", "XAUUSD")


def _clean():
    database.init_db()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        for a in ASSETS:
            cur.execute(f"DELETE FROM historical_candles WHERE asset={ph}", (a,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _isolate():
    _clean()
    yield
    _clean()


def _series(n, start=BASE, tf_sec=TF_SEC, price=100.0):
    out = []
    for i in range(n):
        p = price + i * 0.1
        out.append({"time": start + i * tf_sec, "open": p, "high": p + 0.5,
                    "low": p - 0.5, "close": p + 0.2, "volume": 10 + i})
    return out


def test_upsert_and_read_roundtrip():
    rep = store.upsert_candles("ZZTESTA", TF, _series(100), source="unit")
    assert rep.inserted == 100 and rep.updated == 0 and rep.rejected == 0
    rows = store.get_candles("ZZTESTA", TF)
    assert len(rows) == 100
    assert rows[0]["source"] == "unit"


def test_duplicate_candles_are_idempotent():
    s = _series(50)
    store.upsert_candles("ZZTESTA", TF, s, source="unit")
    rep2 = store.upsert_candles("ZZTESTA", TF, s, source="unit")
    assert rep2.inserted == 0
    assert rep2.updated == 50
    assert len(store.get_candles("ZZTESTA", TF)) == 50


def test_duplicate_within_batch_rejected_once():
    s = _series(10)
    s.append(dict(s[3]))  # exact dup of an earlier open_time
    rep = store.upsert_candles("ZZTESTA", TF, s, source="unit")
    assert rep.reject_reasons.get("DUPLICATE_IN_BATCH") == 1
    assert len(store.get_candles("ZZTESTA", TF)) == 10


def test_invalid_ohlc_rejected_not_repaired():
    s = _series(5)
    s.append({"time": BASE + 5 * TF_SEC, "open": 100, "high": 90, "low": 95, "close": 100, "volume": 1})
    s.append({"time": BASE + 6 * TF_SEC, "open": 100, "high": 105, "low": 101, "close": 100, "volume": 1})  # low>min(o,c)
    s.append({"time": BASE + 7 * TF_SEC, "open": 100, "high": 99, "low": 98, "close": 100, "volume": 1})   # high<max(o,c)
    rep = store.upsert_candles("ZZTESTA", TF, s, source="unit")
    assert rep.rejected == 3
    assert set(rep.reject_reasons) == {"HIGH_LT_LOW", "LOW_GT_MIN_OPEN_CLOSE", "HIGH_LT_MAX_OPEN_CLOSE"}
    assert len(store.get_candles("ZZTESTA", TF)) == 5  # nothing repaired / coerced


def test_ordering_is_ascending_even_if_input_shuffled():
    s = _series(20)
    shuffled = s[::-1]
    store.upsert_candles("ZZTESTA", TF, shuffled, source="unit")
    rows = store.get_candles("ZZTESTA", TF)
    times = [r["time"] for r in rows]
    assert times == sorted(times)


def test_timezone_normalization_via_ingest_frame():
    import pandas as pd
    import market_data_ingest as ing
    idx = pd.to_datetime(["2024-01-01 00:00", "2024-01-01 01:00"]).tz_localize("America/New_York")
    df = pd.DataFrame({"Open": [1, 1], "High": [2, 2], "Low": [0.5, 0.5], "Close": [1.5, 1.5],
                       "Volume": [10, 10]}, index=idx)
    candles = ing._frame_to_candles(df)
    # 00:00 New York on 2024-01-01 is 05:00 UTC
    assert candles[0]["time"] == int(datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc).timestamp())


def test_gap_detection():
    s = _series(10) + _series(5, start=BASE + 20 * TF_SEC)  # 10-bar hole
    store.upsert_candles("ZZTESTA", TF, s, source="unit")
    gaps = store.detect_gaps("ZZTESTA", TF, min_gap_bars=2)
    assert len(gaps) == 1
    assert gaps[0]["missing_bars"] == 10  # last bar @ +9h, next @ +20h -> 10 missing
    cov = store.get_coverage("ZZTESTA", TF)
    assert cov.largest_gap_bars == 10
    assert cov.missing_bars == 10


def test_data_sufficiency_states():
    store.upsert_candles("ZZTESTA", "1d", _series(100, tf_sec=86400), source="unit")
    suf = store.data_sufficiency("ZZTESTA", "1d")
    assert suf["state"] == "INSUFFICIENT_EVIDENCE"
    assert any("BELOW_MIN_BARS" in r for r in suf["reasons"])
    assert suf["next_dependency"]  # names the ingestion command

    store.upsert_candles("ZZTESTB", "1d", _series(500, tf_sec=86400), source="unit")
    suf2 = store.data_sufficiency("ZZTESTB", "1d")
    assert suf2["state"] == "AVAILABLE"
    assert suf2["reasons"] == []


def test_data_sufficiency_never_reports_zero_trades():
    suf = store.data_sufficiency("ZZTESTA", "1d")  # empty
    assert suf["state"] == "INSUFFICIENT_EVIDENCE"
    assert "NO_DATA_IN_STORE" in suf["reasons"]
    assert "trades" not in str(suf).lower() or "0 trades" not in str(suf).lower()


def test_as_of_filtering_excludes_future_and_forming_candle():
    store.upsert_candles("ZZTESTA", TF, _series(100), source="unit")
    as_of = BASE + 50 * TF_SEC  # exactly the OPEN of bar 50 -> bar 49 closes at as_of
    rows = store.get_candles("ZZTESTA", TF, as_of=as_of)
    assert all(r["time"] + TF_SEC <= as_of for r in rows)
    assert len(rows) == 50  # bars 0..49; bar 50 is still forming


def test_store_provider_provenance_and_separation():
    store.upsert_candles("XAUUSD", TF, _series(300), source="unit")
    store.register_with_phase68()
    import historical_market_data as hmd
    hmd.set_test_provider(None)
    hmd._reset_live_feed_state()
    as_of = datetime.fromtimestamp(BASE + 250 * TF_SEC, tz=timezone.utc)
    win = hmd.get_candle_window("XAUUSD", TF, as_of)
    assert win is not None
    assert win.provenance == "historical_ohlcv"
    assert win.source_id == "provider:store"
    # every candle strictly historical relative to as_of
    assert all(c["time"] + TF_SEC <= as_of.timestamp() + 1e-6 for c in win.candles)


def test_empty_store_is_still_an_honest_gap():
    store.register_with_phase68()
    import historical_market_data as hmd
    hmd.set_test_provider(None)
    hmd._reset_live_feed_state()
    win = hmd.get_candle_window("ZZTESTB", TF, datetime(2024, 6, 1, tzinfo=timezone.utc))
    assert win is None  # no data -> None, never fabricated


def test_suspect_quality_flag_not_rejection():
    # sub-minute-aligned open_time is flagged suspect, still stored
    s = [{"time": BASE + 30, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 1}]
    rep = store.upsert_candles("ZZTESTA", TF, s, source="unit")
    assert rep.suspect == 1
    assert rep.inserted == 1
    rows = store.get_candles("ZZTESTA", TF)
    assert rows[0]["data_quality"] == "suspect"


def test_artifact_persistence_roundtrip_and_content_hash():
    h1 = store.save_artifact("zz_test_artifact", "unit", {"b": 2, "a": 1})
    h2 = store.save_artifact("zz_test_artifact", "unit", {"a": 1, "b": 2})
    assert h1 == h2  # key-order independent
    loaded = store.load_artifact("zz_test_artifact")
    assert loaded["payload"] == {"a": 1, "b": 2}
    assert loaded["content_hash"] == h1
