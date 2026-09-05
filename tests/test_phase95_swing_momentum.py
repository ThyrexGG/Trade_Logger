# -*- coding: utf-8 -*-
"""
Phase 95 -- swing momentum (time-series + cross-sectional, daily-bar universe).

Covers: the frozen universe / parameter set, weekly-return panel construction
from daily candles, the TS signal (mean of sign over lookbacks) and XS signal
(count-neutral tertiles), causality of signals and sizing, inverse-vol weight
normalisation, the cost ladder ordering, the sleeve-verdict decision tree,
determinism, persistence round-trip, the read-only API surface, and safety
invariants (no execution/broker/account import, holdout never read, live
automation flags unchanged). Network / store calls are monkeypatched with
synthetic candles; the real run is ``python -m phase95_swing_momentum``.
"""
import inspect
import re

import numpy as np
import pandas as pd
import pytest

import phase95_swing_momentum as p95


# --------------------------------------------------------------------------
# synthetic daily candles
# --------------------------------------------------------------------------
def _daily(asset, n=1400, seed=0, drift=0.0002, vol=0.01):
    rng = np.random.default_rng(abs(hash(asset)) % (2**32) + seed)
    t0 = 1_500_000_000 // 86400 * 86400
    rets = rng.normal(drift, vol, n)
    close = 100.0 * np.cumprod(1.0 + rets)
    return [{"time": t0 + i * 86400, "open": float(close[i]), "high": float(close[i] * 1.01),
             "low": float(close[i] * 0.99), "close": float(close[i]), "volume": 1000.0}
            for i in range(n)]


@pytest.fixture(autouse=True)
def _clear_panel_cache():
    p95._PANEL_CACHE.clear()
    p95._FUNDING_CACHE.clear()
    yield
    p95._PANEL_CACHE.clear()
    p95._FUNDING_CACHE.clear()


@pytest.fixture
def synthetic_store(monkeypatch):
    monkeypatch.setattr(p95.store, "get_candles", lambda a, tf, **kw: _daily(a))
    monkeypatch.setattr(p95.p94, "get_funding_daily", lambda a: None)
    return True


# --- A. frozen design --------------------------------------------------------
def test_universe_is_frozen_and_matches_phase94():
    assert len(p95.FX_METALS_SLEEVE) == 13
    assert p95.CRYPTO_SLEEVE == tuple(f"{b}USD" for b in p95.p94.CRYPTO_UNIVERSE)
    assert "XAUUSD" in p95.FX_METALS_SLEEVE and "XAGUSD" in p95.FX_METALS_SLEEVE
    assert p95.SUBSTRATEGIES == ("TS", "XS", "COMBO")


def test_frozen_parameters_unchanged():
    assert p95._LOOKBACKS_WEEKS == (13, 26, 52)
    assert p95._REBALANCE_WEEKS == 1
    assert p95._SLEEVE_VOL_TARGET == 0.10
    assert p95._COST_LADDER["ZERO"] == 0.0 and p95._COST_LADDER["BASE"] == 1.0
    assert p95._COST_LADDER["ADVERSE"] == 2.0 and p95._COST_LADDER["SEVERE"] == 4.0
    # BTC/ETH cheaper than the rest of crypto; FX majors cheapest
    assert p95._COST_BPS["BTCUSD"] < p95._COST_BPS["SOLUSD"]
    assert p95._COST_BPS["EURUSD"] < p95._COST_BPS["XAUUSD"] < p95._COST_BPS["BTCUSD"]


# --- B. panel construction --------------------------------------------------
def test_build_return_panel_is_weekly(synthetic_store):
    panel = p95.build_return_panel(p95.FX_METALS_SLEEVE)
    assert list(panel.columns) == list(p95.FX_METALS_SLEEVE)
    # weekly Friday index
    assert (panel.index.dayofweek == 4).all()
    diffs = np.diff(panel.index.values).astype("timedelta64[D]").astype(int)
    assert set(diffs.tolist()) <= {7}


# --- C. time-series signal -------------------------------------------------
def test_ts_signal_is_mean_of_sign_over_lookbacks():
    # a strictly rising series -> every trailing return positive -> TS signal +1
    T, N = 80, 3
    rising = np.tile(np.full(T, 0.01), (N, 1)).T
    panel = pd.DataFrame(rising, index=pd.date_range("2020-01-03", periods=T, freq="W-FRI"))
    mom = p95._mom_matrix(panel, (13, 26, 52))
    sig = p95.ts_signal_matrix(mom)
    assert np.allclose(sig[60:], 1.0)
    # a strictly falling series -> -1
    panel2 = pd.DataFrame(-rising, index=panel.index)
    sig2 = p95.ts_signal_matrix(p95._mom_matrix(panel2, (13, 26, 52)))
    assert np.allclose(sig2[60:], -1.0)


def test_ts_signal_is_causal():
    T, N = 90, 2
    rng = np.random.default_rng(1)
    arr = rng.normal(0, 0.01, (T, N))
    panel = pd.DataFrame(arr, index=pd.date_range("2020-01-03", periods=T, freq="W-FRI"))
    sig_full = p95.ts_signal_matrix(p95._mom_matrix(panel, (13, 26, 52)))
    # perturb only the last row; earlier signal rows must be unchanged
    arr2 = arr.copy()
    arr2[-1] += 5.0
    panel2 = pd.DataFrame(arr2, index=panel.index)
    sig_pert = p95.ts_signal_matrix(p95._mom_matrix(panel2, (13, 26, 52)))
    assert np.allclose(np.nan_to_num(sig_full[:-1]), np.nan_to_num(sig_pert[:-1]))


# --- D. cross-sectional signal -------------------------------------------
def test_xs_signal_is_count_neutral_tertiles():
    T, N = 70, 9
    rng = np.random.default_rng(2)
    arr = rng.normal(0, 0.02, (T, N))
    panel = pd.DataFrame(arr, index=pd.date_range("2020-01-03", periods=T, freq="W-FRI"))
    xs = p95.xs_signal_matrix(p95._mom_matrix(panel, (13, 26, 52)))
    for t in range(60, T):
        row = xs[t]
        if np.isfinite(row).any():
            assert (row == 1.0).sum() == (row == -1.0).sum()   # count-neutral
            assert (row == 1.0).sum() == max(1, N // 3)


def test_xs_signal_needs_minimum_names():
    T, N = 70, 4   # < _MIN_XS_NAMES
    panel = pd.DataFrame(np.random.default_rng(3).normal(0, 0.02, (T, N)),
                         index=pd.date_range("2020-01-03", periods=T, freq="W-FRI"))
    xs = p95.xs_signal_matrix(p95._mom_matrix(panel, (13, 26, 52)))
    assert np.isnan(xs[65]).all()


# --- E. sizing ------------------------------------------------------------
def test_raw_weights_gross_normalised_and_inverse_vol():
    sig = np.array([[1.0, -1.0, 1.0]])
    ann_vol = np.array([[0.1, 0.2, 0.4]])
    w = p95._raw_weights(sig, ann_vol)
    assert abs(np.abs(w).sum() - 1.0) < 1e-9
    # lower vol -> larger absolute weight
    assert abs(w[0, 0]) > abs(w[0, 1]) > abs(w[0, 2])


def test_raw_weights_zero_when_signal_or_vol_missing():
    sig = np.array([[np.nan, 1.0]])
    ann_vol = np.array([[0.1, np.nan]])
    w = p95._raw_weights(sig, ann_vol)
    assert np.allclose(w, 0.0)


# --- F. simulation / costs ----------------------------------------------
def test_cost_ladder_monotonic_drag(synthetic_store):
    sharpes = {k: p95.run_sleeve("FX_METALS", cost_key=k)["by_substrategy"]["COMBO"]["metrics"]
               for k in ("ZERO", "BASE", "ADVERSE", "SEVERE")}
    drag = [sharpes[k].get("ann_cost_drag", 0.0) for k in ("ZERO", "BASE", "ADVERSE", "SEVERE")]
    assert drag[0] == 0.0
    assert drag[1] <= drag[2] <= drag[3]


def test_simulate_is_vol_targeted(synthetic_store):
    m = p95.run_sleeve("CRYPTO", cost_key="BASE")["by_substrategy"]["COMBO"]["metrics"]
    # realised vol should be in the neighbourhood of the 10% target (loose band)
    assert 0.03 < m["ann_vol"] < 0.25


# --- G. verdict decision tree ------------------------------------------
def _m(sharpe, pos_years=8, n_years=10):
    return {"state": "OK", "sharpe": sharpe, "positive_years": pos_years, "n_years": n_years}


def test_verdict_negative_when_sharpe_below_zero():
    v, _ = p95.classify_sleeve_verdict(_m(-0.2), _m(-0.3), {"real_percentile": 0.5}, {"metrics": {"sharpe": 0.0}})
    assert v == "SWING_MOMENTUM_EDGE_NEGATIVE"


def test_verdict_confirmed_requires_full_bar():
    strong = _m(0.6, 8, 10)
    v, _ = p95.classify_sleeve_verdict(strong, _m(0.3), {"real_percentile": 0.98},
                                      {"metrics": {"sharpe": 0.2}})
    assert v == "SWING_MOMENTUM_EDGE_CONFIRMED"
    # fails the placebo bar -> not confirmed
    v2, _ = p95.classify_sleeve_verdict(strong, _m(0.3), {"real_percentile": 0.80},
                                       {"metrics": {"sharpe": 0.2}})
    assert v2 != "SWING_MOMENTUM_EDGE_CONFIRMED"


def test_verdict_not_established_midband_without_placebo_separation():
    v, _ = p95.classify_sleeve_verdict(_m(0.3), _m(0.1), {"real_percentile": 0.6},
                                      {"metrics": {"sharpe": 0.1}})
    assert v == "SWING_MOMENTUM_EDGE_NOT_ESTABLISHED"


def test_classify_overall_maps_combined_verdict():
    assert p95.classify_overall("SWING_MOMENTUM_EDGE_CONFIRMED") == "PROFITABLE_SWING_EDGE_FOUND"
    assert p95.classify_overall("SWING_MOMENTUM_EDGE_NOT_ESTABLISHED") == "PROFITABLE_SWING_EDGE_NOT_ESTABLISHED"


# --- H. determinism + persistence -------------------------------------
def test_run_sleeve_is_deterministic(synthetic_store):
    import json
    a = p95.run_sleeve("FX_METALS")["by_substrategy"]["COMBO"]["metrics"]
    b = p95.run_sleeve("FX_METALS")["by_substrategy"]["COMBO"]["metrics"]
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}
    monkeypatch.setattr(p95.store, "save_artifact",
                        lambda k, kind, payload: (saved.update(key=k, payload=payload) or "h95"))
    monkeypatch.setattr(p95.store, "load_artifact",
                        lambda k: {"payload": saved["payload"]} if k == saved.get("key") else None)
    res = p95.Phase95Result(
        schema_version=p95.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00", git_commit="abc",
        frozen_contract_hash="x", design_note={}, universe={}, sleeve_results={}, combined_book={},
        controls={}, per_asset_contribution={}, sleeve_verdicts={"COMBINED_BOOK": {"verdict": "V"}},
        overall_verdict="PROFITABLE_SWING_EDGE_NOT_ESTABLISHED", determinism={"match": True})
    assert p95.persist(res) == "h95"
    assert p95.get_result()["overall_verdict"] == "PROFITABLE_SWING_EDGE_NOT_ESTABLISHED"


def test_result_reports_safety_flags():
    res = p95.Phase95Result(
        schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="x", design_note={},
        universe={}, sleeve_results={}, combined_book={}, controls={}, per_asset_contribution={},
        sleeve_verdicts={}, overall_verdict="x", determinism={})
    d = res.to_dict()
    assert d["live_automation_enabled"] is False
    assert d["live_broker_transmission"] == "BLOCKED"
    assert d["holdout_untouched"] is True


# --- I. safety invariants -------------------------------------------
def test_module_never_imports_execution_or_reads_holdout():
    src = inspect.getsource(p95)
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


def test_no_strategy_search_or_optimization_language_in_code():
    # the design must be frozen -- no grid search / "best" selection in the module body
    for name, obj in vars(p95).items():
        if not inspect.isfunction(obj) or obj.__module__ != p95.__name__:
            continue
        src = inspect.getsource(obj)
        for token in ("GridSearch", "argmax(sharpe", "best_sharpe", "optimize(", ".fit("):
            assert token not in src, f"optimization token {token} in {name}"


# --- J. API surface -------------------------------------------------
def test_api_endpoint_get_only_and_safe():
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)
    r = client.get("/api/research/swing-momentum")
    assert r.status_code == 200
    body = r.json()
    assert body["state"] in ("NOT_COMPUTED", "AVAILABLE")
    assert body["safety_barrier"] == {"live_automation_enabled": False, "live_broker_transmission": "BLOCKED"}
    assert client.post("/api/research/swing-momentum").status_code == 405
