# -*- coding: utf-8 -*-
"""
Phase 74 — MT5 intraday provider, dataset manifest, data-quality gates, safety.

MT5 needs a Windows terminal + live account, so the provider tests here assert
the *contract* (import-safety, credential hygiene, symbol mapping, graceful
degradation, no execution imports) rather than a live pull. Tests that need real
ingested candles skip when the DB has none.
"""
import importlib
import inspect
import os

import pytest

import database
import dataset_manifest
import historical_data_store as store
import historical_provider as hp
import mt5_provider

BASE = 1_400_000_000
# A canonical symbol that is NOT in the MT5 research universe, so real ingested
# candles can never collide with these fixtures (Phase 74 ingested real data for
# every universe instrument).
ASSET = "ZZTESTPAIR"


def _clean():
    database.init_db()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(f"DELETE FROM historical_candles WHERE asset={ph}", (ASSET,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _iso():
    _clean()
    yield
    _clean()


def _series(n, tf_sec, start=BASE, p0=0.65):
    return [{"time": start + i * tf_sec, "open": round(p0 + 1e-5 * i, 5),
             "high": round(p0 + 1e-5 * i + 3e-4, 5), "low": round(p0 + 1e-5 * i - 3e-4, 5),
             "close": round(p0 + 1e-5 * i + 1e-4, 5), "volume": 100} for i in range(n)]


# --- MT5 provider contract (§4, §5, §6, §13) -------------------------------
def test_mt5_provider_registers_itself():
    assert "mt5" in hp._PROVIDERS
    assert hp._PROVIDERS["mt5"] is mt5_provider.get()


def test_mt5_import_safe_without_package():
    # module imported fine above; if the package is missing it degrades, never raises
    cap = mt5_provider.get().capability("XAUUSD", "1m")
    assert isinstance(cap, hp.ProviderCapability)
    if not mt5_provider._available():
        assert cap.state == hp.ProviderCapabilityState.PROVIDER_UNAVAILABLE


def test_mt5_vendor_symbol_is_defensible_spot_not_futures():
    # §13 — XAUUSD must map to a broker spot symbol, never a GC futures contract
    assert mt5_provider.vendor_symbol("XAUUSD") == "XAUUSD"
    assert "GC" not in mt5_provider.vendor_symbol("XAUUSD")
    assert mt5_provider.vendor_symbol("EURUSD") == "EURUSD"


def test_mt5_unknown_instrument_and_timeframe():
    prov = mt5_provider.get()
    assert prov.capability("DOGEUSD", "1h").state == hp.ProviderCapabilityState.INSTRUMENT_NOT_SUPPORTED
    assert prov.capability("XAUUSD", "3m").state == hp.ProviderCapabilityState.TIMEFRAME_NOT_SUPPORTED


def test_mt5_provider_never_returns_credentials():
    src = inspect.getsource(mt5_provider)
    # credentials are read from env and never placed on any returned object
    prov = mt5_provider.get()
    cap = prov.capability("XAUUSD", "15m")
    blob = repr(cap.to_dict()).lower()
    for tok in ("mt5_password", "password",
                os.getenv("MT5_PASSWORD", "\x00unlikely\x00").lower()):
        if not tok:                     # MT5_PASSWORD unset/empty -> nothing to leak
            continue
        assert tok not in blob
    assert "os.getenv(\"MT5_PASSWORD\")" in src or "os.getenv('MT5_PASSWORD')" in src


def test_get_provider_honours_explicit_mt5(monkeypatch):
    monkeypatch.setenv("HISTORICAL_OHLCV_PROVIDER", "mt5")
    assert hp.get_provider().name == "mt5"


def test_get_provider_defaults_to_yfinance(monkeypatch):
    monkeypatch.delenv("HISTORICAL_OHLCV_PROVIDER", raising=False)
    assert hp.get_provider().name in ("yfinance", "yahoo")


# --- no execution / broker / risk imports (safety invariant) --------------
def test_phase74_modules_have_no_execution_imports():
    for name in ("mt5_provider", "dataset_manifest", "native_gold_revalidation"):
        src = inspect.getsource(importlib.import_module(name))
        for bad in ("execution_pipeline", "broker_adapter", "risk_gateway",
                    "reconciliation", "order_execution", "live_trading"):
            assert bad not in src, f"{name} imports {bad}"


# --- data quality gates (§9, §12) ----------------------------------------
def test_ohlc_consistency_rejects_broken_candle():
    rep = store.upsert_candles(ASSET, "15m",
                               [{"time": BASE, "open": 1.0, "high": 0.5, "low": 0.9,
                                 "close": 1.0, "volume": 1}], source="qa_test")
    assert rep.rejected == 1 and "HIGH_LT_LOW" in rep.reject_reasons


def test_duplicate_open_time_is_idempotent():
    s = _series(200, 900)
    r1 = store.upsert_candles(ASSET, "15m", s, source="qa_test")
    r2 = store.upsert_candles(ASSET, "15m", s, source="qa_test")
    assert r1.inserted == 200
    assert r2.inserted == 0 and r2.updated == 200
    assert store.get_coverage(ASSET, "15m").count == 200


def test_15m_interval_alignment_flagged_suspect():
    rep = store.upsert_candles(ASSET, "15m",
                               [{"time": BASE + 37, "open": 1, "high": 1.1, "low": 0.9,
                                 "close": 1.0, "volume": 1}], source="qa_test")
    assert rep.suspect == 1


def test_no_silent_multi_vendor_merge_on_one_key():
    store.upsert_candles(ASSET, "15m", _series(100, 900), source="yfinance")
    srcs = store.series_sources(ASSET, "15m")
    assert srcs == ["yfinance"]
    store.clear_series(ASSET, "15m", only_source="yfinance")
    store.upsert_candles(ASSET, "15m", _series(100, 900), source="mt5")
    assert store.series_sources(ASSET, "15m") == ["mt5"]


def test_analyze_gaps_contiguous_15m_has_no_anomalies():
    store.upsert_candles(ASSET, "15m", _series(4 * 24 * 10, 900), source="qa_test")
    ga = store.analyze_gaps(ASSET, "15m")
    assert ga["anomalous_gaps"] == 0
    assert "weekend_gaps" in ga


# --- dataset manifest (§14) --------------------------------------------
def test_manifest_records_provenance_and_holdout_isolation():
    store.upsert_candles(ASSET, "15m", _series(400, 900), source="mt5")
    store.upsert_candles(ASSET, "1h", _series(200, 3600), source="mt5")
    m = dataset_manifest.build_manifest(ASSET, timeframes=("15m", "1h"))
    assert m.canonical_symbol == ASSET
    assert m.providers == ["mt5"]
    assert len(m.content_hash) == 64
    assert "holdout" in m.holdout_isolation.lower()
    assert "never read" in m.holdout_isolation.lower()
    tfs = {s["timeframe"]: s for s in m.series}
    assert tfs["15m"]["provider"] == "mt5"
    assert tfs["15m"]["asset_type"] == "BROKER_SPOT"
    assert "GC" not in (tfs["15m"]["vendor_symbol"] or "")


def test_manifest_hash_is_deterministic():
    store.upsert_candles(ASSET, "15m", _series(300, 900), source="mt5")
    a = dataset_manifest.build_manifest(ASSET, timeframes=("15m",)).content_hash
    b = dataset_manifest.build_manifest(ASSET, timeframes=("15m",)).content_hash
    assert a == b


def test_manifest_flags_yahoo_gold_as_futures_proxy():
    note = dataset_manifest._PROVIDER_SYMBOL_NOTE["yahoo"]["XAUUSD"]
    assert note[1] == "GOLD_FUTURES_PROXY"
    assert "spot" in note[2].lower()


# --- frozen contract + holdout untouched (§41 STOP 6/7) ----------------
def test_frozen_hash_intact():
    from xauusd_market_conditions import FROZEN_CONTRACT_HASH
    assert FROZEN_CONTRACT_HASH == \
        "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"


def test_frozen_holdout_baseline_unchanged():
    from xauusd_forward_accumulation import HistoricalVsForwardComparator as H
    b = H.LOCKED_HISTORICAL_BASELINE
    assert (b["n"], b["expectancy_r"], b["win_rate_pct"],
            b["profit_factor"], b["max_drawdown_r"]) == (82, 0.637, 58.6, 2.52, 4.0)


def test_no_research_module_reads_the_holdout():
    for name in ("native_gold_revalidation", "dataset_manifest", "mt5_provider",
                 "data_coverage", "strategy_discovery"):
        src = inspect.getsource(importlib.import_module(name))
        assert "LOCKED_HISTORICAL_BASELINE" not in src
        assert "forward_accumulation" not in src


def test_safety_flags_untouched():
    from xauusd_forward_lifecycle import ForwardExecutionLifecycleEngine as E
    assert E.LIVE_AUTOMATION_ENABLED is False
    assert E.LIVE_BROKER_TRANSMISSION == "BLOCKED"
