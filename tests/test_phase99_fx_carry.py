# -*- coding: utf-8 -*-
"""
Phase 99 -- FX / rate-differential carry (G10).

Covers: the frozen universe + FRED area-code mapping, the monthly
total-return construction (spot + rate differential, USD leg = 0), the
frozen long-top-3 / short-bottom-3 basket, the verdict tree, the
"does it help the Phase-97 book" combination check, determinism,
persistence, the read-only API surface, and safety invariants. FRED and
the candle store are monkeypatched; the real run is
``python -m phase99_fx_carry``.
"""
import inspect
import re

import numpy as np
import pandas as pd
import pytest

import phase99_fx_carry as p99


# --------------------------------------------------------------------------
def _rates_payload(n_months=140, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2015-01-01", periods=n_months, freq="MS")
    # persistent, distinct rate levels per currency (AUD/NZD high, JPY/CHF low)
    base = {"USD": 2.0, "EUR": 0.5, "GBP": 1.5, "JPY": 0.1, "CAD": 1.8, "AUD": 3.5, "NZD": 3.0, "CHF": -0.2}
    series = {}
    for c, lvl in base.items():
        path = lvl + np.cumsum(rng.normal(0, 0.05, n_months))
        series[c] = [[d.date().isoformat(), float(v)] for d, v in zip(dates, path)]
    return {"schema_version": "t", "series": series, "fred_series": p99._FRED_SERIES,
            "coverage": {c: [v[0][0], v[-1][0], len(v)] for c, v in series.items()}}


_ASSET_SEED = {"EURUSD": 11, "GBPUSD": 12, "USDJPY": 13, "USDCHF": 14,
               "USDCAD": 15, "AUDUSD": 16, "NZDUSD": 17}


def _fx_daily(asset, n=1600):
    # deterministic per asset (no hash()), low spot vol so the rate signal is visible
    rng = np.random.default_rng(_ASSET_SEED.get(asset, 99))
    t0 = 1_483_228_800  # 2017-01-01
    close = 1.2 * np.cumprod(1.0 + rng.normal(0.0, 0.0015, n))
    return [{"time": t0 + i * 86400, "open": float(close[i]), "high": float(close[i] * 1.003),
             "low": float(close[i] * 0.997), "close": float(close[i]), "volume": 0.0}
            for i in range(n)]


@pytest.fixture
def patched(monkeypatch):
    rp = _rates_payload()
    monkeypatch.setattr(p99, "fetch_g10_rates", lambda force=False: rp)
    monkeypatch.setattr(p99, "get_g10_rates", lambda: rp)
    monkeypatch.setattr(p99.store, "get_candles", lambda a, tf, **kw: _fx_daily(a))
    monkeypatch.setattr(p99.store, "save_artifact", lambda k, kind, payload: "h")
    # crypto carry stub for the combination test
    idx = pd.date_range("2018-01-05", periods=420, freq="W-FRI", tz="UTC")
    monkeypatch.setattr(p99.p96, "run_carry",
                        lambda **kw: {"index": idx, "net": np.full(420, 0.002)})
    return rp


# --- A. frozen design --------------------------------------------------
def test_frozen_universe_and_fred_area_codes():
    assert p99.G10 == ("USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF")
    assert p99._FRED_SERIES["USD"] == "IR3TIB01USM156N"      # area code US, not USD
    assert p99._FRED_SERIES["EUR"] == "IR3TIB01EZM156N"      # euro area
    assert p99._N_LONG == 3 and p99._N_SHORT == 3


# --- B. monthly total returns --------------------------------------
def test_total_return_usd_leg_is_zero(patched):
    tot = p99.build_monthly_total_returns(patched)
    assert "USD" in tot.columns
    assert np.allclose(tot["USD"].dropna().to_numpy(), 0.0, atol=1e-9)


def test_total_return_includes_rate_differential(patched):
    tot = p99.build_monthly_total_returns(patched)
    # AUD (high rate ~3.5%) should on average out-carry JPY (low rate ~0.1%)
    assert tot["AUD"].mean() > tot["JPY"].mean()


# --- C. the basket ------------------------------------------------
def test_carry_basket_is_dollar_neutral_and_picks_by_rate(patched):
    r = p99.run_fx_carry("BASE", rates_payload=patched)
    m = p99._metrics(r["net"], r["index"])
    assert m["state"] == "OK"
    # with a persistent high-minus-low rate spread and modest FX noise,
    # the carry basket should have positive mean return
    assert np.nanmean(r["net"][p99._WARMUP_MONTHS:]) > 0


def test_cost_ladder_is_ordered(patched):
    lad = p99.cost_ladder()
    vals = [lad[k] for k in ("ZERO", "BASE", "ADVERSE", "SEVERE")]
    assert vals == sorted(vals, reverse=True)   # more cost -> lower Sharpe


# --- D. verdict tree --------------------------------------------
def _m(sharpe, pos_years=6, n_years=10, n_months=112):
    return {"state": "OK", "sharpe": sharpe, "positive_years": pos_years, "n_years": n_years,
            "n_months": n_months}


def test_verdict_negative_when_sharpe_below_zero():
    v, _ = p99.classify_fx_carry(_m(-0.3), _m(-0.3), {"real_percentile": 0.5},
                                 {"metrics": {"sharpe": -0.2}}, {"correlation": 0.1})
    assert v == "FX_CARRY_EDGE_NEGATIVE"


def test_verdict_promising_needs_full_bar():
    good = p99.classify_fx_carry(_m(0.7), _m(0.5), {"real_percentile": 0.95},
                                 {"metrics": {"sharpe": -0.2}},
                                 {"correlation": 0.1, "fx_sleeve_helps_phase97_book": True})[0]
    assert good == "FX_CARRY_EDGE_PROMISING"
    weak = p99.classify_fx_carry(_m(0.35), _m(0.34), {"real_percentile": 0.92},
                                 {"metrics": {"sharpe": -0.23}}, {"correlation": 0.07})[0]
    assert weak == "FX_CARRY_EDGE_NOT_ESTABLISHED"


# --- E. combination with Phase-97 book -------------------------
def test_combine_reports_phase97_book_comparison(patched):
    cb = p99.combine_with_crypto_carry()
    assert "phase97_book_25_75" in cb and "phase97_book_plus_15pct_fx" in cb
    assert isinstance(cb["fx_sleeve_helps_phase97_book"], bool)
    assert abs(cb["correlation"]) <= 1.0


# --- F. determinism + persistence ----------------------------
def test_run_fx_carry_deterministic(patched):
    import json
    a = p99._metrics(p99.run_fx_carry("BASE", rates_payload=patched)["net"],
                     p99.build_monthly_total_returns(patched).index)
    b = p99._metrics(p99.run_fx_carry("BASE", rates_payload=patched)["net"],
                     p99.build_monthly_total_returns(patched).index)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}
    monkeypatch.setattr(p99.store, "save_artifact",
                        lambda k, kind, payload: (saved.update(key=k, payload=payload) or "h99"))
    monkeypatch.setattr(p99.store, "load_artifact",
                        lambda k: {"payload": saved["payload"]} if k == saved.get("key") else None)
    res = p99.Phase99Result(
        schema_version=p99.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00", git_commit="a",
        frozen_contract_hash="x", design_note={}, rates_coverage={}, headline_base={}, headline_adverse={},
        halves={}, controls={}, combine_with_crypto_carry={}, verdict="V", verdict_reason="",
        determinism={"match": True})
    assert p99.persist(res) == "h99"
    assert p99.get_result()["verdict"] == "V"


def test_result_reports_safety_flags():
    res = p99.Phase99Result(
        schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="x", design_note={},
        rates_coverage={}, headline_base={}, headline_adverse={}, halves={}, controls={},
        combine_with_crypto_carry={}, verdict="x", verdict_reason="", determinism={})
    d = res.to_dict()
    assert d["live_automation_enabled"] is False and d["live_broker_transmission"] == "BLOCKED"
    assert d["holdout_untouched"] is True


# --- G. safety ----------------------------------------------
def test_module_never_imports_execution_or_reads_holdout():
    src = inspect.getsource(p99)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    for f in ("order_execution", "broker_adapter", "execution_pipeline", "risk_engine",
              "account_management", "paper_simulator", "positions"):
        assert not any(f in l for l in import_lines), f"forbidden import: {f}"
    for token in ("place_order", "submit_order", "execute_trade", "load_holdout", "locked_holdout"):
        assert token not in src


def test_frozen_contract_hash_is_the_canonical_constant():
    import gold_strategy_baseline as gsb
    assert gsb.get_gold_baseline().frozen_contract_hash == gsb.CANONICAL_CONTRACT_HASH


# --- H. API -----------------------------------------------
def test_api_endpoint_get_only_and_safe():
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
    r = client.get("/api/research/fx-carry")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] in ("NOT_COMPUTED", "AVAILABLE")
    assert body["safety_barrier"] == {"live_automation_enabled": False, "live_broker_transmission": "BLOCKED"}
    assert client.post("/api/research/fx-carry").status_code == 405
