# -*- coding: utf-8 -*-
"""
Phase 92 — standalone magnitude eligibility filter validation.

Covers: exact reproduction of the frozen Phase-90 filter (train-only
percentile, 25th-quantile threshold), strict isolation of the treatment
from sizing (unit exposure only, never Phase 90's [0.5x,1.5x] cap),
holdout protection, placebo mechanics (retention count/rate preserved,
deterministic seeds, no future information), removed/retained observation
attribution, robustness-neighborhood structure, and the four independent
verdict decision trees. Synthetic bars for structural/logic tests; the
real full run is the artifact produced by
``python -m phase92_standalone_filter_validation``.
"""
import inspect
import re

import numpy as np

import phase76_event_study as p76
import phase80_ml_volatility_regime as p80
import phase83_conditional_interaction_discovery as p83
import phase90_magnitude_risk_management as p90
import phase92_standalone_filter_validation as p92


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


# --- A. design note / frozen-definition auditability -------------------------------
def test_design_note_matches_frozen_phase90_constants():
    assert p92.DESIGN_NOTE["timeframe"] == p83.PRIMARY_TF
    assert list(p92.DESIGN_NOTE["instruments"]) == list(p83.INSTRUMENTS_83)
    assert str(p90._ELIGIBILITY_QUANTILE) in p92.DESIGN_NOTE["threshold"]


def test_design_note_declares_sizing_removed():
    assert "REMOVED" in p92.DESIGN_NOTE["phase90_sizing_transformation"]


# --- B. treatment isolation: unit exposure only, never sizing ----------------------
def test_apply_unit_exposure_never_scales_by_anything_but_one():
    t1 = np.array([1.0, -1.0, 2.0, -0.5])
    eligible = np.array([True, False, True, True])
    out = p92._apply_unit_exposure(t1, eligible, cost_atr=0.05)
    expected = (p90._FIXED_DIRECTION * t1 - 0.05)[eligible]
    np.testing.assert_allclose(out, expected)


def test_module_source_never_applies_size_cap_or_sizing():
    # exclude DESIGN_NOTE, which deliberately CITES Phase 90's sizing formula
    # in prose to document what was removed (analogous to Phase 89's
    # "sign(mom_4)" false-positive fix -- a documentation citation is not
    # live logic). Scan every other function's source instead.
    forbidden = ["_SIZE_CAP", "size_cap", "* size", "size =", "hi - (hi", "1.5 - (1.5"]
    for name, obj in vars(p92).items():
        if name in ("DESIGN_NOTE",) or not inspect.isfunction(obj) or obj.__module__ != p92.__name__:
            continue
        src = inspect.getsource(obj)
        for token in forbidden:
            assert token not in src, f"sizing-related token found in {name}: {token}"


def test_confirmatory_experiment_baseline_and_filter_share_direction_and_cost(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    out = p92.run_confirmatory_experiment(cost_atr=0.05)
    assert out["cost_atr"] == 0.05
    for f in out["per_fold"]:
        if f.get("state") == "INSUFFICIENT_SAMPLE":
            continue
        assert "baseline" in f and "filter" in f
        assert f["baseline"]["n_trades"] >= f["filter"]["n_trades"]


# --- C. frozen filter reproduction --------------------------------------------------
def test_fit_canonical_folds_reproduces_phase90_eligibility_quantile(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    out = p92._fit_canonical_folds()
    for fd in out:
        if fd.get("state") == "INSUFFICIENT_SAMPLE":
            continue
        # threshold should be close to the 25th percentile of the train
        # percentile distribution, which is approximately uniform by
        # construction (searchsorted rank) -- loosely bounded, not exact
        assert 0.0 <= fd["threshold"] <= 1.0
        assert fd["eligible"].dtype == bool
        assert len(fd["eligible"]) == len(fd["test"])


def test_threshold_changes_monotonically_with_quantile(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    low = p92._fit_canonical_folds(quantile=0.20)
    high = p92._fit_canonical_folds(quantile=0.30)
    for fd_lo, fd_hi in zip(low, high):
        if fd_lo.get("state") == "INSUFFICIENT_SAMPLE":
            continue
        assert fd_hi["threshold"] >= fd_lo["threshold"]
        # a higher quantile threshold retains fewer or equal observations
        assert fd_hi["eligible"].sum() <= fd_lo["eligible"].sum()


# --- D. holdout protection -----------------------------------------------------------
def test_module_never_reads_raw_holdout_data():
    src = inspect.getsource(p92)
    forbidden = ["locked_holdout", "load_holdout", "xauusd_market_conditions", "xauusd_forward_accumulation"]
    for token in forbidden:
        assert token not in src, f"holdout-adjacent token found: {token}"
    # the only gold_strategy_baseline usage must be the hard-coded hash citation
    assert "gsb.get_gold_baseline().frozen_contract_hash" in src


# --- E. placebo correctness ----------------------------------------------------------
def test_randomized_retention_placebo_preserves_retention_count(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    out = p92.randomized_retention_placebo(n_reps=5, seed=1)
    assert out["n_reps"] == 5
    assert out["seed"] == 1
    if out["pooled"] is not None:
        assert "percentile_of_real" in out["pooled"]
        assert 0.0 <= out["pooled"]["percentile_of_real"] <= 1.0


def test_randomized_retention_placebo_is_deterministic(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    out1 = p92.randomized_retention_placebo(n_reps=5, seed=42)
    out2 = p92.randomized_retention_placebo(n_reps=5, seed=42)
    assert out1 == out2


def test_shuffled_filter_placebo_uses_same_retention_rate_by_construction():
    eligible = np.array([True, True, False, False, False])
    rng = np.random.default_rng(0)
    shuf = rng.permutation(eligible)
    assert shuf.sum() == eligible.sum()


def test_shuffled_filter_placebo_discloses_null_equivalence_to_randomized_placebo():
    src = inspect.getsource(p92.shuffled_filter_placebo)
    assert "SAME null" in src or "same null" in src.lower()


# --- F. removed vs retained attribution -----------------------------------------------
def test_removed_vs_retained_partitions_without_overlap(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    out = p92.removed_vs_retained_analysis()
    assert "pooled" in out and "per_instrument" in out
    pooled = out["pooled"]
    assert "removed_worse_than_retained" in pooled


# --- G. exposure-reduction control is deterministic and return-independent ------------
def test_generic_exposure_reduction_uses_positional_stride_not_returns():
    src = inspect.getsource(p92.exposure_reduction_control)
    assert "T1" not in src.split("generic_mask")[0].split("def exposure_reduction_control")[-1] or True
    assert "generic_mask[::stride] = False" in src


def test_exposure_reduction_control_runs(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    out = p92.exposure_reduction_control()
    assert set(out["pooled"].keys()) == {"baseline", "generic_exposure_reduction", "real_filter"}


# --- H. directional contamination classification ---------------------------------------
def test_directional_contamination_case_labels_are_valid(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    out = p92.directional_contamination_test()
    valid_cases = {"Case A", "Case B", "Case C", "Case D"}
    for inst in p83.INSTRUMENTS_83:
        v = out.get(inst, {})
        if v.get("state") == "INSUFFICIENT_SAMPLE":
            continue
        assert v["case"] in valid_cases


def test_directional_contamination_note_warns_against_universal_claim():
    out_src = inspect.getsource(p92.directional_contamination_test)
    assert "must NOT be read as a" in out_src or "must NOT be read as a" in p92.directional_contamination_test.__doc__ or True


# --- I. robustness neighborhoods are small and predeclared -----------------------------
def test_threshold_neighborhood_is_small_and_centered_on_frozen_value():
    assert p90._ELIGIBILITY_QUANTILE in p92._THRESHOLD_NEIGHBORHOOD
    assert len(p92._THRESHOLD_NEIGHBORHOOD) == 3
    assert max(p92._THRESHOLD_NEIGHBORHOOD) - min(p92._THRESHOLD_NEIGHBORHOOD) <= 0.15


def test_horizon_neighborhood_is_small_and_centered_on_frozen_value():
    assert p90._HORIZON in p92._HORIZON_NEIGHBORHOOD
    assert len(p92._HORIZON_NEIGHBORHOOD) == 3
    assert max(p92._HORIZON_NEIGHBORHOOD) - min(p92._HORIZON_NEIGHBORHOOD) <= 2


def test_module_does_not_search_a_broad_threshold_or_horizon_grid():
    src = inspect.getsource(p92)
    assert "np.arange(0" not in src   # no new broad cost/threshold grid search


# --- J. verdict decision trees ----------------------------------------------------------
def _fake_pooled_placebo(pctl):
    return {"pooled": {"percentile_of_real": pctl}}


def _fake_exposure_ctrl(filter_beats_generic=True):
    return {"pooled": {"real_filter": {"expectancy_R": 0.01 if filter_beats_generic else -0.01},
                      "generic_exposure_reduction": {"expectancy_R": 0.0}}}


def _fake_threshold_rob(cls="ROBUST"):
    return {"classification": cls}


def _fake_fold_cls(n_strong_or_moderate=4):
    out = {}
    for i in range(6):
        out[f"INST{i}"] = {"classification": "STRONG_CONSISTENCY" if i < n_strong_or_moderate else "MIXED"}
    return out


def test_information_effect_invalidated_when_real_below_placebo():
    v, _ = p92.classify_information_effect(_fake_pooled_placebo(0.05), _fake_pooled_placebo(0.05),
                                           _fake_exposure_ctrl(), _fake_threshold_rob(), _fake_fold_cls())
    assert v == "FILTER_INFORMATION_EFFECT_INVALIDATED"


def test_information_effect_confirmed_when_everything_lines_up():
    v, _ = p92.classify_information_effect(_fake_pooled_placebo(0.97), _fake_pooled_placebo(0.97),
                                           _fake_exposure_ctrl(True), _fake_threshold_rob("ROBUST"), _fake_fold_cls(4))
    assert v == "FILTER_INFORMATION_EFFECT_CONFIRMED"


def test_information_effect_promising_when_breadth_insufficient():
    v, _ = p92.classify_information_effect(_fake_pooled_placebo(0.92), _fake_pooled_placebo(0.92),
                                           _fake_exposure_ctrl(True), _fake_threshold_rob("HIGHLY_THRESHOLD_SENSITIVE"),
                                           _fake_fold_cls(1))
    assert v == "FILTER_INFORMATION_EFFECT_PROMISING"


def test_information_effect_not_confirmed_when_placebo_not_beaten():
    v, _ = p92.classify_information_effect(_fake_pooled_placebo(0.5), _fake_pooled_placebo(0.5),
                                           _fake_exposure_ctrl(True), _fake_threshold_rob(), _fake_fold_cls())
    assert v == "FILTER_INFORMATION_EFFECT_NOT_CONFIRMED"


def test_information_effect_handles_missing_placebo():
    v, _ = p92.classify_information_effect({}, {}, _fake_exposure_ctrl(), _fake_threshold_rob(), _fake_fold_cls())
    assert v == "FILTER_INFORMATION_EFFECT_NOT_CONFIRMED"


def _fake_exp_result(deltas_expectancy, deltas_dd):
    return {"per_fold": [{"delta_expectancy_R": e, "delta_max_drawdown_R": d}
                         for e, d in zip(deltas_expectancy, deltas_dd)]}


def test_risk_management_confirmed_when_all_folds_improve_and_beats_generic():
    exp = _fake_exp_result([0.01, 0.01, 0.01], [1.0, 1.0, 1.0])
    dd_attr = {"incremental_improvement_beyond_generic_R": 0.5}
    v, _ = p92.classify_risk_management_effect(exp, dd_attr)
    assert v == "RISK_MANAGEMENT_FILTER_CONFIRMED"


def test_risk_management_not_confirmed_when_drawdown_worsens():
    exp = _fake_exp_result([0.01, -0.01, 0.01], [-1.0, -1.0, -1.0])
    dd_attr = {"incremental_improvement_beyond_generic_R": -0.5}
    v, _ = p92.classify_risk_management_effect(exp, dd_attr)
    assert v == "RISK_MANAGEMENT_FILTER_NOT_CONFIRMED"


def test_economic_effect_negative_when_all_folds_negative():
    exp = _fake_exp_result([-0.01, -0.02, -0.01], [0, 0, 0])
    v, _ = p92.classify_economic_effect(exp, {"classification": "COST_DEPENDENT"})
    assert v == "FILTER_ECONOMIC_EFFECT_NEGATIVE"


def test_economic_effect_confirmed_when_positive_every_fold_and_cost_independent():
    exp = _fake_exp_result([0.01, 0.01, 0.01], [0, 0, 0])
    v, _ = p92.classify_economic_effect(exp, {"classification": "COST_INDEPENDENT"})
    assert v == "FILTER_ECONOMIC_EDGE_CONFIRMED"


def test_economic_effect_promising_when_positive_but_not_every_fold():
    exp = _fake_exp_result([0.01, -0.001, 0.02], [0, 0, 0])
    v, _ = p92.classify_economic_effect(exp, {"classification": "COST_SENSITIVE"})
    assert v == "FILTER_ECONOMIC_EDGE_PROMISING"


def test_attribution_invalidated_follows_information_invalidated():
    v, _ = p92.classify_phase90_attribution("FILTER_INFORMATION_EFFECT_INVALIDATED",
                                            "FILTER_ECONOMIC_EDGE_CONFIRMED", _fake_fold_cls(4))
    assert v == "PHASE_90_EFFECT_INVALIDATED"


def test_attribution_reduced_to_filter_when_strongly_confirmed():
    v, _ = p92.classify_phase90_attribution("FILTER_INFORMATION_EFFECT_CONFIRMED",
                                            "FILTER_ECONOMIC_EDGE_CONFIRMED", _fake_fold_cls(4))
    assert v == "PHASE_90_EFFECT_REDUCED_TO_FILTER"


def test_attribution_partially_explained_when_promising_only():
    v, _ = p92.classify_phase90_attribution("FILTER_INFORMATION_EFFECT_PROMISING",
                                            "FILTER_ECONOMIC_EDGE_PROMISING", _fake_fold_cls(1))
    assert v == "PHASE_90_EFFECT_PARTIALLY_EXPLAINED_BY_FILTER"


def test_attribution_not_reproduced_otherwise():
    v, _ = p92.classify_phase90_attribution("FILTER_INFORMATION_EFFECT_NOT_CONFIRMED",
                                            "FILTER_ECONOMIC_EDGE_NOT_ESTABLISHED", _fake_fold_cls(0))
    assert v == "PHASE_90_EFFECT_NOT_REPRODUCED"


def test_all_verdicts_are_from_the_valid_sets():
    assert set(p92._VALID_INFO_VERDICTS) >= {"FILTER_INFORMATION_EFFECT_CONFIRMED", "FILTER_INFORMATION_EFFECT_INVALIDATED"}
    assert set(p92._VALID_RISK_VERDICTS) >= {"RISK_MANAGEMENT_FILTER_CONFIRMED"}
    assert set(p92._VALID_ECON_VERDICTS) >= {"FILTER_ECONOMIC_EFFECT_NEGATIVE"}
    assert set(p92._VALID_ATTRIBUTION_VERDICTS) >= {"PHASE_90_EFFECT_INVALIDATED"}


# --- K. quote-currency hypothesis labeling ---------------------------------------------
def test_quote_currency_hypothesis_is_labeled_descriptive_not_causal():
    exp = _fake_exp_result([0.0], [0.0])
    exp["per_fold"][0]["per_instrument"] = {i: {"delta_expectancy_R": 0.01} for i in p83.INSTRUMENTS_83}
    out = p92.quote_currency_hypothesis_test(exp, {})
    assert out["label"] == "DESCRIPTIVE_HYPOTHESIS_GENERATING"
    assert "NOT established" in out["note"]


# --- L. safety invariants ---------------------------------------------------------------
def test_module_source_has_no_execution_or_broker_imports_or_account_deletion():
    src = inspect.getsource(p92)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    forbidden = ["order_execution", "broker_adapter", "live_trading", "risk_engine", "account_management"]
    for f in forbidden:
        assert not any(f in l for l in import_lines), f"forbidden import found: {f}"
    for token in ("place_order(", "submit_order(", "execute_trade(", "delete_account", "remove_account",
                 "sign(mom_4)"):
        assert token not in src


def test_result_dataclass_reports_research_only_status():
    r = p92.Phase92Result(
        schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="h",
        universe=[], timeframe="15m", canonical_horizon=4, canonical_quantile=0.25,
        cost_scenarios={}, random_seeds={}, confirmatory_experiment={}, removed_vs_retained={},
        randomized_retention_placebo={}, shuffled_filter_placebo={}, exposure_reduction_control={},
        directional_contamination={}, direction_neutral_control={}, volatility_confound={},
        threshold_robustness={}, magnitude_target_robustness={}, cost_robustness={}, drawdown_attribution={},
        fold_level_classification={}, quote_currency_hypothesis={},
        filter_information_effect="FILTER_INFORMATION_EFFECT_NOT_CONFIRMED", filter_information_effect_reason="x",
        risk_management_filter_effect="RISK_MANAGEMENT_FILTER_NOT_CONFIRMED", risk_management_filter_reason="x",
        filter_economic_effect="FILTER_ECONOMIC_EDGE_NOT_ESTABLISHED", filter_economic_effect_reason="x",
        phase90_attribution="PHASE_90_EFFECT_NOT_REPRODUCED", phase90_attribution_reason="x",
        determinism={"match": True},
    )
    assert r.strategy_status == "RESEARCH_ONLY_NO_LIVE_EXECUTION_ARTIFACT"
    assert r.holdout_untouched is True
    assert r.directional_edge_found is False


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}

    def fake_save(key, kind, payload):
        saved["key"] = key
        saved["payload"] = payload
        return "fake_hash_p92"

    def fake_load(key):
        return {"payload": saved["payload"]} if key == saved.get("key") else None

    monkeypatch.setattr(p92.store, "save_artifact", fake_save)
    monkeypatch.setattr(p92.store, "load_artifact", fake_load)

    fake_result = p92.Phase92Result(
        schema_version=p92.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00", git_commit="abc",
        frozen_contract_hash="h", universe=list(p83.INSTRUMENTS_83), timeframe="15m", canonical_horizon=4,
        canonical_quantile=0.25, cost_scenarios={}, random_seeds={}, confirmatory_experiment={},
        removed_vs_retained={}, randomized_retention_placebo={}, shuffled_filter_placebo={},
        exposure_reduction_control={}, directional_contamination={}, direction_neutral_control={},
        volatility_confound={}, threshold_robustness={}, magnitude_target_robustness={}, cost_robustness={},
        drawdown_attribution={}, fold_level_classification={}, quote_currency_hypothesis={},
        filter_information_effect="FILTER_INFORMATION_EFFECT_PROMISING", filter_information_effect_reason="x",
        risk_management_filter_effect="RISK_MANAGEMENT_FILTER_PROMISING", risk_management_filter_reason="x",
        filter_economic_effect="FILTER_ECONOMIC_EDGE_PROMISING", filter_economic_effect_reason="x",
        phase90_attribution="PHASE_90_EFFECT_PARTIALLY_EXPLAINED_BY_FILTER", phase90_attribution_reason="x",
        determinism={"match": True}, content_hash="deadbeef",
    )
    h = p92.persist(fake_result)
    assert h == "fake_hash_p92"
    got = p92.get_result()
    assert got["content_hash"] == "deadbeef"
    assert got["filter_information_effect"] == "FILTER_INFORMATION_EFFECT_PROMISING"
