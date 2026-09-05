# -*- coding: utf-8 -*-
"""
Phase 96 -- crypto perpetual funding-rate carry (delta-neutral).

Covers: frozen parameters, perp asset naming, the trailing-funding signal
(causal, annualised), eligibility hysteresis + capacity cap, equal-weight
sizing with the per-coin cap, the carry P&L decomposition
(net == funding + basis + cost), delta-neutrality of the construction,
the exchange-collapse Monte-Carlo (shape + severity monotonicity), the
edge / tail / overall verdict trees, determinism, persistence round-trip,
the read-only API surface, and safety invariants (no execution/broker/
account import, holdout never read, live flags unchanged). Store/network
calls are monkeypatched with synthetic candles; the real run is
``python -m phase96_funding_carry``.
"""
import inspect
import re

import numpy as np
import pandas as pd
import pytest

import phase96_funding_carry as p96


# --------------------------------------------------------------------------
# synthetic data
# --------------------------------------------------------------------------
def _daily(asset, n=1400, seed=0, drift=0.0003):
    rng = np.random.default_rng(abs(hash(asset)) % (2**32) + seed)
    t0 = 1_500_000_000 // 86400 * 86400
    close = 100.0 * np.cumprod(1.0 + rng.normal(drift, 0.02, n))
    return [{"time": t0 + i * 86400, "open": float(close[i]), "high": float(close[i] * 1.02),
             "low": float(close[i] * 0.98), "close": float(close[i]), "volume": 1000.0}
            for i in range(n)]


def _funding(base, rate=0.0004, n=1400):
    t0 = 1_500_000_000 // 86400 * 86400
    return {"symbol": f"{base}USD", "n_days": n,
            "daily_summed_funding_rate": [[t0 + i * 86400, rate] for i in range(n)]}


@pytest.fixture(autouse=True)
def _clear_cache():
    p96._PANEL_CACHE.clear()
    yield
    p96._PANEL_CACHE.clear()


@pytest.fixture
def synthetic(monkeypatch):
    # perp price == spot price (perfectly delta-neutral construction), positive funding
    monkeypatch.setattr(p96.store, "get_candles",
                        lambda a, tf, **kw: _daily(a.replace("PERP", "USD")))
    monkeypatch.setattr(p96.p94, "get_funding_daily", lambda a: _funding(a.replace("USD", "")))
    return True


# --- A. frozen design -----------------------------------------------------
def test_frozen_parameters_unchanged():
    assert p96._FUNDING_LOOKBACK_WEEKS == 4
    assert p96._ENTRY_THRESHOLD_ANN == 0.03
    assert p96._EXIT_THRESHOLD_ANN == 0.0
    assert p96._MAX_POSITIONS == 15
    assert p96._MAX_WEIGHT == 0.15
    assert p96._COST_LADDER == {"ZERO": 0.0, "BASE": 1.0, "ADVERSE": 2.0, "SEVERE": 4.0}
    assert p96.CRYPTO_BASES == p96.p94.CRYPTO_UNIVERSE
    # perps cheaper than spot; majors cheaper than alts
    assert p96._PERP_COST_BPS["BTC"] < p96._SPOT_COST_BPS["BTC"] < p96._SPOT_COST_BPS["SOL"]


def test_perp_asset_naming():
    assert p96.PERP_ASSET("BTC") == "BTCPERP"
    assert p96.SPOT_ASSET("BTC") == "BTCUSD"


# --- B. signal ----------------------------------------------------------
def test_signal_is_trailing_annualised_mean_and_causal():
    T, N = 40, 2
    f = np.full((T, N), 0.001)   # 10 bps/wk
    funding = pd.DataFrame(f, index=pd.date_range("2020-01-03", periods=T, freq="W-FRI"))
    sig = p96._signal_matrix(funding)
    assert np.isnan(sig[:p96._FUNDING_LOOKBACK_WEEKS - 1]).all()
    # annualised: 0.001 * 52
    assert abs(sig[10, 0] - 0.052) < 1e-9
    # causal: perturbing the last row leaves earlier rows unchanged
    f2 = f.copy(); f2[-1] = 9.0
    sig2 = p96._signal_matrix(pd.DataFrame(f2, index=funding.index))
    assert np.allclose(np.nan_to_num(sig[:-1]), np.nan_to_num(sig2[:-1]))


# --- C. eligibility ---------------------------------------------------
def test_eligibility_entry_exit_hysteresis():
    prev = np.array([False, True, True])
    # coin0 below entry, coin1 between exit and entry (stays), coin2 above entry
    sig = np.array([0.01, 0.02, 0.10])
    elig = p96._eligibility(sig, prev, entry_thr=0.03)
    assert list(elig) == [False, True, True]
    # coin1 now negative -> exits even though held
    elig2 = p96._eligibility(np.array([0.01, -0.01, 0.10]), prev, entry_thr=0.03)
    assert list(elig2) == [False, False, True]


def test_eligibility_capacity_cap_keeps_highest_funding():
    n = 20
    sig = np.linspace(0.05, 0.30, n)          # all above entry
    prev = np.zeros(n, dtype=bool)
    elig = p96._eligibility(sig, prev, entry_thr=0.03)
    assert elig.sum() == p96._MAX_POSITIONS
    # the kept ones are the highest-funding tail
    assert elig[-p96._MAX_POSITIONS:].all()
    assert not elig[:n - p96._MAX_POSITIONS].any()


def test_target_weights_equal_with_cap():
    # 10 eligible -> 1/10 = 0.10 < 0.15 cap -> fully deployed, equal weight
    w = p96._target_weights(np.array([True] * 10))
    assert np.allclose(w, 0.1)
    assert abs(w.sum() - 1.0) < 1e-9
    # 4 eligible -> 1/4 = 0.25 > 0.15 cap -> cap binds, book only 60% deployed
    w2 = p96._target_weights(np.array([True, True, True, True, False]))
    assert np.allclose(w2[w2 > 0], 0.15)
    assert abs(w2.sum() - 0.6) < 1e-9


# --- D. carry P&L decomposition ------------------------------------
def test_net_equals_funding_plus_basis_plus_cost(synthetic):
    r = p96.run_carry(cost_key="BASE")
    recon = r["funding"] + r["basis"] + r["cost"]
    assert np.allclose(r["net"], recon, atol=1e-12)


def test_construction_is_delta_neutral_when_perp_equals_spot(synthetic):
    # perp price == spot price in the fixture -> basis term is exactly zero
    r = p96.run_carry(cost_key="BASE")
    assert np.allclose(r["basis"], 0.0, atol=1e-12)
    # and with positive funding the net (ex-cost) is positive on average
    assert (r["funding"][p96._WARMUP_WEEKS:] >= 0).mean() > 0.9


def test_zero_cost_beats_or_equals_costed(synthetic):
    z = p96._metrics(p96.run_carry(cost_key="ZERO")["net"], p96.build_panels()["spot"].index)
    b = p96._metrics(p96.run_carry(cost_key="SEVERE")["net"], p96.build_panels()["spot"].index)
    assert z["cagr"] >= b["cagr"]


# --- E. tail stress -------------------------------------------------
def test_exchange_collapse_grid_shape_and_monotonic_severity(synthetic):
    st = p96.exchange_collapse_stress(paths=200, seed=1)
    assert "p0.05_sev0.50" in st["grid"]
    # for a fixed prob, higher severity -> worse median total return
    a = st["grid"]["p0.10_sev0.30"]["median_total_return"]
    c = st["grid"]["p0.10_sev1.00"]["median_total_return"]
    assert c <= a
    assert st["deterministic_worst_case"]["total_return_if_full_loss_at_worst_week"] is not None


# --- F. verdict trees ----------------------------------------------
def _bm(sharpe, pos_years=9, n_years=10):
    return {"state": "OK", "sharpe": sharpe, "positive_years": pos_years, "n_years": n_years}


def test_edge_negative_when_sharpe_below_zero():
    v, _ = p96.classify_edge(_bm(-0.1), _bm(-0.2), {"real_percentile": 0.5},
                             {"pooled_corr": 0.3}, {"btc": {"beta": 0.0}})
    assert v == "FUNDING_CARRY_EDGE_NEGATIVE"


def test_edge_confirmed_requires_full_bar():
    strong_base, strong_adv = _bm(1.8), _bm(1.0)
    good = p96.classify_edge(strong_base, strong_adv, {"real_percentile": 0.99},
                             {"pooled_corr": 0.4}, {"btc": {"beta": 0.02}})[0]
    assert good == "FUNDING_CARRY_EDGE_CONFIRMED"
    # residual BTC beta too big -> downgraded
    leaky = p96.classify_edge(strong_base, strong_adv, {"real_percentile": 0.99},
                              {"pooled_corr": 0.4}, {"btc": {"beta": 0.4}})[0]
    assert leaky != "FUNDING_CARRY_EDGE_CONFIRMED"


def test_tail_verdict_tree():
    survives = {"grid": {
        "p0.05_sev0.50": {"p05_total_return": 0.2, "mean_total_return": 0.5,
                          "prob_total_return_negative": 0.03},
        "p0.10_sev1.00": {"prob_total_return_negative": 0.15, "p05_total_return": -0.4}}}
    assert p96.classify_tail(survives)[0] == "FUNDING_CARRY_SURVIVES_TAIL_YES"
    marginal = {"grid": {
        "p0.05_sev0.50": {"p05_total_return": 0.1, "mean_total_return": 0.5,
                          "prob_total_return_negative": 0.05},
        "p0.10_sev1.00": {"prob_total_return_negative": 0.48, "p05_total_return": -1.0}}}
    assert p96.classify_tail(marginal)[0] == "FUNDING_CARRY_SURVIVES_TAIL_MARGINAL"
    dies = {"grid": {
        "p0.05_sev0.50": {"p05_total_return": -0.6, "mean_total_return": -0.3,
                          "prob_total_return_negative": 0.7}}}
    assert p96.classify_tail(dies)[0] == "FUNDING_CARRY_SURVIVES_TAIL_NO"


def test_classify_overall():
    assert p96.classify_overall("FUNDING_CARRY_EDGE_CONFIRMED",
                                "FUNDING_CARRY_SURVIVES_TAIL_YES") == "PROFITABLE_SWING_EDGE_FOUND"
    assert p96.classify_overall("FUNDING_CARRY_EDGE_PROMISING",
                                "FUNDING_CARRY_SURVIVES_TAIL_MARGINAL") == "PROFITABLE_SWING_EDGE_PROMISING"
    assert p96.classify_overall("FUNDING_CARRY_EDGE_NOT_ESTABLISHED",
                                "FUNDING_CARRY_SURVIVES_TAIL_NO") == "PROFITABLE_SWING_EDGE_NOT_ESTABLISHED"


# --- G. determinism + persistence --------------------------------
def test_run_carry_is_deterministic(synthetic):
    import json
    a = p96._metrics(p96.run_carry()["net"], p96.build_panels()["spot"].index)
    b = p96._metrics(p96.run_carry()["net"], p96.build_panels()["spot"].index)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}
    monkeypatch.setattr(p96.store, "save_artifact",
                        lambda k, kind, payload: (saved.update(key=k, payload=payload) or "h96"))
    monkeypatch.setattr(p96.store, "load_artifact",
                        lambda k: {"payload": saved["payload"]} if k == saved.get("key") else None)
    res = p96.Phase96Result(
        schema_version=p96.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00", git_commit="abc",
        frozen_contract_hash="x", design_note={}, universe=[], perp_ingestion=[], perp_data_ready={},
        headline_base={}, headline_adverse={}, halves={}, controls={}, per_coin_breakdown={},
        tail_stress={}, edge_verdict="E", edge_reason="", tail_verdict="T", tail_reason="",
        overall_verdict="PROFITABLE_SWING_EDGE_PROMISING", determinism={"match": True})
    assert p96.persist(res) == "h96"
    assert p96.get_result()["overall_verdict"] == "PROFITABLE_SWING_EDGE_PROMISING"


def test_result_reports_safety_flags():
    res = p96.Phase96Result(
        schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="x", design_note={},
        universe=[], perp_ingestion=[], perp_data_ready={}, headline_base={}, headline_adverse={},
        halves={}, controls={}, per_coin_breakdown={}, tail_stress={}, edge_verdict="x", edge_reason="",
        tail_verdict="x", tail_reason="", overall_verdict="x", determinism={})
    d = res.to_dict()
    assert d["live_automation_enabled"] is False
    assert d["live_broker_transmission"] == "BLOCKED"
    assert d["holdout_untouched"] is True


# --- H. safety invariants --------------------------------------
def test_module_never_imports_execution_or_reads_holdout():
    src = inspect.getsource(p96)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    for f in ("order_execution", "broker_adapter", "live_trading", "risk_engine",
              "account_management", "mt5_execution", "trade_execution"):
        assert not any(f in l for l in import_lines), f"forbidden import: {f}"
    for token in ("place_order", "submit_order", "execute_trade", "delete_account", "remove_account",
                  "load_holdout", "locked_holdout", "read_holdout"):
        assert token not in src, f"forbidden token: {token}"


def test_frozen_contract_hash_is_the_canonical_constant():
    import gold_strategy_baseline as gsb
    assert gsb.get_gold_baseline().frozen_contract_hash == gsb.CANONICAL_CONTRACT_HASH


def test_no_optimization_language_in_module():
    for name, obj in vars(p96).items():
        if not inspect.isfunction(obj) or obj.__module__ != p96.__name__:
            continue
        s = inspect.getsource(obj)
        for token in ("GridSearch", "argmax(sharpe", "best_sharpe", ".fit("):
            assert token not in s, f"optimization token {token} in {name}"


# --- I. API surface ------------------------------------------
def test_api_endpoint_get_only_and_safe():
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
    r = client.get("/api/research/funding-carry")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] in ("NOT_COMPUTED", "AVAILABLE")
    assert body["safety_barrier"] == {"live_automation_enabled": False, "live_broker_transmission": "BLOCKED"}
    assert client.post("/api/research/funding-carry").status_code == 405
