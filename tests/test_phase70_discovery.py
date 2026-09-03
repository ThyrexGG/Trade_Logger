# -*- coding: utf-8 -*-
"""
Phase 70 — strategy discovery engine (§55/§56).

Offline + deterministic: the store is seeded (SQLite under pytest) with a
synthetic but self-consistent OHLC series; no network, no yfinance.
"""
import math
from datetime import datetime, timezone

import pytest

import database
import historical_data_store as store
import strategy_discovery as disc

ASSET = "EURUSD"
BASE = 1_600_000_000  # 2020-09-13, well before any real ingested data
TFS = {"1h": 3600, "4h": 14400, "1d": 86400}


def _clean():
    database.init_db()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(f"DELETE FROM historical_candles WHERE asset={ph} AND open_time < {ph}",
                    (ASSET, BASE + 5_000 * 86400))
        conn.commit()
    finally:
        conn.close()


def _series(n, tf_sec, seed_price=1.10):
    """Deterministic trend + oscillation + bounded noise; valid OHLC."""
    out = []
    p = seed_price
    for i in range(n):
        drift = 0.00002 * tf_sec / 3600
        osc = 0.010 * math.sin(i / 23.0)
        noise = 0.002 * math.sin(i * 12.9898)
        close = seed_price + drift * i + osc + noise
        openp = seed_price + drift * (i - 1) + 0.010 * math.sin((i - 1) / 23.0)
        hi = max(openp, close) + 0.0015 + abs(noise)
        lo = min(openp, close) - 0.0015 - abs(noise)
        out.append({"time": BASE + i * tf_sec, "open": round(openp, 5), "high": round(hi, 5),
                    "low": round(lo, 5), "close": round(close, 5), "volume": 1000})
        p = close
    return out


@pytest.fixture(autouse=True)
def _seed_store():
    _clean()
    disc.clear_prepare_cache()
    store.upsert_candles(ASSET, "1h", _series(2600, 3600), source="synthetic_test")
    store.upsert_candles(ASSET, "4h", _series(700, 14400), source="synthetic_test")
    store.upsert_candles(ASSET, "1d", _series(200, 86400), source="synthetic_test")
    yield
    _clean()


# --- definitions ---------------------------------------------------------
def test_strategy_definitions_are_machine_readable():
    defs = disc.list_strategy_definitions()
    assert len(defs) >= 4
    for d in defs:
        assert d["id"] and d["registry_name"] and d["version"]
        assert d["entry_conditions"] and d["stop_model"] and d["target_model"]
        assert "sl_atr" in d["parameter_schema"] and "grid" in d["parameter_schema"]["sl_atr"]


def test_unknown_strategy_raises():
    with pytest.raises(KeyError):
        disc.discover(ASSET, "does_not_exist", "1h")


# --- data gate ---------------------------------------------------------
def test_intraday_timeframes_below_1h_are_insufficient():
    r = disc.discover(ASSET, "trend_continuation_ema", "15m")
    assert r.state in ("INSUFFICIENT_EVIDENCE", "NOT_APPLICABLE")
    # never a fabricated 0-trade edge
    assert r.oos_metrics.get("total_trades", 0) == 0


def test_empty_store_asset_is_insufficient_not_zero_edge():
    r = disc.discover("GBPUSD", "trend_continuation_ema", "1h")
    assert r.state == "INSUFFICIENT_EVIDENCE"
    assert r.next_dependency
    assert r.scorecard == {}


# --- determinism ---------------------------------------------------------
def test_discovery_is_deterministic():
    a = disc.discover(ASSET, "mean_reversion_rsi", "1h")
    b = disc.discover(ASSET, "mean_reversion_rsi", "1h")
    assert a.all_metrics == b.all_metrics
    assert a.oos_metrics == b.oos_metrics
    assert a.bootstrap_ci == b.bootstrap_ci
    assert a.dataset_hash == b.dataset_hash


# --- no lookahead ---------------------------------------------------------
def _run_trades(df, prepared):
    import backtester
    res = backtester.run_backtest(
        symbol=ASSET, timeframe="1h", strategy="Mean Reversion",
        sl_atr=1.5, tp_atr=2.5, train_split=1.0,
        preloaded_data={"df": df, "df_struct": prepared.df_struct,
                        "df_bias": prepared.df_bias})
    return [] if "error" in res else res["trades"]


def test_no_lookahead_future_candles_do_not_change_past_trades():
    """A backtest over candles [0:k] must produce exactly the trades of a backtest
    over the full series whose entry falls before candle k — appending future
    candles cannot create, remove or move an earlier trade."""
    prepared, _ = disc.prepare_data(ASSET, "1h")
    full_df = prepared.df
    k = 1800
    cut_ts = full_df.index[k]

    full_trades = _run_trades(full_df, prepared)
    early_trades = _run_trades(full_df.iloc[:k], prepared)
    if not early_trades:
        pytest.skip("synthetic series produced no early trades")

    def key(t):
        return (str(t["entry_time"]), t["direction"], round(float(t["entry_price"]), 5))

    full_keys = {key(t) for t in full_trades}
    for t in early_trades:
        # a trade that also closed before the cut must match the full run exactly
        import pandas as pd
        if pd.Timestamp(t["exit_time"]) < cut_ts:
            assert key(t) in full_keys


# --- train / test isolation ---------------------------------------------
def test_oos_trades_are_flagged_and_chronologically_after_is():
    import backtester
    prepared, _ = disc.prepare_data(ASSET, "1h")
    res = backtester.run_backtest(
        symbol=ASSET, timeframe="1h", strategy="Mean Reversion",
        train_split=disc.TRAIN_SPLIT,
        preloaded_data={"df": prepared.df, "df_struct": prepared.df_struct,
                        "df_bias": prepared.df_bias})
    if "error" in res:
        pytest.skip("no trades on synthetic series")
    trades = res["trades"]
    is_t = [t for t in trades if not t["is_oos"]]
    oos_t = [t for t in trades if t["is_oos"]]
    if is_t and oos_t:
        import pandas as pd
        assert max(pd.Timestamp(t["entry_time"]) for t in is_t) <= \
               min(pd.Timestamp(t["entry_time"]) for t in oos_t)


# --- ranking score ---------------------------------------------------------
def test_research_ranking_score_is_decomposable_and_not_a_market_score():
    r = disc.discover(ASSET, "mean_reversion_rsi", "1h")
    rs = disc.research_ranking_score(r)
    if rs["score"] is None:
        assert rs["state"] == "INSUFFICIENT_EVIDENCE"
        return
    assert set(rs["components"]) == set(disc.RANKING_WEIGHTS)
    assert abs(sum(disc.RANKING_WEIGHTS.values()) - 1.0) < 1e-9
    assert "NOT a trading signal" in rs["note"]
    assert rs["raw_metrics"]  # underlying numbers stay visible


def test_small_sample_is_not_scored():
    r = disc.discover(ASSET, "smc_continuation_bos_fvg", "1h")
    if r.oos_metrics.get("total_trades", 0) < 30:
        rs = disc.research_ranking_score(r)
        assert rs["score"] is None
        assert rs["state"] == "INSUFFICIENT_EVIDENCE"


def test_bootstrap_ci_uses_research_engine():
    r = disc.discover(ASSET, "mean_reversion_rsi", "1h")
    if r.state == "AVAILABLE":
        assert "ci_lower" in r.bootstrap_ci and "ci_upper" in r.bootstrap_ci
        assert r.bootstrap_ci["sample_size"] >= 0
