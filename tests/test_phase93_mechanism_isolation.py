# -*- coding: utf-8 -*-
"""
Phase 93 — magnitude / volatility / volume mechanism isolation.

Covers: the magnitude/volatility/volume feature decomposition (partition
of Phase 89's frozen Baseline B, disjoint, exhaustive), treatment
definitions (each contains exactly the intended columns, canonical == full
== Phase 90/92 frozen filter, magnitude+volatility == Baseline B),
canonical Phase-92 reproduction anchor, equal-retention property, the
placebo/directional/fold helpers operating on pre-fitted fold data, the
minimum-sufficient-mechanism decision procedure, the six verdict decision
trees, holdout protection, and safety invariants. Synthetic bars for
structural/logic tests; the real run is the artifact produced by
``python -m phase93_mechanism_isolation``.
"""
import inspect
import re

import numpy as np

import phase76_event_study as p76
import phase80_ml_volatility_regime as p80
import phase83_conditional_interaction_discovery as p83
import phase89_research_integrity_gate as p89
import phase90_magnitude_risk_management as p90
import phase92_standalone_filter_validation as p92
import phase93_mechanism_isolation as p93


def _frame(n=40000, seed=71):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0, 1.0, n).cumsum()
    close = 100.0 + steps * 0.1
    high = close + np.abs(rng.normal(0, 0.15, n))
    low = close - np.abs(rng.normal(0, 0.15, n))
    open_ = close - rng.normal(0, 0.05, n)
    vol = np.abs(rng.normal(100.0, 20.0, n)) + 1.0
    t0 = 1_622_505_600
    return [{"time": t0 + i * 900, "open": float(open_[i]),
             "high": float(max(open_[i], high[i], close[i])),
             "low": float(min(open_[i], low[i], close[i])),
             "close": float(close[i]), "volume": float(vol[i]), "source": "mt5"} for i in range(n)]


# --- A. feature decomposition -------------------------------------------------------
def test_magnitude_and_volatility_features_partition_baseline_b_exactly():
    combined = set(p93.MAGNITUDE_FEATURES) | set(p93.VOLATILITY_FEATURES)
    assert combined == set(p89.BASELINE_B_COLUMNS)
    assert set(p93.MAGNITUDE_FEATURES).isdisjoint(set(p93.VOLATILITY_FEATURES))
    assert p93.VOLUME_FEATURES == ("volume_rank",)


def test_volatility_features_are_the_rank_transformed_ones():
    assert set(p93.VOLATILITY_FEATURES) == {"atr_rank", "rv_rank"}
    assert not any("rank" in f for f in p93.MAGNITUDE_FEATURES)


# --- B. treatment definitions ------------------------------------------------------
def test_canonical_equals_full_equals_phase90_frozen_filter():
    assert set(p93.TREATMENTS["T1_canonical"]) == set(p93.TREATMENTS["T7_full"])
    assert set(p93.TREATMENTS["T1_canonical"]) == set(p89.BASELINE_B_COLUMNS) | {"volume_rank"}


def test_magnitude_plus_volatility_equals_baseline_b():
    assert set(p93.TREATMENTS["T6_magnitude_plus_volatility"]) == set(p89.BASELINE_B_COLUMNS)
    assert "volume_rank" not in p93.TREATMENTS["T6_magnitude_plus_volatility"]


def test_magnitude_only_excludes_volume_and_volatility_ranks():
    feats = set(p93.TREATMENTS["T2_magnitude_only"])
    assert "volume_rank" not in feats
    assert "atr_rank" not in feats and "rv_rank" not in feats


def test_volatility_only_excludes_volume_and_raw_magnitude():
    feats = set(p93.TREATMENTS["T3_volatility_only"])
    assert "volume_rank" not in feats
    assert feats == {"atr_rank", "rv_rank"}


def test_volume_only_is_just_volume_rank():
    assert p93.TREATMENTS["T4_volume_only"] == ("volume_rank",)


def test_baseline_treatment_has_no_features():
    assert p93.TREATMENTS["T0_baseline"] is None


# --- C. canonical reproduction anchor ---------------------------------------------
def test_verify_canonical_reproduction_flags_discrepancy(monkeypatch):
    fake_p92 = {"confirmatory_experiment": {"per_fold": [
        {"fold": 1, "delta_expectancy_R": 0.999}, {"fold": 2, "delta_expectancy_R": 0.999},
        {"fold": 3, "delta_expectancy_R": 0.999}]}}
    monkeypatch.setattr(p93.p92, "get_result", lambda: fake_p92)
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    out = p93.verify_canonical_reproduction()
    assert out["state"] == "MATERIAL_DISCREPANCY"


def test_verify_canonical_reproduction_handles_missing_phase92(monkeypatch):
    monkeypatch.setattr(p93.p92, "get_result", lambda: None)
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    out = p93.verify_canonical_reproduction()
    assert out["state"] == "MISSING_PHASE92_ARTIFACT"


# --- D. fold fitting + equal retention -------------------------------------------
def test_fit_treatment_folds_produces_eligible_mask_matching_test_length(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    out = p93._fit_treatment_folds(p93.MAGNITUDE_FEATURES)
    for fd in out:
        if fd.get("state") == "INSUFFICIENT_SAMPLE":
            continue
        assert fd["eligible"].dtype == bool
        assert len(fd["eligible"]) == len(fd["test"])
        # retention should be roughly 1 - quantile by construction
        retention = fd["eligible"].mean()
        assert 0.55 <= retention <= 0.9


def test_all_info_treatments_have_similar_retention(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    retentions = []
    for name in p93._INFO_TREATMENTS:
        folds = p93._fit_treatment_folds(p93.TREATMENTS[name])
        for fd in folds:
            if fd.get("state") != "INSUFFICIENT_SAMPLE":
                retentions.append(fd["eligible"].mean())
    assert retentions
    # equal-retention property: spread across all treatments/folds stays tight
    assert max(retentions) - min(retentions) < 0.25


# --- E. treatment isolation: unit exposure, no sizing ------------------------------
def test_confirmatory_from_folds_uses_unit_exposure_only():
    src = inspect.getsource(p93._confirmatory_from_folds)
    assert "_apply_unit_exposure" in src
    for token in ("_SIZE_CAP", "* size", "size =", "hi - (hi"):
        assert token not in src


def test_module_never_applies_sizing():
    for name, obj in vars(p93).items():
        if name == "DESIGN_NOTE" or not inspect.isfunction(obj) or obj.__module__ != p93.__name__:
            continue
        src = inspect.getsource(obj)
        for token in ("_SIZE_CAP", "size_cap", "* size", "1.5 - (1.5"):
            assert token not in src, f"sizing token in {name}: {token}"


# --- F. placebo helpers ----------------------------------------------------------
def test_randomized_placebo_from_folds_deterministic_and_preserves_count(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    folds = p93._fit_treatment_folds(p93.MAGNITUDE_FEATURES)
    a = p93._randomized_placebo_from_folds(folds, n_reps=5, seed=7)
    b = p93._randomized_placebo_from_folds(folds, n_reps=5, seed=7)
    assert a == b
    if a["pooled"] is not None:
        assert 0.0 <= a["pooled"]["percentile_of_real"] <= 1.0


def test_generic_exposure_control_uses_positional_stride():
    src = inspect.getsource(p93._generic_exposure_control_from_folds)
    assert "generic_mask[::stride] = False" in src


# --- G. directional contamination ------------------------------------------------
def test_directional_contamination_case_labels_valid(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p80, "_FOLD_BOUNDARY_YEARS", (2022,))
    folds = p93._fit_treatment_folds(p93.TREATMENTS["T1_canonical"])
    out = p93._directional_contamination_from_folds(folds)
    for inst in p83.INSTRUMENTS_83:
        v = out.get(inst, {})
        if v.get("state") == "INSUFFICIENT_SAMPLE":
            continue
        assert v["case"] in {"Case A", "Case B", "Case C", "Case D"}


# --- H. minimum sufficient mechanism decision procedure ---------------------------
def _fake_core_table(pooled):
    return {"pooled": pooled, "per_instrument": {i: dict(pooled) for i in p83.INSTRUMENTS_83}}


def _fake_placebo(percentiles, generic_beats=False):
    out = {}
    for name, pctl in percentiles.items():
        out[name] = {"randomized_retention": {"pooled": {"percentile_of_real": pctl}},
                    "generic_exposure_reduction": {
                        "baseline": {"expectancy_R": -0.05},
                        "generic_exposure_reduction": {"expectancy_R": -0.049 if not generic_beats else -0.03},
                        "real_filter": {"expectancy_R": -0.03, "max_drawdown_R": -100}}}
    return out


def test_minimum_mechanism_scenario_b_volatility_only():
    core = _fake_core_table({"T1_canonical": 0.02, "T3_volatility_only": 0.019, "T2_magnitude_only": 0.005,
                            "T6_magnitude_plus_volatility": 0.02, "T5_magnitude_plus_volume": 0.02, "T7_full": 0.02})
    placebo = _fake_placebo({"T1_canonical": 0.99, "T3_volatility_only": 0.97, "T2_magnitude_only": 0.6,
                            "T6_magnitude_plus_volatility": 0.99, "T5_magnitude_plus_volume": 0.99, "T7_full": 0.99})
    out = p93.determine_minimum_sufficient_mechanism(core, placebo)
    assert out["minimum_level"] == "T3_volatility_only"
    assert "Scenario B" in out["scenario"]


def test_minimum_mechanism_scenario_a_magnitude_only():
    core = _fake_core_table({"T1_canonical": 0.02, "T3_volatility_only": 0.003, "T2_magnitude_only": 0.018,
                            "T6_magnitude_plus_volatility": 0.02, "T5_magnitude_plus_volume": 0.02, "T7_full": 0.02})
    placebo = _fake_placebo({"T1_canonical": 0.99, "T3_volatility_only": 0.55, "T2_magnitude_only": 0.96,
                            "T6_magnitude_plus_volatility": 0.99, "T5_magnitude_plus_volume": 0.99, "T7_full": 0.99})
    out = p93.determine_minimum_sufficient_mechanism(core, placebo)
    assert out["minimum_level"] == "T2_magnitude_only"
    assert "Scenario A" in out["scenario"]


def test_minimum_mechanism_scenario_d_volume_adds_value():
    core = _fake_core_table({"T1_canonical": 0.02, "T3_volatility_only": 0.005, "T2_magnitude_only": 0.006,
                            "T6_magnitude_plus_volatility": 0.01, "T5_magnitude_plus_volume": 0.018, "T7_full": 0.02})
    placebo = _fake_placebo({"T1_canonical": 0.99, "T3_volatility_only": 0.5, "T2_magnitude_only": 0.55,
                            "T6_magnitude_plus_volatility": 0.7, "T5_magnitude_plus_volume": 0.95, "T7_full": 0.99})
    out = p93.determine_minimum_sufficient_mechanism(core, placebo)
    assert out["minimum_level"] == "T5_magnitude_plus_volume"
    assert "Scenario D" in out["scenario"]


def test_minimum_mechanism_scenario_f_nothing_survives():
    core = _fake_core_table({"T1_canonical": 0.02, "T3_volatility_only": 0.001, "T2_magnitude_only": 0.001,
                            "T6_magnitude_plus_volatility": 0.001, "T5_magnitude_plus_volume": 0.001, "T7_full": 0.02})
    placebo = _fake_placebo({"T1_canonical": 0.4, "T3_volatility_only": 0.4, "T2_magnitude_only": 0.4,
                            "T6_magnitude_plus_volatility": 0.4, "T5_magnitude_plus_volume": 0.4, "T7_full": 0.4})
    out = p93.determine_minimum_sufficient_mechanism(core, placebo)
    assert out["minimum_level"] == "NONE"
    assert "Scenario F" in out["scenario"]


# --- I. verdict decision trees --------------------------------------------------
def test_magnitude_verdict_reduced_to_volatility():
    core = _fake_core_table({"T1_canonical": 0.02, "T2_magnitude_only": 0.008, "T3_volatility_only": 0.015})
    placebo = _fake_placebo({"T2_magnitude_only": 0.9})
    v, _ = p93.classify_magnitude_effect(core, placebo)
    assert v == "MAGNITUDE_EFFECT_REDUCED_TO_VOLATILITY"


def test_magnitude_verdict_confirmed():
    core = _fake_core_table({"T1_canonical": 0.02, "T2_magnitude_only": 0.018, "T3_volatility_only": 0.002})
    placebo = _fake_placebo({"T2_magnitude_only": 0.96})
    v, _ = p93.classify_magnitude_effect(core, placebo)
    assert v == "MAGNITUDE_EFFECT_CONFIRMED"


def test_volatility_verdict_confirmed():
    core = _fake_core_table({"T1_canonical": 0.02, "T3_volatility_only": 0.018})
    placebo = _fake_placebo({"T3_volatility_only": 0.97})
    v, _ = p93.classify_volatility_effect(core, placebo)
    assert v == "VOLATILITY_EXPLANATION_CONFIRMED"


def test_volatility_verdict_partial():
    core = _fake_core_table({"T1_canonical": 0.02, "T3_volatility_only": 0.009})
    placebo = _fake_placebo({"T3_volatility_only": 0.8})
    v, _ = p93.classify_volatility_effect(core, placebo)
    assert v == "VOLATILITY_EXPLANATION_PARTIAL"


def test_filter_mechanism_invalidated_when_below_placebo():
    core = _fake_core_table({"T1_canonical": 0.02})
    placebo = _fake_placebo({"T1_canonical": 0.05})
    v, _ = p93.classify_filter_mechanism(core, placebo, {"T1_canonical": {}})
    assert v == "FILTER_MECHANISM_INVALIDATED"


def test_directional_dependence_directionally_dependent():
    directional = {i: {"case": "Case B"} for i in p83.INSTRUMENTS_83}
    v, _ = p93.classify_directional_dependence(directional)
    assert v == "DIRECTIONALLY_DEPENDENT"


def test_directional_dependence_independent():
    directional = {i: {"case": "Case A"} for i in p83.INSTRUMENTS_83}
    v, _ = p93.classify_directional_dependence(directional)
    assert v == "DIRECTION_INDEPENDENT"


def test_cross_instrument_generalization_partial():
    fold = {i: {"classification": "STRONG_CONSISTENCY"} for i in list(p83.INSTRUMENTS_83)[:4]}
    fold.update({i: {"classification": "FAILURE"} for i in list(p83.INSTRUMENTS_83)[4:]})
    v, _ = p93.classify_cross_instrument_generalization(fold)
    assert v == "CROSS_INSTRUMENT_PARTIAL"


def test_incremental_volume_not_established_when_deltas_near_zero():
    core = _fake_core_table({"T1_canonical": 0.02, "T2_magnitude_only": 0.018, "T5_magnitude_plus_volume": 0.0181,
                            "T6_magnitude_plus_volatility": 0.019, "T7_full": 0.0191, "T3_volatility_only": 0.01,
                            "T4_volume_only": 0.001})
    placebo = _fake_placebo({k: 0.8 for k in p93._INFO_TREATMENTS})
    fold = {k: {i: {"classification": "MIXED"} for i in p83.INSTRUMENTS_83} for k in p93._INFO_TREATMENTS}
    out = p93.incremental_volume_analysis(core, placebo, fold)
    assert out["verdict"] == "VOLUME_INCREMENTAL_VALUE_NOT_ESTABLISHED"


# --- J. holdout protection & safety --------------------------------------------
def test_module_never_reads_raw_holdout_data():
    src = inspect.getsource(p93)
    for token in ("locked_holdout", "load_holdout", "xauusd_market_conditions", "xauusd_forward_accumulation"):
        assert token not in src
    assert "gsb.get_gold_baseline().frozen_contract_hash" in src


def test_module_source_has_no_execution_or_broker_imports_or_account_deletion():
    src = inspect.getsource(p93)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    forbidden = ["order_execution", "broker_adapter", "live_trading", "risk_engine", "account_management"]
    for f in forbidden:
        assert not any(f in l for l in import_lines), f"forbidden import: {f}"
    for token in ("place_order(", "submit_order(", "execute_trade(", "delete_account", "remove_account", "sign(mom_4)"):
        assert token not in src


def test_module_does_not_search_a_broad_grid():
    src = inspect.getsource(p93)
    assert "np.arange(0" not in src


def test_result_dataclass_reports_research_only_status():
    kw = dict(schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="h", universe=[],
              timeframe="15m", canonical_horizon=4, canonical_quantile=0.25, canonical_reproduction={},
              core_attribution_table={}, information_ablation={}, incremental_volume_analysis={}, placebo_battery={},
              directional_contamination={}, fold_level_classification={}, xauusd_deep_dive={}, jpy_hypothesis_matrix={},
              temporal_stability={}, cost_analysis={}, drawdown_decomposition={}, minimum_sufficient_mechanism={},
              magnitude_effect="MAGNITUDE_EFFECT_NOT_CONFIRMED", magnitude_effect_reason="x",
              volatility_explanation="VOLATILITY_EXPLANATION_NOT_CONFIRMED", volatility_explanation_reason="x",
              volume_incremental_value="VOLUME_INCREMENTAL_VALUE_NOT_ESTABLISHED", volume_incremental_value_reason="x",
              filter_mechanism="FILTER_MECHANISM_NOT_CONFIRMED", filter_mechanism_reason="x",
              directional_dependence="INSUFFICIENT_EVIDENCE", directional_dependence_reason="x",
              cross_instrument_generalization="NOT_GENERALIZABLE", cross_instrument_generalization_reason="x",
              determinism={"match": True})
    r = p93.Phase93Result(**kw)
    assert r.strategy_status == "RESEARCH_ONLY_NO_LIVE_EXECUTION_ARTIFACT"
    assert r.holdout_untouched is True
    assert r.directional_edge_found is False


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}
    monkeypatch.setattr(p93.store, "save_artifact", lambda k, kind, payload: (saved.update(key=k, payload=payload) or "h93"))
    monkeypatch.setattr(p93.store, "load_artifact", lambda k: {"payload": saved["payload"]} if k == saved.get("key") else None)
    kw = dict(schema_version=p93.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00", git_commit="abc",
              frozen_contract_hash="h", universe=list(p83.INSTRUMENTS_83), timeframe="15m", canonical_horizon=4,
              canonical_quantile=0.25, canonical_reproduction={}, core_attribution_table={}, information_ablation={},
              incremental_volume_analysis={}, placebo_battery={}, directional_contamination={},
              fold_level_classification={}, xauusd_deep_dive={}, jpy_hypothesis_matrix={}, temporal_stability={},
              cost_analysis={}, drawdown_decomposition={}, minimum_sufficient_mechanism={},
              magnitude_effect="MAGNITUDE_EFFECT_PROMISING", magnitude_effect_reason="x",
              volatility_explanation="VOLATILITY_EXPLANATION_PARTIAL", volatility_explanation_reason="x",
              volume_incremental_value="VOLUME_INCREMENTAL_VALUE_NOT_ESTABLISHED", volume_incremental_value_reason="x",
              filter_mechanism="FILTER_MECHANISM_PROMISING", filter_mechanism_reason="x",
              directional_dependence="DIRECTION_PARTIALLY_CONTAMINATED", directional_dependence_reason="x",
              cross_instrument_generalization="CROSS_INSTRUMENT_PARTIAL", cross_instrument_generalization_reason="x",
              determinism={"match": True}, content_hash="deadbeef")
    assert p93.persist(p93.Phase93Result(**kw)) == "h93"
    got = p93.get_result()
    assert got["content_hash"] == "deadbeef"
    assert got["filter_mechanism"] == "FILTER_MECHANISM_PROMISING"
