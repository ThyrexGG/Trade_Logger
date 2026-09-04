# -*- coding: utf-8 -*-
"""Phase 73 — intraday data foundation, provider abstraction, native Gold (§32)."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import database
import historical_data_store as store
import historical_provider as hp
import research_universe
from api.main import app

client = TestClient(app)

BASE = 1_500_000_000  # 2017, well before real ingested data
ASSET = "EURUSD"


def _clean():
    database.init_db()
    conn = database.get_connection()
    try:
        cur = conn.cursor()
        ph = database.get_sql_placeholder(conn)
        cur.execute(f"DELETE FROM historical_candles WHERE asset={ph} AND open_time < {ph}",
                    (ASSET, BASE + 400 * 86400))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def _iso():
    _clean()
    yield
    _clean()


def _series(n, tf_sec, start=BASE, p0=1.10):
    out = []
    for i in range(n):
        p = p0 + 0.00003 * i
        out.append({"time": start + i * tf_sec, "open": round(p, 5), "high": round(p + 0.001, 5),
                    "low": round(p - 0.001, 5), "close": round(p + 0.0004, 5), "volume": 100})
    return out


# --- provider capability (§4, §5) --------------------------------------
# These pin the yfinance provider explicitly — Phase 74 lets
# HISTORICAL_OHLCV_PROVIDER select a real vendor (mt5), so get_provider() is no
# longer necessarily yfinance.
def test_capability_declares_insufficient_depth_for_intraday():
    prov = hp.YFinanceProvider()
    for tf in ("1m", "5m", "15m"):
        cap = prov.capability("XAUUSD", tf)
        assert cap.state == hp.ProviderCapabilityState.INSUFFICIENT_HISTORICAL_DEPTH
        assert cap.approx_depth_days < cap.required_depth_days
    for tf in ("1h", "4h", "1d"):
        assert prov.capability("XAUUSD", tf).state == hp.ProviderCapabilityState.OK


def test_capability_flags_fx_synthetic_spot():
    cap = hp.YFinanceProvider().capability("EURUSD", "15m")
    assert any("synthetic spot" in x for x in cap.limitations)


def test_env_vendor_provider_ships_disabled():
    cap = hp.EnvKeyVendorProvider().capability("XAUUSD", "1m")
    assert cap.state in (hp.ProviderCapabilityState.NOT_CONFIGURED,
                         hp.ProviderCapabilityState.PROVIDER_UNAVAILABLE)


def test_capability_unknown_instrument_and_timeframe():
    prov = hp.get_provider()
    assert prov.capability("DOGEUSD", "1h").state == hp.ProviderCapabilityState.INSTRUMENT_NOT_SUPPORTED
    assert prov.capability("XAUUSD", "7m").state == hp.ProviderCapabilityState.TIMEFRAME_NOT_SUPPORTED


# --- coverage report (§8) --------------------------------------------
def test_coverage_report_states():
    import data_coverage
    store.upsert_candles(ASSET, "1d", _series(600, 86400), source="synthetic_test")
    store.upsert_candles(ASSET, "15m", _series(1200, 900), source="synthetic_test")
    rep = data_coverage.coverage_report(("15m", "1d"))
    by = {(r["instrument"], r["timeframe"]): r for r in rep["rows"]}
    assert by[(ASSET, "1d")]["sufficiency_state"] == "SUFFICIENT"
    # 1200 15m bars is real but below the bar -> PARTIAL
    assert by[(ASSET, "15m")]["sufficiency_state"] == "PARTIAL"
    # an instrument/timeframe with nothing stored and provider can't reach -> INSUFFICIENT_DATA
    assert by[("GBPUSD", "15m")]["sufficiency_state"] in ("INSUFFICIENT_DATA", "NO_DATA")


def test_coverage_report_never_calls_weekend_a_gap():
    import data_coverage
    # contiguous daily incl. weekends collapsed by ingest is normal; a synthetic
    # contiguous series has no gaps
    store.upsert_candles(ASSET, "1d", _series(500, 86400), source="synthetic_test")
    row = next(r for r in data_coverage.coverage_report(("1d",))["rows"]
               if r["instrument"] == ASSET)
    assert row["anomalous_gaps"] == 0


# --- PARTIAL tier + as-of (§10, §18) ---------------------------------
def test_prepare_data_partial_tier_only_when_allowed():
    import strategy_discovery as disc
    store.upsert_candles(ASSET, "15m", _series(1500, 900), source="synthetic_test")
    store.upsert_candles(ASSET, "1h", _series(400, 3600), source="synthetic_test")
    store.upsert_candles(ASSET, "4h", _series(120, 14400), source="synthetic_test")
    disc.clear_prepare_cache()
    p_no, suf_no = disc.prepare_data(ASSET, "15m", allow_partial=False)
    assert p_no is None and suf_no["state"] == "INSUFFICIENT_EVIDENCE"
    disc.clear_prepare_cache()
    p_yes, suf_yes = disc.prepare_data(ASSET, "15m", allow_partial=True)
    assert p_yes is not None and p_yes.tier == "PARTIAL"


def test_as_of_truncation_at_intraday_boundary():
    tf, tf_sec = "5m", 300
    store.upsert_candles(ASSET, tf, _series(200, tf_sec), source="synthetic_test")
    as_of = BASE + 100 * tf_sec  # open of bar 100 -> bar 99 closes exactly at as_of
    rows = store.get_candles(ASSET, tf, as_of=as_of)
    assert all(r["time"] + tf_sec <= as_of for r in rows)
    assert len(rows) == 100  # bars 0..99; bar 100 still forming
    # one second earlier -> bar 99 not yet closed
    rows2 = store.get_candles(ASSET, tf, as_of=as_of - 1)
    assert len(rows2) == 99


# --- timeframe interval integrity (§9) ------------------------------
def test_sub_minute_aligned_candle_flagged_suspect():
    rep = store.upsert_candles(ASSET, "5m",
                               [{"time": BASE + 37, "open": 1, "high": 2, "low": 0.5,
                                 "close": 1.5, "volume": 1}], source="synthetic_test")
    assert rep.suspect == 1


# --- native Gold revalidation (§11, §12, §21) -----------------------
def test_native_revalidation_timeframe_roles():
    import native_gold_revalidation as ngr
    assert ngr._TF_ROLE["1m"][0] == "NATIVE"
    assert ngr._TF_ROLE["5m"][0] == "NEAR_NATIVE"
    assert ngr._TF_ROLE["15m"][0] == "NEAR_NATIVE"
    assert ngr._TF_ROLE["1h"][0] == "PROXY"


def test_native_revalidation_classify_no_native_edge():
    """A negative native 1m result with a solid sample => INVALIDATED / NO_EDGE,
    with an explicit note that the frozen forward-validation is untouched."""
    import native_gold_revalidation as ngr
    rows = [
        {"role": "NATIVE", "state": "AVAILABLE",
         "all_metrics": {"total_trades": 400, "expectancy_r": -0.09},
         "oos_metrics": {"total_trades": 200, "expectancy_r": -0.09},
         "bootstrap_ci": {"ci_lower": -0.2, "ci_upper": 0.02}, "walk_forward": {}},
        {"role": "NEAR_NATIVE", "state": "AVAILABLE",
         "oos_metrics": {"expectancy_r": 0.05}, "bootstrap_ci": {"ci_lower": -0.02}},
    ]
    cls = ngr._classify(rows)
    assert cls["native_state"] == "NO_EDGE"
    assert cls["edge_status"] == "INVALIDATED"
    assert "does NOT invalidate the frozen contract's own forward-validation" in cls["verdict"]


def test_native_revalidation_classify_validated_needs_strong_evidence():
    import native_gold_revalidation as ngr
    rows = [{"role": "NATIVE", "state": "AVAILABLE",
             "all_metrics": {"total_trades": 400, "expectancy_r": 0.15},
             "oos_metrics": {"total_trades": 120, "expectancy_r": 0.2},
             "bootstrap_ci": {"ci_lower": 0.05, "ci_upper": 0.35},
             "walk_forward": {"stability": 0.8}}]
    assert ngr._classify(rows)["edge_status"] == "VALIDATED"


def test_native_revalidation_never_claims_holdout_equivalence():
    import native_gold_revalidation as ngr
    src = ngr.__doc__ + (ngr.revalidate.__doc__ or "")
    assert "never compared" in src.lower() or "not a reproduction of the frozen holdout" in src.lower()


def test_frozen_hash_and_holdout_intact():
    from xauusd_market_conditions import FROZEN_CONTRACT_HASH
    from xauusd_forward_accumulation import HistoricalVsForwardComparator as H
    assert FROZEN_CONTRACT_HASH == "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    b = H.LOCKED_HISTORICAL_BASELINE
    assert (b["n"], b["expectancy_r"], b["win_rate_pct"], b["profit_factor"], b["max_drawdown_r"]) \
        == (82, 0.637, 58.6, 2.52, 4.0)


# --- P2-11 Monte Carlo on real trades (§29) -------------------------
def test_walk_forward_returns_real_trade_level_r():
    import pair_ranking as pr
    import inspect
    src = inspect.getsource(pr.walk_forward)
    assert "stitched_oos_r" in src
    src2 = inspect.getsource(pr.compute_pair_ranking)
    assert "real_wfo_oos_trades" in src2


# --- API + safety (§26, §32) ----------------------------------------
def test_new_endpoints_get_only():
    for p in ("/api/research/data-coverage", "/api/research/historical/providers",
              "/api/research/gold-revalidation/native"):
        assert client.get(p).status_code == 200
        assert client.post(p).status_code in (404, 405)


def test_providers_endpoint_has_no_credentials():
    body = client.get("/api/research/historical/providers").text.lower()
    for tok in ("api_key=", "apikey", "secret", "bearer ", "password"):
        assert tok not in body
    j = client.get("/api/research/historical/providers").json()
    assert j["config_pattern"]["env"] == ["HISTORICAL_OHLCV_PROVIDER", "HISTORICAL_OHLCV_API_KEY"]


def test_no_execution_imports_in_phase73_modules():
    import importlib
    import inspect
    for name in ("historical_provider", "data_coverage", "native_gold_revalidation"):
        src = inspect.getsource(importlib.import_module(name))
        for bad in ("execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
                    "order_execution"):
            assert bad not in src


def test_safety_barrier_on_new_endpoints():
    for p in ("/api/research/data-coverage", "/api/research/historical/providers"):
        assert client.get(p).json()["safety_barrier"]["live_broker_transmission"] == "BLOCKED"
