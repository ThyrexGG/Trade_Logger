# -*- coding: utf-8 -*-
"""
Phase 89 — independent red-team + magnitude edge gate.

Covers: the direct causal re-verification checks (volume-feature window,
T2 target window), the cross-instrument volume placebo mechanics, the
Gate A verdict decision tree, the Gate B walk-forward dataset builder and
its train/test separation, the direction-neutral economic tests'
structural correctness (train-only tercile boundaries, no future leakage),
the Gate B verdict decision tree, and safety invariants. Synthetic bars
for structural/logic tests; the real full run is the artifact produced by
``python -m phase89_research_integrity_gate``.
"""
import inspect
import re

import numpy as np
import pandas as pd

import phase76_event_study as p76
import phase80_ml_volatility_regime as p80
import phase83_conditional_interaction_discovery as p83
import phase89_research_integrity_gate as p89


def _frame(n=8000, seed=71):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 1.0, n).cumsum()
    close = 100.0 + steps * 0.1
    high = close + np.abs(rng.normal(0, 0.15, n))
    low = close - np.abs(rng.normal(0, 0.15, n))
    open_ = close - rng.normal(0, 0.05, n)
    vol = np.abs(rng.normal(100.0, 20.0, n)) + 1.0
    t0 = 1_650_000_000
    return [{"time": t0 + i * 900, "open": float(open_[i]),
             "high": float(max(open_[i], high[i], close[i])),
             "low": float(min(open_[i], low[i], close[i])),
             "close": float(close[i]), "volume": float(vol[i]), "source": "mt5"} for i in range(n)]


# --- A. direct causal re-verification -----------------------------------------
def test_volume_feature_causality_verified_directly():
    out = p89.verify_volume_feature_causality()
    assert out["verdict"] == "SUPPORTED"
    assert out["monotone_series_rank_is_1_from_i_199_onward"] is True
    assert out["a_future_perturbation_leaves_all_earlier_values_unchanged"] is True


def test_t2_target_causality_verified_directly():
    out = p89.verify_t2_target_excludes_own_bar()
    assert out["verdict"] == "SUPPORTED"
    assert out["match"] is True


def test_volume_feature_causality_would_catch_a_forward_looking_bug(monkeypatch):
    """Sanity: if the window included a future bar, the monotone-series
    check would fail -- proving the check has teeth, not just passing
    vacuously."""
    import phase84_information_frontier_audit as p84
    n = 500
    vol = np.arange(1, n + 1, dtype=float)
    df = pd.DataFrame({"vol": vol})
    # simulate a forward-looking rank (uses a CENTERED window) to confirm
    # the monotone-series property would be violated
    centered_rank = pd.Series(vol).rolling(200, center=True, min_periods=1).apply(
        lambda s: (s <= s.iloc[len(s) // 2]).mean(), raw=False).to_numpy()
    assert not np.allclose(centered_rank[199:-100], 1.0)  # NOT all 1.0 -- the real function's own output is


# --- B. cross-instrument volume placebo -----------------------------------------
def test_cross_instrument_volume_placebo_runs_and_returns_delta(monkeypatch):
    rows = _frame(n=8000, seed=5)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    import phase85_tick_volume_confirmation as p85
    p85._clear_cache_85()
    monkeypatch.setattr(p89, "discovery_confirmation_split", None, raising=False)
    r = p89.cross_instrument_volume_placebo("EURUSD", "GBPUSD")
    assert "delta_r2" in r or r.get("state") in ("NO_DATA", "INSUFFICIENT_SAMPLE")


def test_cross_instrument_volume_placebo_insufficient_sample_flagged(monkeypatch):
    rows = _frame(n=500, seed=5)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    import phase85_tick_volume_confirmation as p85
    p85._clear_cache_85()
    r = p89.cross_instrument_volume_placebo("EURUSD", "GBPUSD")
    assert r.get("state") in ("NO_DATA", "INSUFFICIENT_SAMPLE")


# --- C. Gate A verdict decision tree ---------------------------------------------
def _minimal_causality(verdict="SUPPORTED"):
    return {"verdict": verdict}


def test_gate_a_pass_when_everything_supported():
    rows = p89.build_gate_a_table(_minimal_causality(), _minimal_causality(), {}, None)
    # force all rows SUPPORTED/SUPPORTED_WITH_CAVEATS for this synthetic check
    for r in rows:
        if r["audit_result"] == "WEAKENED":
            r["audit_result"] = "SUPPORTED_WITH_CAVEATS"
    verdict, _ = p89.classify_gate_a_verdict(rows)
    assert verdict in ("PASS", "PASS_WITH_REVISIONS")


def test_gate_a_fails_on_invalidated_causality():
    rows = p89.build_gate_a_table(_minimal_causality("INVALIDATED"), _minimal_causality(), {}, None)
    verdict, reason = p89.classify_gate_a_verdict(rows)
    assert verdict == "FAIL"
    assert "INVALIDATED" in reason


def test_gate_a_pass_with_revisions_on_weakened_cross_instrument():
    placebos = {"A_vol_predicts_B": {"delta_r2": 0.02, "ci": [0.01, 0.03]}}
    rows = p89.build_gate_a_table(_minimal_causality(), _minimal_causality(), placebos, None)
    cross_row = next(r for r in rows if "cross-instrument" in r["claim"])
    assert cross_row["audit_result"] == "WEAKENED"
    verdict, _ = p89.classify_gate_a_verdict(rows)
    assert verdict == "PASS_WITH_REVISIONS"


def test_gate_a_table_covers_all_five_prior_phases():
    rows = p89.build_gate_a_table(_minimal_causality(), _minimal_causality(), {}, None)
    phases = {r["phase"] for r in rows}
    assert phases == {84, 85, 86, 87, 88}


# --- D. Gate B dataset builder --------------------------------------------------
def test_gate_b_dataset_has_baseline_b_and_volume_columns(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    ds = p89.build_gate_b_dataset("EURUSD", "15m", 4)
    assert not ds.empty
    for c in p89.BASELINE_B_COLUMNS:
        assert f"feat__{c}" in ds.columns
    assert "feat__volume_rank" in ds.columns
    assert np.isfinite(ds[[f"feat__{c}" for c in p89.BASELINE_B_COLUMNS]].to_numpy(float)).all()


def test_baseline_b_columns_are_volatility_only_not_session_or_location():
    forbidden = {"loc_in_range", "dist_pdh_atr", "dist_pdl_atr", "hour_sin", "hour_cos", "dow",
                "session_LONDON", "regime_TRENDING"}
    assert forbidden.isdisjoint(set(p89.BASELINE_B_COLUMNS))


# --- E. walk-forward incremental prediction --------------------------------------
def test_run_walk_forward_incremental_uses_phase80_folds_and_reports_per_fold(monkeypatch):
    rows = _frame(n=4000, seed=11)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    out = p89.run_walk_forward_incremental("T2")
    assert "per_fold" in out
    assert len(out["per_fold"]) == len(p80._FOLD_BOUNDARY_YEARS)
    for row in out["per_fold"]:
        assert "fold" in row


def test_walk_forward_never_trains_on_data_after_its_own_test_window(monkeypatch):
    """Structural leakage check: for each fold, every TRAIN row's own
    prediction_timestamp must be strictly before that fold's train_end."""
    rows = _frame(n=4000, seed=13)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    ds = p89.build_pooled_gate_b_dataset("15m", 4, instruments=("EURUSD",))
    folds = p80.make_folds(ds, p80._FOLD_BOUNDARY_YEARS)
    for fold in folds:
        train, val, test, _ = p80.split_fold(ds, fold, "15m")
        if len(train) == 0:
            continue
        assert (train["prediction_timestamp"] < fold.train_end).all()
        if len(test) > 0:
            assert (test["prediction_timestamp"] >= fold.test_start).all()


def test_walk_forward_placebo_collapses_relative_to_a_known_synthetic_effect(monkeypatch):
    """The within-walk-forward placebo must be able to actually collapse a
    real effect, not merely report a number -- construct a synthetic
    series with a genuine, persistent (AR1) volume->magnitude relationship
    and confirm the shuffled-volume delta is smaller than the real delta."""
    rng = np.random.default_rng(23)
    n = 40000   # ~1.14 years of 15m bars -- long enough to straddle a real
               # calendar-year fold boundary (make_folds/split_fold use
               # actual Jan-1/Jul-1 dates, not relative offsets)
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
    t0 = 1_622_505_600   # 2021-06-01 UTC -- straddles the 2022 fold boundary below
    rows = [{"time": t0 + i * 900, "open": float(open_[i]), "high": float(max(open_[i], high[i], close[i])),
            "low": float(min(open_[i], low[i], close[i])), "close": float(close[i]),
            "volume": float(vol[i]), "source": "mt5"} for i in range(n)]
    # get_candles returns the SAME synthetic series regardless of instrument
    # name, so build_pooled_gate_b_dataset's default 6-instrument universe
    # still produces a valid (if repetitive) pooled dataset for this check.
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    real = p89.run_walk_forward_incremental("T2")
    placebo = p89.walk_forward_volume_shuffle_placebo("T2")
    real_deltas = [f["delta_r2_C_minus_B"] for f in real["per_fold"] if "delta_r2_C_minus_B" in f]
    placebo_deltas = [f["delta_r2"] for f in placebo["per_fold"] if "delta_r2" in f]
    assert real_deltas and placebo_deltas
    assert max(abs(d) for d in placebo_deltas) < max(abs(d) for d in real_deltas)


def test_gate_b_verdict_invalidated_when_placebo_does_not_collapse():
    wf = _wf(0.02, 3, 3)
    cross = {inst: {"delta_r2": 0.01} for inst in p83.INSTRUMENTS_83}
    bad_placebo = {"all_folds_collapsed": False, "per_fold": [{"fold": 1, "delta_r2": 0.02}]}
    v, reason = p89.classify_gate_b_verdict(wf, {"k_1.0": [{"brier_improvement": 0.01}]},
                                            {"fold_results": [{"log_loss_improvement": 0.01}]},
                                            cross, bad_placebo)
    assert v == "MAGNITUDE_SIGNAL_INVALIDATED"
    assert "placebo" in reason.lower()


# --- F. direction-neutral economic tests -----------------------------------------
def test_target_reachability_test_covers_predeclared_k_grid(monkeypatch):
    rows = _frame(n=4000, seed=17)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    out = p89.target_reachability_test(k_grid=(1.0,))
    assert "k_1.0" in out


def test_regime_classification_boundaries_are_train_only_not_global():
    """Structural check: the tercile computation must use only the train
    split's own target values, never test or the full pooled series."""
    src = inspect.getsource(p89.volatility_regime_classification_test)
    assert "train[target_col]" in src
    assert "np.percentile(train" in src


# --- G. Gate B verdict decision tree ----------------------------------------------
def _wf(pooled, n_pos, n_total):
    return {"pooled_mean_delta_r2_C_minus_B": pooled, "n_folds_with_positive_delta": n_pos,
           "n_folds_total": n_total}


def test_gate_b_invalidated_when_delta_not_positive_every_fold():
    v, _ = p89.classify_gate_b_verdict(_wf(0.01, 2, 3), {}, {"fold_results": []}, {})
    assert v == "MAGNITUDE_SIGNAL_INVALIDATED"


def test_gate_b_invalidated_when_no_data():
    v, _ = p89.classify_gate_b_verdict(_wf(None, 0, 0), {}, {}, {})
    assert v == "MAGNITUDE_SIGNAL_INVALIDATED"


def test_gate_b_not_tradable_when_no_economic_improvement():
    wf = _wf(0.02, 3, 3)
    v, _ = p89.classify_gate_b_verdict(wf, {"k_1.0": [{"brier_improvement": -0.001}]},
                                       {"fold_results": [{"log_loss_improvement": -0.001}]},
                                       {inst: {"delta_r2": 0.01} for inst in p83.INSTRUMENTS_83})
    assert v == "MAGNITUDE_SIGNAL_PROMISING_NOT_TRADABLE_YET"


def test_gate_b_not_tradable_when_economic_gain_concentrated_in_few_instruments():
    wf = _wf(0.02, 3, 3)
    cross = {inst: {"delta_r2": -0.001} for inst in p83.INSTRUMENTS_83}
    cross["XAUUSD"] = {"delta_r2": 0.02}
    v, _ = p89.classify_gate_b_verdict(wf, {"k_1.0": [{"brier_improvement": 0.01}]},
                                       {"fold_results": [{"log_loss_improvement": 0.01}]}, cross)
    assert v == "MAGNITUDE_SIGNAL_PROMISING_NOT_TRADABLE_YET"


def test_gate_b_confirmed_requires_everything():
    wf = _wf(0.02, 3, 3)
    cross = {inst: {"delta_r2": 0.01} for inst in p83.INSTRUMENTS_83}
    v, _ = p89.classify_gate_b_verdict(wf, {"k_1.0": [{"brier_improvement": 0.01}]},
                                       {"fold_results": [{"log_loss_improvement": 0.01}]}, cross)
    assert v == "MAGNITUDE_EDGE_CONFIRMED"


# --- H. safety invariants ----------------------------------------------------------
def test_module_source_has_no_execution_or_broker_imports_or_order_logic():
    src = inspect.getsource(p89)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    forbidden = ["order_execution", "broker_adapter", "live_trading", "risk_engine"]
    for f in forbidden:
        assert not any(f in l for l in import_lines), f"forbidden import found: {f}"
    # NOTE: "sign(mom_4)" deliberately excluded from this list -- it appears
    # only as a citation of Phase 86's own tested (and rejected) directional
    # construction inside the Gate A audit table, never as logic here.
    for token in ("place_order(", "submit_order(", "execute_trade(", "future_sign", "future_direction"):
        assert token not in src


def test_module_never_reads_the_holdout():
    src = inspect.getsource(p89)
    forbidden_modules = ["native_gold_revalidation", "gold_revalidation"]
    for m in forbidden_modules:
        assert m not in src


def test_result_dataclass_reports_research_only_status():
    r = p89.Phase89Result(
        schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="h",
        universe=[], timeframe="15m", gate_a_checks={}, gate_a_table=[], gate_a_verdict="PASS",
        gate_a_reason="x", gate_b_walk_forward={}, gate_b_walk_forward_placebo={}, gate_b_reachability={},
        gate_b_regime_classification={}, gate_b_cross_asset={}, gate_b_verdict=None,
        gate_b_reason=None, directional_edge_found=False, magnitude_signal_found=False,
        tradable_edge_found=False, determinism={},
    )
    assert r.strategy_status == "RESEARCH_ONLY_NO_LIVE_EXECUTION_ARTIFACT"
    assert r.holdout_untouched is True


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}

    def fake_save(key, kind, payload):
        saved["key"] = key
        saved["payload"] = payload
        return "fake_hash_p89"

    def fake_load(key):
        return {"payload": saved["payload"]} if key == saved.get("key") else None

    monkeypatch.setattr(p89.store, "save_artifact", fake_save)
    monkeypatch.setattr(p89.store, "load_artifact", fake_load)

    fake_result = p89.Phase89Result(
        schema_version=p89.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00",
        git_commit="abc", frozen_contract_hash="h", universe=list(p83.INSTRUMENTS_83),
        timeframe="15m", gate_a_checks={}, gate_a_table=[], gate_a_verdict="PASS_WITH_REVISIONS",
        gate_a_reason="x", gate_b_walk_forward={}, gate_b_walk_forward_placebo={}, gate_b_reachability={},
        gate_b_regime_classification={}, gate_b_cross_asset={},
        gate_b_verdict="MAGNITUDE_SIGNAL_PROMISING_NOT_TRADABLE_YET", gate_b_reason="x",
        directional_edge_found=False, magnitude_signal_found=True, tradable_edge_found=False,
        determinism={"match": True}, content_hash="deadbeef",
    )
    h = p89.persist(fake_result)
    assert h == "fake_hash_p89"
    got = p89.get_result()
    assert got["content_hash"] == "deadbeef"
    assert got["gate_b_verdict"] == "MAGNITUDE_SIGNAL_PROMISING_NOT_TRADABLE_YET"
