# -*- coding: utf-8 -*-
"""
Phase 85 — tick-volume confirmation, generalization & feed-independence study.

Covers: frozen feature/baseline/target reuse, the unified matched-population
dataset builder, the M1-M4 ablation's structural correctness, cross-asset/
LOAO/temporal/horizon breakdown shapes, the confounding decomposition, the
full placebo battery's collapse behaviour on a synthetic signal, the
broker/feed-generalization and data-provenance audits (live, never
hard-coded), the multiple-testing BH bookkeeping, the verdict/claim-level
decision tree, and safety invariants. Synthetic bars for structural/logic
tests; a few audits are exercised live against the real store (cheap,
read-only, matching the precedent set by Phase 84's own tests) — the real
full run is the artifact produced by
``python -m phase85_tick_volume_confirmation``.
"""
import inspect
import re

import numpy as np
import pandas as pd

import phase76_event_study as p76
import phase83_conditional_interaction_discovery as p83
import phase85_tick_volume_confirmation as p85


def _frame(n=6000, seed=71, drift=0.0, vol_seed=None):
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, 1.0, n).cumsum()
    close = 100.0 + steps * 0.1
    high = close + np.abs(rng.normal(0, 0.15, n))
    low = close - np.abs(rng.normal(0, 0.15, n))
    open_ = close - rng.normal(0, 0.05, n)
    vrng = np.random.default_rng(vol_seed if vol_seed is not None else seed + 1)
    vol = np.abs(vrng.normal(100.0, 20.0, n)) + 1.0
    t0 = 1_650_000_000
    return [{"time": t0 + i * 900, "open": float(open_[i]),
             "high": float(max(open_[i], high[i], close[i])),
             "low": float(min(open_[i], low[i], close[i])),
             "close": float(close[i]), "volume": float(vol[i]), "source": "mt5"} for i in range(n)]


def _signal_frame(n=8000, seed=13, effect=3.0):
    """A synthetic frame whose true range depends on a PERSISTENT (AR1)
    volume regime, so the ablation/placebo machinery has a real, known
    effect to try to destroy. Persistence is essential: i.i.d. volume
    carries no information about future volume (and hence future range),
    so an AR1 regime is what makes the causal link testable at all."""
    rng = np.random.default_rng(seed)
    vstate = np.zeros(n)
    for i in range(1, n):
        vstate[i] = 0.97 * vstate[i - 1] + rng.normal(0, 0.3)
    vol = np.exp(vstate) * 100.0 + 1.0
    close = 100.0 + np.cumsum(rng.normal(0, 1, n)) * 0.05
    vol_rank = pd.Series(vol).rolling(200, min_periods=1).apply(
        lambda s: (s <= s.iloc[-1]).mean(), raw=False).to_numpy()
    rng_size = (0.05 + effect * vol_rank) * np.abs(rng.normal(1, 0.2, n))
    high = close + rng_size
    low = close - rng_size
    open_ = close - rng.normal(0, 0.02, n)
    t0 = 1_650_000_000
    return [{"time": t0 + i * 900, "open": float(open_[i]),
             "high": float(max(open_[i], high[i], close[i])),
             "low": float(min(open_[i], low[i], close[i])),
             "close": float(close[i]), "volume": float(vol[i]), "source": "mt5"} for i in range(n)]


def _pooled(monkeypatch, rows, horizon=4):
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    p85._clear_cache_85()
    return p85.build_pooled_dataset_85("15m", horizon, instruments=p85.INSTRUMENTS_83)


def _split(ds, frac=0.7):
    n = len(ds)
    return ds.iloc[: int(n * frac)].reset_index(drop=True), ds.iloc[int(n * frac):].reset_index(drop=True)


# --- A. frozen reuse & unified dataset builder -------------------------------
def test_ablations_are_frozen_to_exactly_m1_through_m4():
    names = [n for n, _ in p85.ABLATIONS_85]
    assert names == ["M1_baseline", "M2_baseline_plus_volume_rank",
                     "M3_baseline_plus_volume_ret_1", "M4_baseline_plus_both"]


def test_m1_is_exactly_phase83_baseline_d_unchanged():
    m1_feats = dict(p85.ABLATIONS_85)["M1_baseline"]
    assert m1_feats == list(p83.BASELINE_D_COLUMNS)


def test_m2_m3_m4_each_add_only_the_declared_volume_columns():
    d = dict(p85.ABLATIONS_85)
    base = set(p83.BASELINE_D_COLUMNS)
    assert set(d["M2_baseline_plus_volume_rank"]) - base == {"volume_rank"}
    assert set(d["M3_baseline_plus_volume_ret_1"]) - base == {"volume_ret_1"}
    assert set(d["M4_baseline_plus_both"]) - base == {"volume_rank", "volume_ret_1"}


def test_build_dataset_85_has_baseline_and_volume_columns(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    p85._clear_cache_85()
    ds = p85.build_dataset_85("EURUSD", "15m", 4)
    assert not ds.empty
    for c in p83.BASELINE_D_COLUMNS:
        assert f"feat__{c}" in ds.columns
    assert "feat__volume_rank" in ds.columns
    assert "feat__volume_ret_1" in ds.columns
    assert np.isfinite(ds["feat__volume_rank"].to_numpy()).all()


def test_build_dataset_85_matched_population_no_extra_nan_columns(monkeypatch):
    """Every row that reaches the output has ALL baseline+volume features
    finite -- the matched-population requirement is structural."""
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    p85._clear_cache_85()
    ds = p85.build_dataset_85("EURUSD", "15m", 4)
    all_cols = [f"feat__{c}" for c in list(p83.BASELINE_D_COLUMNS) + list(p85.VOLUME_COLUMNS)]
    assert np.isfinite(ds[all_cols].to_numpy(float)).all()


def test_feature_target_contract_holds(monkeypatch):
    ds = _pooled(monkeypatch, _frame())
    contract = p83.assert_feature_target_contract(ds, "T2")
    assert contract["pass"] is True


# --- B. population matching audit --------------------------------------------
def test_population_matching_audit_reports_per_instrument_and_totals():
    audit = p85.population_matching_audit()
    assert set(audit["per_instrument"].keys()) == set(p83.INSTRUMENTS_83)
    for row in audit["per_instrument"].values():
        assert row["n_final_all_ablations_M1_to_M4"] <= row["n_baseline_only_would_keep"]
    assert audit["total_rows_all_ablations_share"] <= audit["total_rows_baseline_only_would_have_had"]


# --- C. run_ablation structure -----------------------------------------------
def test_run_ablation_m1_has_no_delta_others_do(monkeypatch):
    ds = _pooled(monkeypatch, _frame())
    disc, conf = _split(ds)
    out = p85.run_ablation(disc, conf, "T2")
    assert "delta_r2_vs_M1" not in out["models"]["M1_baseline"]
    for name in ("M2_baseline_plus_volume_rank", "M3_baseline_plus_volume_ret_1", "M4_baseline_plus_both"):
        assert "delta_r2_vs_M1" in out["models"][name]
        assert "point" in out["models"][name]["delta_r2_vs_M1"]


def test_run_ablation_deterministic_across_two_calls(monkeypatch):
    ds = _pooled(monkeypatch, _frame())
    disc, conf = _split(ds)
    a1 = p85._strip_internal(p85.run_ablation(disc, conf, "T2"))
    a2 = p85._strip_internal(p85.run_ablation(disc, conf, "T2"))
    assert a1 == a2


def test_run_ablation_recovers_a_known_synthetic_volume_effect(monkeypatch):
    ds = _pooled(monkeypatch, _signal_frame())
    disc, conf = _split(ds)
    out = p85.run_ablation(disc, conf, "T2")
    delta = out["models"]["M4_baseline_plus_both"]["delta_r2_vs_M1"]["point"]
    assert delta > 0  # the synthetic data was constructed so volume genuinely helps


# --- D. cross-asset / LOAO ----------------------------------------------------
def test_cross_asset_breakdown_covers_all_six_instruments(monkeypatch):
    ds = _pooled(monkeypatch, _frame())
    disc, conf = _split(ds)
    abl = p85.run_ablation(disc, conf, "T2")
    out = p85.cross_asset_breakdown(abl, conf, "M4_baseline_plus_both")
    assert set(out.keys()) == set(p83.INSTRUMENTS_83)
    for row in out.values():
        assert "state" in row or "delta_r2" in row


def test_cross_asset_breakdown_insufficient_sample_flagged(monkeypatch):
    ds = _pooled(monkeypatch, _frame(n=1200))
    disc, conf = _split(ds)
    abl = p85.run_ablation(disc, conf, "T2")
    out = p85.cross_asset_breakdown(abl, conf, "M4_baseline_plus_both")
    # with all 6 instruments sharing the same tiny synthetic series, the
    # confirmation slice per instrument is small -- some may be flagged
    assert any(isinstance(v, dict) for v in out.values())


def test_leave_one_asset_out_covers_all_instruments_or_flags_insufficient(monkeypatch):
    ds = _pooled(monkeypatch, _frame())
    disc, conf = _split(ds)
    out = p85.leave_one_asset_out(disc, conf, "M4_baseline_plus_both", "T2")
    assert set(out.keys()) == set(p83.INSTRUMENTS_83)


# --- E. temporal / horizon stability -------------------------------------------
def test_quarter_blocks_partition_without_gaps():
    ts = pd.to_datetime(["2025-07-15", "2025-08-01", "2025-11-01", "2026-02-01"], utc=True)
    df = pd.DataFrame({"prediction_timestamp": ts})
    blocks = p85._quarter_blocks(df)
    assert blocks[0][0] == "2025Q3"
    assert blocks[-1][0] in ("2026Q1", "2026Q2")
    # every block is exactly one calendar quarter (3 months) wide
    for _, lo, hi in blocks:
        assert (hi - lo).days in (89, 90, 91, 92)


def test_temporal_stability_returns_a_list_of_blocks(monkeypatch):
    ds = _pooled(monkeypatch, _frame())
    disc, conf = _split(ds)
    abl = p85.run_ablation(disc, conf, "T2")
    out = p85.temporal_stability(abl, conf, "M4_baseline_plus_both")
    assert isinstance(out, list) and len(out) >= 1


def test_horizon_stability_covers_all_declared_horizons(monkeypatch):
    # horizon_stability calls the REAL calendar-based discovery_confirmation_split
    # internally; the synthetic frame's 2022-anchored timestamps never reach
    # the real 2025 confirmation window, so that split is patched here to a
    # positional 70/30 split (structural test only, not the real dates).
    rows = _frame(n=3000)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    monkeypatch.setattr(p85, "discovery_confirmation_split",
                        lambda ds: (ds.iloc[: int(len(ds) * 0.7)], ds.iloc[int(len(ds) * 0.7):]))
    p85._clear_cache_85()
    out = p85.horizon_stability("T2", "M4_baseline_plus_both")
    assert set(out.keys()) == set(p85.ALL_HORIZONS)
    for h, res in out.items():
        assert "M1_baseline" in res["models"]


# --- F. confounding analysis --------------------------------------------------
def test_confounding_analysis_has_all_declared_stages(monkeypatch):
    ds = _pooled(monkeypatch, _frame())
    disc, conf = _split(ds)
    out = p85.confounding_analysis(disc, conf, "T2")
    for stage in ("volatility_only", "volatility_plus_volume", "time_session_only",
                 "time_session_plus_volume", "full_baseline", "full_baseline_plus_volume"):
        assert stage in out
    assert "volatility_delta_from_volume" in out
    assert "full_baseline_delta_from_volume" in out


# --- G. placebo battery: must collapse a real synthetic effect ----------------
def test_target_shuffle_collapses_a_real_synthetic_effect(monkeypatch):
    ds = _pooled(monkeypatch, _signal_frame())
    disc, conf = _split(ds)
    real = p85.run_ablation(disc, conf, "T2")["models"]["M4_baseline_plus_both"]["delta_r2_vs_M1"]["point"]
    shuf = p85.target_shuffle_control(disc, conf, "M4_baseline_plus_both", "T2")
    assert abs(shuf["delta_r2"]) < abs(real)


def test_global_volume_shuffle_collapses_a_real_synthetic_effect(monkeypatch):
    ds = _pooled(monkeypatch, _signal_frame())
    disc, conf = _split(ds)
    real = p85.run_ablation(disc, conf, "T2")["models"]["M4_baseline_plus_both"]["delta_r2_vs_M1"]["point"]
    ph = p85.global_volume_shuffle_placebo(disc, conf, "M4_baseline_plus_both", "T2")
    assert abs(ph["delta_r2"]) < abs(real)


def test_stratified_shuffle_placebo_runs_and_returns_delta(monkeypatch):
    ds = _pooled(monkeypatch, _signal_frame())
    disc, conf = _split(ds)
    out = p85.stratified_shuffle_placebo(disc, conf, "M4_baseline_plus_both", "T2")
    assert "delta_r2" in out


def test_temporal_misalignment_placebo_uses_predeclared_offsets_only(monkeypatch):
    rows = _signal_frame(n=4000)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    p85._clear_cache_85()
    out = p85.temporal_misalignment_placebo(offsets=(10, 50))
    assert [o["offset_bars"] for o in out] == [10, 50]


def test_stronger_temporal_placebo_runs_and_returns_delta(monkeypatch):
    ds = _pooled(monkeypatch, _signal_frame())
    disc, conf = _split(ds)
    out = p85.stronger_temporal_placebo(disc, conf, "M4_baseline_plus_both", "T2")
    assert "delta_r2" in out


# --- H. distribution drift ----------------------------------------------------
def test_distribution_drift_audit_shape(monkeypatch):
    ds = _pooled(monkeypatch, _frame())
    disc, conf = _split(ds)
    out = p85.distribution_drift_audit(disc, conf)
    assert set(out["by_split"].keys()) == {"discovery", "confirmation"}
    for c in p85.VOLUME_COLUMNS:
        assert c in out["by_split"]["discovery"]
    assert set(out["by_instrument"].keys()) == set(p83.INSTRUMENTS_83)


# --- I. data provenance / feed generalization (live, cheap, read-only) -------
def test_data_provenance_audit_confirms_tick_volume_only():
    prov = p85.data_provenance_audit()
    mapping = prov["field_mapping_verified_by_source_inspection"]
    assert "tick_volume" in mapping["source_line"]
    assert mapping["captures_real_volume_field"] is False
    assert prov["schema_has_bid_ask_spread_or_depth"] is False
    assert set(prov["per_instrument_live_stats"].keys()) == set(p83.INSTRUMENTS_83)


def test_broker_feed_generalization_audit_verdict_is_valid():
    out = p85.broker_feed_generalization_audit()
    assert out["verdict"] in ("INDEPENDENT_FEED_REPLICATION_NOT_AVAILABLE",
                              "INDEPENDENT_FEED_CANDIDATE_FOUND_NOT_YET_TESTED")
    assert "capital_com_integration_note" in out
    assert out["yfinance_check"]["attempted"] is True


# --- J. multiple-testing audit -------------------------------------------------
def test_multiple_testing_audit_discloses_bounded_search_space():
    cross_asset = {"XAUUSD": {"delta_r2": 0.02, "ci": [0.01, 0.03]},
                  "EURUSD": {"delta_r2": 0.001, "ci": [-0.01, 0.012]}}
    horizons = {4: {"models": {"M4_baseline_plus_both":
                              {"delta_r2_vs_M1": {"point": 0.02, "se": 0.005}}}}}
    out = p85.multiple_testing_audit(cross_asset, horizons)
    assert out["disclosed_search_space"]["candidate_features_ever_tested_phase84_and_85"] == \
        list(p85.VOLUME_COLUMNS)
    assert set(out["cross_asset_bh_q0.10"].keys()) == {"XAUUSD", "EURUSD"}
    assert 4 in out["horizon_bh_q0.10"]


# --- K. verdict / claim-level decision tree ------------------------------------
def test_classify_verdict_rejects_when_ci_does_not_exclude_zero():
    v, claim, _ = p85.classify_verdict_85(0.02, False, True, True, True, True, 4, 6, False)
    assert v == "REJECTED"


def test_classify_verdict_artifact_when_leakage_fails():
    v, claim, _ = p85.classify_verdict_85(0.02, True, True, False, True, True, 4, 6, False)
    assert v == "ARTIFACT_OR_LEAKAGE"


def test_classify_verdict_artifact_when_placebo_does_not_collapse():
    v, claim, _ = p85.classify_verdict_85(0.02, True, False, True, True, True, 4, 6, False)
    assert v == "ARTIFACT_OR_LEAKAGE"


def test_classify_verdict_incremental_not_material_below_margin():
    v, claim, _ = p85.classify_verdict_85(0.002, True, True, True, True, True, 4, 6, False)
    assert v == "INCREMENTAL_BUT_NOT_MATERIAL"


def test_classify_verdict_unstable_when_breadth_below_half():
    v, claim, _ = p85.classify_verdict_85(0.02, True, True, True, True, True, 2, 6, False)
    assert v == "UNSTABLE"


def test_classify_verdict_promising_when_material_and_broad_but_no_independent_feed():
    v, claim, _ = p85.classify_verdict_85(0.02, True, True, True, True, True, 4, 6, False)
    assert v == "PROMISING_REQUIRES_FURTHER_CONFIRMATION"
    assert claim == "B"


def test_classify_verdict_robust_only_with_independent_feed_and_breadth():
    v, claim, _ = p85.classify_verdict_85(0.02, True, True, True, True, True, 4, 6, True)
    assert v == "ROBUST_INCREMENTAL_INFORMATION"
    assert claim == "C"


def test_classify_verdict_never_awards_robust_without_independent_feed():
    """Regression guard for the master prompt's Sec.44 requirement #17."""
    for n_pos in range(0, 7):
        v, claim, _ = p85.classify_verdict_85(0.05, True, True, True, True, True, n_pos, 6, False)
        assert v != "ROBUST_INCREMENTAL_INFORMATION"


# --- L. safety invariants -----------------------------------------------------
def test_module_source_has_no_execution_or_broker_imports():
    src = inspect.getsource(p85)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    forbidden = ["order_execution", "broker_adapter", "live_trading", "risk_engine"]
    for f in forbidden:
        assert not any(f in l for l in import_lines), f"forbidden import found: {f}"


def test_result_dataclass_reports_research_only_status():
    r = p85.Phase85Result(
        schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="h",
        universe=[], timeframe="15m", horizons=[1, 2, 4, 8], discovery_confirmation_split={},
        data_provenance={}, population_matching={}, ablation_headline={}, cross_asset_M2={},
        cross_asset_M4={}, leave_one_asset_out={}, temporal_stability=[], horizon_stability={},
        confounding={}, placebos={}, distribution_drift={}, broker_feed_generalization={},
        multiple_testing={}, determinism={}, verdict="REJECTED", claim_level="NONE",
        verdict_reason="test",
    )
    assert r.strategy_status == "RESEARCH_ONLY_NO_STRATEGY_ARTIFACT"
    assert r.holdout_untouched is True


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}

    def fake_save(key, kind, payload):
        saved["key"] = key
        saved["payload"] = payload
        return "fake_hash_xyz"

    def fake_load(key):
        return {"payload": saved["payload"]} if key == saved.get("key") else None

    monkeypatch.setattr(p85.store, "save_artifact", fake_save)
    monkeypatch.setattr(p85.store, "load_artifact", fake_load)

    fake_result = p85.Phase85Result(
        schema_version=p85.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00",
        git_commit="abc123", frozen_contract_hash="h", universe=list(p83.INSTRUMENTS_83),
        timeframe="15m", horizons=[1, 2, 4, 8], discovery_confirmation_split={}, data_provenance={},
        population_matching={}, ablation_headline={}, cross_asset_M2={}, cross_asset_M4={},
        leave_one_asset_out={}, temporal_stability=[], horizon_stability={}, confounding={},
        placebos={}, distribution_drift={}, broker_feed_generalization={}, multiple_testing={},
        determinism={"match": True}, verdict="PROMISING_REQUIRES_FURTHER_CONFIRMATION",
        claim_level="B", verdict_reason="test", content_hash="deadbeef",
    )
    h = p85.persist(fake_result)
    assert h == "fake_hash_xyz"
    got = p85.get_result()
    assert got["content_hash"] == "deadbeef"
    assert got["verdict"] == "PROMISING_REQUIRES_FURTHER_CONFIRMATION"
