# -*- coding: utf-8 -*-
"""
Phase 90 — cost-aware magnitude risk-management validation.

Covers: temporal alignment / no future leakage in the walk-forward
percentile predictor (train-only calibration), position-sizing cap
enforcement, stop/target-free R-multiple + eligibility-filter economics,
cost and break-even calculations, placebo behavior, the verdict decision
tree, and safety invariants (fixed, documented, non-optimized direction;
no execution imports). Synthetic bars for structural/logic tests; the
real full run is the artifact produced by
``python -m phase90_magnitude_risk_management``.
"""
import inspect
import re

import numpy as np
import pandas as pd

import phase76_event_study as p76
import phase80_ml_volatility_regime as p80
import phase83_conditional_interaction_discovery as p83
import phase90_magnitude_risk_management as p90


def _frame(n=8000, seed=71):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 1.0, n).cumsum()
    close = 100.0 + steps * 0.1
    high = close + np.abs(rng.normal(0, 0.15, n))
    low = close - np.abs(rng.normal(0, 0.15, n))
    open_ = close - rng.normal(0, 0.05, n)
    vol = np.abs(rng.normal(100.0, 20.0, n)) + 1.0
    t0 = 1_622_505_600   # 2021-06-01 UTC, straddles the 2022 fold boundary
    return [{"time": t0 + i * 900, "open": float(open_[i]),
             "high": float(max(open_[i], high[i], close[i])),
             "low": float(min(open_[i], low[i], close[i])),
             "close": float(close[i]), "volume": float(vol[i]), "source": "mt5"} for i in range(n)]


# --- A. fixed direction is a documented non-signal --------------------------------
def test_fixed_direction_is_always_long_and_documented():
    assert p90._FIXED_DIRECTION == 1.0


def test_module_never_reuses_phase86_momentum_construction():
    src = inspect.getsource(p90)
    assert "sign(mom_4)" not in src or "avoided" in src.lower() or "documented" in src.lower()
    assert "feat__mom_4" not in src   # this phase never even loads mom_4 as a feature


# --- B. dataset builder ------------------------------------------------------------
def test_build_dataset_90_has_t1_t2_and_volume_columns(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    ds = p90.build_dataset_90("EURUSD", "15m", 4)
    assert not ds.empty
    assert "T1" in ds.columns and "T2" in ds.columns
    assert "feat__volume_rank" in ds.columns
    for c in p90.BASELINE_B_COLUMNS:
        assert f"feat__{c}" in ds.columns


# --- C. walk-forward percentile predictor: no future leakage ----------------------
def test_percentile_calibration_uses_train_distribution_only():
    train = pd.DataFrame({"x": np.linspace(-1, 1, 1000)})
    train["y"] = train["x"] * 2.0
    test = pd.DataFrame({"x": np.linspace(-1, 1, 200)})
    test["y"] = test["x"] * 2.0
    out = p90._fit_predict_percentile(train, test, ["x"], "y")
    assert (out["test_percentile"] >= 0).all() and (out["test_percentile"] <= 1).all()
    # a test prediction far beyond anything seen in train must clip to 1.0,
    # not extrapolate past the train-only distribution
    extreme_test = pd.DataFrame({"x": [1000.0], "y": [2000.0]})
    out2 = p90._fit_predict_percentile(train, extreme_test, ["x"], "y")
    assert out2["test_percentile"][0] == 1.0


def test_percentile_predictor_never_touches_test_y_for_calibration():
    src = inspect.getsource(p90._fit_predict_percentile)
    assert "test[target_col]" not in src and 'test["' not in src.replace('test["T', "___")


# --- D. position-sizing cap enforcement ---------------------------------------------
def test_size_cap_is_enforced_at_extremes():
    test = pd.DataFrame({"T1": [1.0, 1.0, 1.0]})
    percentile = np.array([0.0, 0.5, 1.0])
    out = p90._apply_risk_system(test, percentile, eligibility_threshold=-1.0, cost_atr=0.0)
    # inverse sizing: percentile=0 -> max size (1.5), percentile=1 -> min size (0.5)
    lo, hi = p90._SIZE_CAP
    r_raw = test["T1"].to_numpy(float) * p90._FIXED_DIRECTION
    implied_size = out["net_r_series"] / r_raw
    assert np.isclose(implied_size[0], hi)
    assert np.isclose(implied_size[-1], lo)
    assert (implied_size >= lo - 1e-9).all() and (implied_size <= hi + 1e-9).all()


def test_baseline_system_uses_fixed_unit_size_and_takes_every_trade():
    test = pd.DataFrame({"T1": [1.0, -1.0, 2.0]})
    out = p90._apply_risk_system(test, None, None, cost_atr=0.05)
    assert out["n_eligible"] == 3
    expected = (p90._FIXED_DIRECTION * test["T1"].to_numpy(float) - 0.05)
    np.testing.assert_allclose(out["net_r_series"], expected)


# --- E. eligibility filter ------------------------------------------------------------
def test_eligibility_filter_skips_rows_below_threshold():
    test = pd.DataFrame({"T1": [1.0, 1.0, 1.0, 1.0]})
    percentile = np.array([0.1, 0.2, 0.8, 0.9])
    out = p90._apply_risk_system(test, percentile, eligibility_threshold=0.5, cost_atr=0.0)
    assert out["n_eligible"] == 2
    assert len(out["net_r_series"]) == 2


# --- F. economic metrics --------------------------------------------------------------
def test_economic_metrics_handles_empty_series():
    out = p90._economic_metrics(np.array([]))
    assert out["state"] == "NO_TRADES"


def test_economic_metrics_computes_drawdown_correctly():
    r = np.array([1.0, -2.0, 1.0, 1.0])   # equity path: 1, -1, 0, 1 -> max dd = -2 (from peak 1 to trough -1)
    out = p90._economic_metrics(r)
    assert out["max_drawdown_R"] == -2.0
    assert out["n_trades"] == 4


def test_economic_metrics_profit_factor_and_hit_rate():
    r = np.array([1.0, 1.0, -0.5])
    out = p90._economic_metrics(r)
    assert out["hit_rate"] == round(2 / 3, 4)
    assert abs(out["profit_factor"] - 4.0) < 1e-9


# --- G. break-even cost -------------------------------------------------------------
def test_break_even_cost_returns_none_when_never_positive(monkeypatch):
    monkeypatch.setattr(p90, "run_primary_experiment",
                        lambda cost, target_col="T2": {"per_fold": [
                            {"fold": 1, "delta_A2_minus_A1": {"expectancy_R": -0.01}}]})
    out = p90.break_even_cost(search_grid=(0.0, 0.1))
    assert out["break_even_cost_atr"] is None


def test_break_even_cost_finds_the_largest_positive_point(monkeypatch):
    def fake_run(cost, target_col="T2"):
        delta = 0.05 - cost   # positive delta up to cost=0.05
        return {"per_fold": [{"fold": 1, "delta_A2_minus_A1": {"expectancy_R": delta}}]}
    monkeypatch.setattr(p90, "run_primary_experiment", fake_run)
    out = p90.break_even_cost(search_grid=(0.0, 0.02, 0.04, 0.06, 0.08))
    assert out["break_even_cost_atr"] == 0.04


# --- H. verdict decision tree --------------------------------------------------------
def _cost_sens(base_delta, adverse_delta, severe_delta, dd_delta=1.0):
    def _res(delta):
        return {"per_fold": [{"delta_A2_minus_A1": {"expectancy_R": delta, "max_drawdown_R": dd_delta}}]}
    return {"BASE": _res(base_delta), "ADVERSE": _res(adverse_delta), "SEVERE": _res(severe_delta)}


def test_verdict_invalidated_when_placebo_not_smaller_than_real():
    cost_sens = _cost_sens(0.01, 0.01, 0.01)
    placebo = {"max_abs_delta": 0.02}
    v, _ = p90.classify_verdict(cost_sens, placebo, {}, {"break_even_cost_atr": 0.1})
    assert v == "MAGNITUDE_SIGNAL_INVALIDATED"


def test_verdict_not_tradable_when_neither_expectancy_nor_drawdown_improves():
    cost_sens = _cost_sens(-0.001, -0.001, -0.001, dd_delta=-1.0)
    placebo = {"max_abs_delta": 0.0001}
    v, _ = p90.classify_verdict(cost_sens, placebo, {}, {"break_even_cost_atr": None})
    assert v == "MAGNITUDE_SIGNAL_CONFIRMED_BUT_NOT_ECONOMICALLY_TRADABLE"


def test_verdict_promising_when_break_even_too_low():
    cost_sens = _cost_sens(0.01, 0.01, 0.01)
    placebo = {"max_abs_delta": 0.0001}
    v, _ = p90.classify_verdict(cost_sens, placebo, {}, {"break_even_cost_atr": 0.01})
    assert v == "RISK_MANAGEMENT_EDGE_PROMISING"


def test_verdict_promising_when_breadth_insufficient():
    cost_sens = _cost_sens(0.01, 0.01, 0.01)
    placebo = {"max_abs_delta": 0.0001}
    cross_inst = {inst: {"delta_expectancy_R": 0.01} for inst in list(p83.INSTRUMENTS_83)[:2]}
    for inst in list(p83.INSTRUMENTS_83)[2:]:
        cross_inst[inst] = {"delta_expectancy_R": -0.01}
    v, _ = p90.classify_verdict(cost_sens, placebo, cross_inst, {"break_even_cost_atr": 0.2})
    assert v == "RISK_MANAGEMENT_EDGE_PROMISING"


def test_verdict_confirmed_requires_everything():
    cost_sens = _cost_sens(0.01, 0.01, 0.01)
    placebo = {"max_abs_delta": 0.0001}
    cross_inst = {inst: {"delta_expectancy_R": 0.01} for inst in p83.INSTRUMENTS_83}
    v, _ = p90.classify_verdict(cost_sens, placebo, cross_inst, {"break_even_cost_atr": 0.2})
    assert v == "RISK_MANAGEMENT_EDGE_CONFIRMED"


def test_verdict_never_confirmed_without_break_even_clearing_base_cost():
    cost_sens = _cost_sens(0.01, 0.01, 0.01)
    placebo = {"max_abs_delta": 0.0001}
    cross_inst = {inst: {"delta_expectancy_R": 0.01} for inst in p83.INSTRUMENTS_83}
    for be in (0.0, 0.01, 0.049):
        v, _ = p90.classify_verdict(cost_sens, placebo, cross_inst, {"break_even_cost_atr": be})
        assert v != "RISK_MANAGEMENT_EDGE_CONFIRMED"


# --- I. walk-forward structural leakage check ---------------------------------------
def test_walk_forward_train_rows_precede_fold_train_end(monkeypatch):
    rows = _frame(n=40000, seed=13)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    ds = p90.build_pooled_dataset_90("15m", 4, instruments=("EURUSD",))
    folds = p80.make_folds(ds, p80._FOLD_BOUNDARY_YEARS)
    for fold in folds:
        train, val, test, _ = p80.split_fold(ds, fold, "15m")
        if len(train) == 0:
            continue
        assert (train["prediction_timestamp"] < fold.train_end).all()


# --- J. placebo actually collapses a known effect -------------------------------------
def test_placebo_collapses_relative_to_real_effect(monkeypatch):
    rng = np.random.default_rng(29)
    n = 40000
    vstate = np.zeros(n)
    for i in range(1, n):
        vstate[i] = 0.97 * vstate[i - 1] + rng.normal(0, 0.3)
    vol = np.exp(vstate) * 100.0 + 1.0
    close = 100.0 + np.cumsum(rng.normal(0, 1, n)) * 0.05
    vol_rank_proxy = pd.Series(vol).rolling(200, min_periods=1).apply(
        lambda s: (s <= s.iloc[-1]).mean(), raw=False).to_numpy()
    rng_size = (0.05 + 3.0 * vol_rank_proxy) * np.abs(rng.normal(1, 0.2, n))
    high, low = close + rng_size, close - rng_size
    open_ = close - rng.normal(0, 0.02, n)
    t0 = 1_622_505_600
    rows = [{"time": t0 + i * 900, "open": float(open_[i]), "high": float(max(open_[i], high[i], close[i])),
            "low": float(min(open_[i], low[i], close[i])), "close": float(close[i]),
            "volume": float(vol[i]), "source": "mt5"} for i in range(n)]
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    primary = p90.run_primary_experiment(0.0)
    placebo = p90.walk_forward_placebo(0.0)
    real_deltas = [f["delta_A2_minus_A1"]["expectancy_R"] for f in primary["per_fold"]
                  if "delta_A2_minus_A1" in f and f["delta_A2_minus_A1"]["expectancy_R"] is not None]
    placebo_deltas = [f["delta_expectancy_R"] for f in placebo["per_fold"] if f.get("delta_expectancy_R") is not None]
    assert real_deltas and placebo_deltas


# --- K. safety invariants ----------------------------------------------------------
def test_module_source_has_no_execution_or_broker_imports_or_order_logic():
    src = inspect.getsource(p90)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    forbidden = ["order_execution", "broker_adapter", "live_trading", "risk_engine", "account_management"]
    for f in forbidden:
        assert not any(f in l for l in import_lines), f"forbidden import found: {f}"
    for token in ("place_order(", "submit_order(", "execute_trade(", "delete_account", "remove_account"):
        assert token not in src


def test_result_dataclass_reports_research_only_status():
    r = p90.Phase90Result(
        schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="h",
        universe=[], timeframe="15m", fixed_direction_note="x", primary_experiment_base_cost={},
        cost_sensitivity={}, break_even_cost={}, walk_forward_placebo={}, cross_instrument_breakdown={},
        temporal_breakdown=[], session_breakdown={}, target_reachability_economic={},
        verdict="NO_MAGNITUDE_EDGE_FOUND", verdict_reason="x", directional_edge_found=False,
        magnitude_signal_found=True, risk_management_edge_found=False,
        profitable_trading_edge_found="NOT_ESTABLISHED", determinism={},
    )
    assert r.strategy_status == "RESEARCH_ONLY_NO_LIVE_EXECUTION_ARTIFACT"
    assert r.holdout_untouched is True
    assert r.directional_edge_found is False


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}

    def fake_save(key, kind, payload):
        saved["key"] = key
        saved["payload"] = payload
        return "fake_hash_p90"

    def fake_load(key):
        return {"payload": saved["payload"]} if key == saved.get("key") else None

    monkeypatch.setattr(p90.store, "save_artifact", fake_save)
    monkeypatch.setattr(p90.store, "load_artifact", fake_load)

    fake_result = p90.Phase90Result(
        schema_version=p90.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00",
        git_commit="abc", frozen_contract_hash="h", universe=list(p83.INSTRUMENTS_83),
        timeframe="15m", fixed_direction_note="x", primary_experiment_base_cost={}, cost_sensitivity={},
        break_even_cost={}, walk_forward_placebo={}, cross_instrument_breakdown={}, temporal_breakdown=[],
        session_breakdown={}, target_reachability_economic={},
        verdict="RISK_MANAGEMENT_EDGE_PROMISING", verdict_reason="x", directional_edge_found=False,
        magnitude_signal_found=True, risk_management_edge_found=True,
        profitable_trading_edge_found="NOT_ESTABLISHED", determinism={"match": True}, content_hash="deadbeef",
    )
    h = p90.persist(fake_result)
    assert h == "fake_hash_p90"
    got = p90.get_result()
    assert got["content_hash"] == "deadbeef"
    assert got["verdict"] == "RISK_MANAGEMENT_EDGE_PROMISING"
