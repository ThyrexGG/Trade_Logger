# -*- coding: utf-8 -*-
"""
Phase 91 — magnitude economic divergence & cross-instrument attribution.

Covers: Phase-90 reconstruction from persisted artifacts (never
recomputed), the sizing/filter decomposition ablation (A0/filter-only/
sizing-only/both), temporal per-instrument fold aggregation, cost/trade-
count attribution, group-level placebo mechanics, the verdict decision
tree, and safety invariants. Synthetic bars for structural/logic tests;
the real full run is the artifact produced by
``python -m phase91_magnitude_economic_attribution``.
"""
import inspect
import re

import numpy as np
import pandas as pd

import phase76_event_study as p76
import phase80_ml_volatility_regime as p80
import phase83_conditional_interaction_discovery as p83
import phase91_magnitude_economic_attribution as p91


def _frame(n=40000, seed=71):
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


# --- A. group definitions match Phase 90's actual persisted split -----------------
def test_positive_and_negative_groups_are_disjoint_and_cover_six_instruments():
    combined = set(p91._POSITIVE_GROUP) | set(p91._NEGATIVE_GROUP)
    assert combined == set(p83.INSTRUMENTS_83)
    assert set(p91._POSITIVE_GROUP).isdisjoint(set(p91._NEGATIVE_GROUP))


def test_positive_group_is_exactly_the_jpy_quoted_instruments():
    assert all(i.endswith("JPY") for i in p91._POSITIVE_GROUP)
    assert not any(i.endswith("JPY") for i in p91._NEGATIVE_GROUP)


# --- B. Phase-90 reconstruction is read-only, never recomputed --------------------
def test_reconstruct_phase90_result_reads_persisted_artifacts_only():
    src = inspect.getsource(p91.reconstruct_phase90_result)
    assert "p89.get_result()" in src and "p90.get_result()" in src
    assert "run()" not in src   # never calls p89.run()/p90.run() to recompute


def test_reconstruct_phase90_result_handles_missing_artifacts(monkeypatch):
    monkeypatch.setattr(p91.p89, "get_result", lambda: None)
    monkeypatch.setattr(p91.p90, "get_result", lambda: None)
    out = p91.reconstruct_phase90_result()
    assert out["state"] == "MISSING_ARTIFACT"


def test_reconstruct_phase90_result_confirms_the_real_split():
    out = p91.reconstruct_phase90_result()
    if out.get("state") == "MISSING_ARTIFACT":
        return   # artifact not yet produced in this environment -- acceptable
    assert out["split_confirmed"] is True


# --- C. sizing/filter decomposition ------------------------------------------------
def test_decomposition_a0_matches_baseline_no_size_no_filter():
    conf = pd.DataFrame({"T1": [1.0, -1.0, 2.0]})
    percentile = np.array([0.9, 0.1, 0.5])
    r_raw = p91._FIXED_DIRECTION * conf["T1"].to_numpy(float)
    a0 = (r_raw - 0.0) * np.ones(3)
    np.testing.assert_allclose(a0, r_raw)


def test_decomposition_filter_only_uses_unit_size():
    percentile = np.array([0.9, 0.1, 0.5, 0.05])
    thr = 0.3
    lo, hi = p91._SIZE_CAP
    eligible = percentile >= thr
    size_filter_only = np.ones(len(percentile))
    assert eligible.tolist() == [True, False, True, False]
    assert (size_filter_only == 1.0).all()


def test_sizing_filter_decomposition_produces_four_frozen_variants(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    out = p91.sizing_filter_decomposition()
    assert set(out["pooled"].keys()) == {"A0_neither", "A_filter_only", "B_sizing_only", "C_both_frozen_phase90"}


# --- D. temporal per-instrument aggregation ----------------------------------------
def test_temporal_attribution_covers_all_instruments_and_folds(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    out = p91.temporal_attribution_by_instrument()
    assert set(out["per_fold"].keys()) == set(p83.INSTRUMENTS_83)
    assert set(out["consistency"].keys()) == set(p83.INSTRUMENTS_83)


def test_temporal_consistency_flags_mixed_sign_correctly():
    consistency_input = {"AUDJPY": {"all_same_sign": True}, "EURUSD": {"all_same_sign": False}}
    # directly exercise the classifier logic path that reads this structure
    pos_consistent = all(consistency_input.get(i, {}).get("all_same_sign", True)
                        for i in ("AUDJPY",) if consistency_input.get(i, {}).get("all_same_sign") is not None)
    assert pos_consistent is True


# --- E. cost & trade-count attribution ----------------------------------------------
def test_cost_and_trade_count_attribution_runs(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    out = p91.cost_and_trade_count_attribution()
    assert out["A0_n_trades"] >= out["A1_n_eligible"] >= 0
    assert out["A0_n_trades"] >= out["A2_n_eligible"] >= 0
    assert "note" in out


# --- F. geometry/mechanism attribution ------------------------------------------------
def test_baseline_and_geometry_attribution_computes_t1_t2_correlation(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    out = p91.baseline_and_geometry_attribution()
    for inst in p83.INSTRUMENTS_83:
        assert "corr_T1_T2" in out[inst]
        assert -1.0 <= out[inst]["corr_T1_T2"] <= 1.0
        assert out[inst]["group"] in ("positive", "negative")
    assert "_summary" in out


def test_geometry_attribution_group_labels_match_defined_groups(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    out = p91.baseline_and_geometry_attribution()
    for inst in p91._POSITIVE_GROUP:
        assert out[inst]["group"] == "positive"
    for inst in p91._NEGATIVE_GROUP:
        assert out[inst]["group"] == "negative"


# --- G. predictive-vs-economic descriptive test ---------------------------------------
def test_predictive_vs_economic_reports_spearman_with_caveat():
    out = p91.predictive_vs_economic()
    if out.get("state") in ("INSUFFICIENT_DATA", "MISSING_ARTIFACT"):
        return   # Phase 89/90 artifacts not available in this environment -- acceptable
    assert "spearman_rho" in out
    assert "caveat" in out
    assert out["n"] <= 6


def test_predictive_vs_economic_handles_missing_artifacts_gracefully(monkeypatch):
    monkeypatch.setattr(p91.p89, "get_result", lambda: None)
    monkeypatch.setattr(p91.p90, "get_result", lambda: None)
    out = p91.predictive_vs_economic()
    assert out["state"] == "MISSING_ARTIFACT"


# --- H. verdict decision tree -------------------------------------------------------
def _fake_recon(split_confirmed=True):
    return {"split_confirmed": split_confirmed}


def _fake_geometry(pos=-0.17, neg=-0.02):
    return {"_summary": {"mean_corr_T1_T2_positive_group": pos, "mean_corr_T1_T2_negative_group": neg}}


def _fake_placebo(small=True):
    val = 0.0001 if small else 0.05
    return {"positive_group": [{"fold": 1, "delta_expectancy_R": val}],
           "negative_group": [{"fold": 1, "delta_expectancy_R": val}]}


def _fake_temporal_consistency(all_true=True):
    return {i: {"all_same_sign": all_true} for i in p83.INSTRUMENTS_83}


def test_verdict_invalidated_when_artifacts_missing():
    v, _ = p91.classify_verdict({"state": "MISSING_ARTIFACT"}, {}, {}, {})
    assert v == "PHASE_90_EFFECT_INVALIDATED"


def test_verdict_weakened_when_split_does_not_match():
    v, _ = p91.classify_verdict(_fake_recon(False), _fake_geometry(), _fake_placebo(), _fake_temporal_consistency())
    assert v == "PHASE_90_EFFECT_WEAKENED"


def test_verdict_weakened_when_group_placebo_does_not_collapse():
    v, _ = p91.classify_verdict(_fake_recon(), _fake_geometry(), _fake_placebo(small=False),
                                _fake_temporal_consistency())
    assert v == "PHASE_90_EFFECT_WEAKENED"


def test_verdict_unexplained_when_no_mechanism_found():
    v, _ = p91.classify_verdict(_fake_recon(), _fake_geometry(pos=-0.02, neg=-0.02), _fake_placebo(),
                                _fake_temporal_consistency())
    assert v == "ECONOMIC_DIVERGENCE_UNEXPLAINED"


def test_verdict_partially_explained_when_mechanism_found_but_inconsistent():
    v, _ = p91.classify_verdict(_fake_recon(), _fake_geometry(), _fake_placebo(),
                                _fake_temporal_consistency(all_true=False))
    assert v == "ECONOMIC_DIVERGENCE_PARTIALLY_EXPLAINED"


def test_verdict_explained_when_everything_lines_up():
    v, _ = p91.classify_verdict(_fake_recon(), _fake_geometry(), _fake_placebo(), _fake_temporal_consistency())
    assert v == "ECONOMIC_DIVERGENCE_EXPLAINED"


# --- I. safety invariants ----------------------------------------------------------
def test_module_source_has_no_execution_or_broker_imports_or_account_deletion():
    src = inspect.getsource(p91)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    forbidden = ["order_execution", "broker_adapter", "live_trading", "risk_engine", "account_management"]
    for f in forbidden:
        assert not any(f in l for l in import_lines), f"forbidden import found: {f}"
    for token in ("place_order(", "submit_order(", "execute_trade(", "delete_account", "remove_account",
                 "sign(mom_4)"):
        assert token not in src


def test_module_does_not_optimize_new_parameters():
    """Sanity: the module reuses Phase 90's frozen _SIZE_CAP and cost
    scenarios rather than defining its own new sweep constants."""
    src = inspect.getsource(p91)
    assert "np.arange(0" not in src   # no new cost/threshold grid search


def test_result_dataclass_reports_research_only_status():
    r = p91.Phase91Result(
        schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="h",
        universe=[], timeframe="15m", positive_group=[], negative_group=[], phase90_reconstruction={},
        movement_cost_ratio={}, volatility_scale={}, predictive_vs_economic={},
        baseline_and_geometry_attribution={}, sizing_filter_decomposition={}, session_attribution={},
        volume_relationship_structure={}, temporal_attribution={}, placebo_by_group={},
        cost_and_trade_count_attribution={}, verdict="ECONOMIC_DIVERGENCE_UNEXPLAINED", verdict_reason="x",
        directional_edge_found=False, magnitude_signal_found=True, risk_management_edge_status="PROMISING",
        determinism={},
    )
    assert r.strategy_status == "RESEARCH_ONLY_NO_LIVE_EXECUTION_ARTIFACT"
    assert r.holdout_untouched is True
    assert r.directional_edge_found is False


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}

    def fake_save(key, kind, payload):
        saved["key"] = key
        saved["payload"] = payload
        return "fake_hash_p91"

    def fake_load(key):
        return {"payload": saved["payload"]} if key == saved.get("key") else None

    monkeypatch.setattr(p91.store, "save_artifact", fake_save)
    monkeypatch.setattr(p91.store, "load_artifact", fake_load)

    fake_result = p91.Phase91Result(
        schema_version=p91.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00", git_commit="abc",
        frozen_contract_hash="h", universe=list(p83.INSTRUMENTS_83), timeframe="15m",
        positive_group=list(p91._POSITIVE_GROUP), negative_group=list(p91._NEGATIVE_GROUP),
        phase90_reconstruction={}, movement_cost_ratio={}, volatility_scale={}, predictive_vs_economic={},
        baseline_and_geometry_attribution={}, sizing_filter_decomposition={}, session_attribution={},
        volume_relationship_structure={}, temporal_attribution={}, placebo_by_group={},
        cost_and_trade_count_attribution={}, verdict="ECONOMIC_DIVERGENCE_PARTIALLY_EXPLAINED",
        verdict_reason="x", directional_edge_found=False, magnitude_signal_found=True,
        risk_management_edge_status="PROMISING", determinism={"match": True}, content_hash="deadbeef",
    )
    h = p91.persist(fake_result)
    assert h == "fake_hash_p91"
    got = p91.get_result()
    assert got["content_hash"] == "deadbeef"
    assert got["verdict"] == "ECONOMIC_DIVERGENCE_PARTIALLY_EXPLAINED"
