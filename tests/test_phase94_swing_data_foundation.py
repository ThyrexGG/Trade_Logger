# -*- coding: utf-8 -*-
"""
Phase 94 — swing-trading data foundation.

Covers: the frozen crypto universe definition, funding daily-aggregation
math, candle shaping from Binance rows, idempotent store writes, the
coverage report structure, and safety invariants (no strategy logic, no
backtest, no signals, holdout never read). Network calls are mocked;
the real ingestion is `python -m phase94_swing_data_foundation --all`.
"""
import inspect
import re

import phase94_swing_data_foundation as p94


# --- A. universe definition ------------------------------------------------------
def test_crypto_universe_is_frozen_tuple_of_uppercase_bases():
    assert isinstance(p94.CRYPTO_UNIVERSE, tuple)
    assert len(p94.CRYPTO_UNIVERSE) >= 20
    for b in p94.CRYPTO_UNIVERSE:
        assert b == b.upper() and b.isalnum()
    assert "BTC" in p94.CRYPTO_UNIVERSE and "ETH" in p94.CRYPTO_UNIVERSE
    # no stablecoins / wrapped / tokenised gold
    for banned in ("USDT", "USDC", "DAI", "WBTC", "WETH", "STETH", "XAUT", "PAXG"):
        assert banned not in p94.CRYPTO_UNIVERSE


def test_aux_fx_pairs_are_silver_and_eurgbp():
    assets = {a for a, _ in p94.AUX_FX}
    assert assets == {"XAGUSD", "EURGBP"}


# --- B. funding daily aggregation ----------------------------------------------
def test_aggregate_funding_daily_sums_within_utc_day():
    # three 8h payments on the same day + one the next day
    day0 = 1_700_000_000 // 86400 * 86400
    payments = [(day0 + 0, 0.0001), (day0 + 28800, 0.0002), (day0 + 57600, -0.00005),
                (day0 + 86400, 0.0003)]
    out = p94._aggregate_funding_daily(payments)
    assert len(out) == 2
    assert out[0][0] == day0
    assert abs(out[0][1] - (0.0001 + 0.0002 - 0.00005)) < 1e-12
    assert abs(out[1][1] - 0.0003) < 1e-12


def test_aggregate_funding_daily_is_sorted_ascending():
    payments = [(200_000, 0.1), (100_000, 0.2), (300_000, 0.3)]
    out = p94._aggregate_funding_daily(payments)
    assert [d for d, _ in out] == sorted(d for d, _ in out)


# --- C. candle shaping from Binance rows --------------------------------------
def test_binance_daily_klines_shapes_rows(monkeypatch):
    day = 1_600_000_000 // 86400 * 86400
    fake_rows = [[day * 1000 + i * p94._DAY_MS, "10.0", "12.0", "9.0", "11.0", "1234.5", 0, "0", 0, "0", "0", "0"]
                 for i in range(5)]

    calls = {"n": 0}

    def fake_get(url, timeout=25):
        calls["n"] += 1
        return fake_rows if calls["n"] == 1 else []

    monkeypatch.setattr(p94, "_get_json", fake_get)
    out = p94._binance_daily_klines("BTC")
    assert all(set(c) == {"time", "open", "high", "low", "close", "volume"} for c in out)
    assert out[0]["open"] == 10.0 and out[0]["high"] == 12.0 and out[0]["close"] == 11.0
    # incomplete "today" bar dropped
    now_day = __import__("time").time() // 86400 * 86400
    assert all(c["time"] < now_day for c in out)


# --- D. idempotency (store upsert is duplicate-safe) -------------------------
def test_ingest_crypto_ohlcv_is_idempotent(monkeypatch):
    day = 1_600_000_000 // 86400 * 86400
    candles = [{"time": day + i * 86400, "open": 10.0 + i, "high": 12.0 + i, "low": 9.0 + i,
                "close": 11.0 + i, "volume": 100.0} for i in range(30)]
    monkeypatch.setattr(p94, "_binance_daily_klines", lambda base, **kw: candles)

    stored = {}

    class _Rep:
        def __init__(self, n):
            self.received = n
            self.inserted = n
            self.updated = 0
            self.rejected = 0

    def fake_upsert(asset, tf, cs, source, source_revision=None):
        key = (asset, tf)
        first = key not in stored
        stored[key] = cs
        return _Rep(len(cs) if first else 0)

    class _Cov:
        first_open_time = day
        last_open_time = day + 29 * 86400

    monkeypatch.setattr(p94.store, "upsert_candles", fake_upsert)
    monkeypatch.setattr(p94.store, "get_coverage", lambda a, t: _Cov())

    r1 = p94.ingest_crypto_ohlcv(("BTC",))
    r2 = p94.ingest_crypto_ohlcv(("BTC",))
    assert r1[0].ok and r2[0].ok
    assert r2[0].stored == 0   # second run inserts nothing new


# --- E. coverage report -------------------------------------------------------
def test_build_coverage_report_structure(monkeypatch):
    import time as _t

    class _Cov:
        count = 500
        first_open_time = 1_500_000_000
        last_open_time = int(_t.time()) - 86400   # yesterday -> "current"

    monkeypatch.setattr(p94.store, "get_coverage", lambda a, t: _Cov())
    monkeypatch.setattr(p94, "get_funding_daily", lambda a: {"n_days": 500})
    rep = p94.build_coverage_report()
    assert set(rep["summary"]) == {"fx_metals_total", "fx_metals_momentum_ready", "crypto_total",
                                   "crypto_momentum_ready", "crypto_funding_ready"}
    assert rep["summary"]["crypto_total"] == len(p94.CRYPTO_UNIVERSE)
    assert rep["holdout_untouched"] is True
    assert all(r["momentum_ready"] for r in rep["crypto_universe"])


def test_coverage_report_marks_thin_series_not_ready(monkeypatch):
    import time as _t

    class _Cov:
        count = 50
        first_open_time = 1_700_000_000
        last_open_time = int(_t.time()) - 86400

    monkeypatch.setattr(p94.store, "get_coverage", lambda a, t: _Cov())
    monkeypatch.setattr(p94, "get_funding_daily", lambda a: None)
    rep = p94.build_coverage_report()
    assert rep["summary"]["crypto_momentum_ready"] == 0
    assert rep["summary"]["crypto_funding_ready"] == 0


# --- F. safety invariants ----------------------------------------------------
def test_module_has_no_strategy_backtest_or_signal_logic():
    src = inspect.getsource(p94)
    for token in ("def backtest", "expectancy", "sharpe", "walk_forward", "_apply_risk", "position_size",
                 "def signal", "long_short", "place_order", "submit_order"):
        assert token.lower() not in src.lower(), f"strategy-ish token present: {token}"


def test_module_never_reads_holdout_or_imports_execution():
    src = inspect.getsource(p94)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    for f in ("order_execution", "broker_adapter", "live_trading", "risk_engine",
              "xauusd_market_conditions", "gold_strategy_baseline", "account_management"):
        assert not any(f in l for l in import_lines), f"forbidden import: {f}"
    for token in ("locked_holdout", "load_holdout", "FROZEN_CONTRACT_HASH"):
        assert token not in src


def test_result_dataclass_reports_data_only_status():
    r = p94.Phase94Result(schema_version="x", generated_at="x", git_commit=None,
                          crypto_ohlcv_outcomes=[], crypto_funding_outcomes=[], aux_fx_outcomes=[],
                          coverage_report={})
    assert r.strategy_status == "DATA_ONLY_NO_STRATEGY_NO_LIVE_EXECUTION"
    assert r.holdout_untouched is True


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}
    monkeypatch.setattr(p94.store, "save_artifact",
                        lambda k, kind, payload: (saved.update(key=k, payload=payload) or "h94"))
    monkeypatch.setattr(p94.store, "load_artifact",
                        lambda k: {"payload": saved["payload"]} if k == saved.get("key") else None)
    r = p94.Phase94Result(schema_version=p94.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00",
                          git_commit="abc", crypto_ohlcv_outcomes=[], crypto_funding_outcomes=[],
                          aux_fx_outcomes=[], coverage_report={"summary": {"crypto_total": 28}})
    assert p94.persist(r) == "h94"
    got = p94.get_result()
    assert got["coverage_report"]["summary"]["crypto_total"] == 28
