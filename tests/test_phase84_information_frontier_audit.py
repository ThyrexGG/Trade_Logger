# -*- coding: utf-8 -*-
"""
Phase 84 — information frontier & missing signal research audit.

This is an audit/roadmap phase, not a pipeline phase — the tests reflect
that: causal-safety of the ONE new derived feature family (volume_rank/
volume_ret_1), the cumulative feature-group ablation's structural
correctness (constant-predictor special case, monotone group nesting),
the volume-ablation controls' collapse behaviour, the live (never
hard-coded) data-inventory audit, the information-frontier matrix's
vocabulary/schema, and safety invariants. Synthetic bars only — no full
data run (the real run is the artifact produced by
``python -m phase84_information_frontier_audit``).
"""
import inspect
import re

import numpy as np
import pandas as pd

import phase76_event_study as p76
import phase83_conditional_interaction_discovery as p83
import phase84_information_frontier_audit as p84


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


def _dataset(monkeypatch, rows, inst="EURUSD", horizon=4):
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    return p84.build_context_dataset_with_volume(inst, "15m", horizon)


# --- A. volume-feature construction: causal safety --------------------------
def test_volume_rank_uses_only_trailing_200_bar_window():
    df = pd.DataFrame({"vol": np.arange(1, 501, dtype=float)})
    out = p84._add_volume_features(df)
    # strictly increasing raw volume -> the trailing-window rank at the last
    # bar must be 1.0 (its own value is the max of its own trailing window)
    assert out["volume_rank"].iloc[-1] == 1.0
    assert out["volume_rank"].iloc[:199].isna().all()
    assert np.isfinite(out["volume_rank"].iloc[199:]).all()


def test_volume_rank_unaffected_by_a_future_shock():
    rng = np.random.default_rng(5)
    vol = np.abs(rng.normal(100, 20, 800)) + 1.0
    df1 = pd.DataFrame({"vol": vol.copy()})
    df2 = pd.DataFrame({"vol": vol.copy()})
    df2.loc[700:, "vol"] = df2.loc[700:, "vol"] * 50.0  # shock far in the future
    out1 = p84._add_volume_features(df1)
    out2 = p84._add_volume_features(df2)
    # bars strictly before the shock must be identical
    pd.testing.assert_series_equal(out1["volume_rank"].iloc[:699],
                                   out2["volume_rank"].iloc[:699], check_names=False)
    pd.testing.assert_series_equal(out1["volume_ret_1"].iloc[:699],
                                   out2["volume_ret_1"].iloc[:699], check_names=False)


def test_volume_ret_1_is_log_ratio_and_handles_nonpositive():
    df = pd.DataFrame({"vol": [10.0, 20.0, 0.0, 5.0]})
    out = p84._add_volume_features(df)
    assert np.isnan(out["volume_ret_1"].iloc[0])
    assert abs(out["volume_ret_1"].iloc[1] - np.log(2.0)) < 1e-9
    assert np.isnan(out["volume_ret_1"].iloc[2])  # prev>0 but current==0
    assert np.isnan(out["volume_ret_1"].iloc[3])  # prev==0


def test_build_context_dataset_with_volume_has_volume_columns(monkeypatch):
    ds = _dataset(monkeypatch, _frame())
    assert not ds.empty
    assert "feat__volume_rank" in ds.columns
    assert "feat__volume_ret_1" in ds.columns
    assert np.isfinite(ds["feat__volume_rank"].to_numpy()).all()
    assert ((ds["feat__volume_rank"] >= 0) & (ds["feat__volume_rank"] <= 1)).all()


def test_build_context_dataset_with_volume_matches_p83_context_columns(monkeypatch):
    rows = _frame()
    ds = _dataset(monkeypatch, rows)
    ds83 = _dataset_p83(monkeypatch, rows)
    base_cols = {f"feat__{c}" for c in p83.BASELINE_D_COLUMNS}
    assert base_cols.issubset(set(ds.columns))
    assert base_cols.issubset(set(ds83.columns))


def _dataset_p83(monkeypatch, rows, inst="EURUSD", horizon=4):
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    return p83.build_context_dataset(inst, "15m", horizon)


def test_feature_target_timestamp_contract_holds_for_volume_dataset(monkeypatch):
    ds = _dataset(monkeypatch, _frame())
    contract = p83.assert_feature_target_contract(ds, "T2")
    assert contract["pass"] is True


# --- B. cumulative feature-group ablation ------------------------------------
def test_cumulative_groups_are_nested_and_end_at_full_baseline_d():
    groups = p84._cumulative_feature_groups()
    assert groups[0][0] == "G0_intercept_only"
    assert groups[0][1] == []
    prev = set()
    for name, feats in groups:
        fs = set(feats)
        assert prev.issubset(fs), f"{name} must be a superset of the previous group"
        prev = fs
    assert set(groups[-1][1]) == set(p83.BASELINE_D_COLUMNS)


def test_empty_feature_group_is_a_constant_predictor():
    train = pd.DataFrame({"feat__x": [1.0, 2.0, 3.0], "T2": [0.1, 0.3, 0.5]})
    test = pd.DataFrame({"feat__x": [4.0, 5.0], "T2": [0.2, 0.4]})
    r = p84._fit_eval_group_84(train, test, [], "T2")
    assert r["features"] == []
    assert np.allclose(r["_p_pred"], 0.3)  # train mean
    assert r["metrics"]["mean_predicted"] == 0.3


def test_directional_hit_rate_is_half_when_prediction_is_uninformative():
    y = np.array([1.0, -1.0, 1.0, -1.0])
    p = np.zeros(4)  # exactly zero -> excluded, falls back to 0.5
    assert p84._directional_hit_rate(y, p) == 0.5


def test_directional_hit_rate_perfect_sign_match():
    y = np.array([1.0, -1.0, 2.0, -3.0])
    p = np.array([0.5, -0.5, 0.1, -0.1])
    assert p84._directional_hit_rate(y, p) == 1.0


def test_feature_group_ablation_runs_on_synthetic_pooled_dataset(monkeypatch):
    rows = _frame(n=4000, seed=11)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    ds = p83.build_pooled_context_dataset("15m", 4, instruments=("EURUSD",))
    disc, conf = p83.discovery_confirmation_split(
        ds.assign(prediction_timestamp=pd.to_datetime(ds["prediction_timestamp"])))
    # force a 60/40-style split for the synthetic (small) dataset since the
    # real discovery/confirmation cutoffs are calendar dates far outside the
    # synthetic series' 2022-anchored timestamps
    n = len(ds)
    disc, conf = ds.iloc[: int(n * 0.7)], ds.iloc[int(n * 0.7):]
    out = p84.run_feature_group_ablation(disc, conf)
    assert set(out.keys()) == {"T1", "T2", "full_vs_intercept_delta_r2"}
    for t in ("T1", "T2"):
        assert len(out[t]) == 5
        assert out[t][0]["group"] == "G0_intercept_only"
        assert out[t][0]["n_features"] == 0


# --- C. volume ablation + controls -------------------------------------------
def test_run_volume_ablation_adds_exactly_two_new_columns(monkeypatch):
    rows = _frame(n=4000, seed=23)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    ds = p84.build_pooled_volume_dataset("15m", 4, instruments=("EURUSD",))
    n = len(ds)
    disc, conf = ds.iloc[: int(n * 0.7)], ds.iloc[int(n * 0.7):]
    out = p84.run_volume_ablation(disc, conf)
    assert set(out.keys()) == {"T1", "T2"}
    for t in ("T1", "T2"):
        assert "delta_r2" in out[t]
        assert "point" in out[t]["delta_r2"]


def test_volume_ablation_controls_returns_both_controls(monkeypatch):
    rows = _frame(n=4000, seed=29)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    ds = p84.build_pooled_volume_dataset("15m", 4, instruments=("EURUSD",))
    n = len(ds)
    disc, conf = ds.iloc[: int(n * 0.7)], ds.iloc[int(n * 0.7):]
    out = p84.volume_ablation_controls(disc, conf, "T2")
    assert out["target"] == "T2"
    assert "shuffled_target_control" in out
    assert "volume_shuffle_placebo" in out


def test_shuffled_target_control_collapses_relative_to_real_signal():
    """On a synthetic series where volume genuinely helps by construction,
    shuffling the TRAIN target must destroy essentially all predictive
    power for both the baseline and the +volume model."""
    rng = np.random.default_rng(3)
    n = 5000
    vol_rank = rng.uniform(0, 1, n)
    x = rng.normal(0, 1, n)
    y = 0.5 * x + 0.5 * vol_rank + rng.normal(0, 0.2, n)
    df = pd.DataFrame({"feat__x": x, "feat__volume_rank": vol_rank, "feat__volume_ret_1": rng.normal(0, 1, n),
                       "T2": y})
    train, test = df.iloc[:3500], df.iloc[3500:]
    r_full = p84._fit_eval_group_84(train, test, ["x"], "T2")
    r_vol = p84._fit_eval_group_84(train, test, ["x", "volume_rank", "volume_ret_1"], "T2")
    assert r_vol["metrics"]["oos_r2"] > r_full["metrics"]["oos_r2"] + 0.01

    train_shuf = train.copy()
    rng2 = np.random.default_rng(84001)
    train_shuf["T2"] = rng2.permutation(train_shuf["T2"].to_numpy())
    r_full_s = p84._fit_eval_group_84(train_shuf, test, ["x"], "T2")
    r_vol_s = p84._fit_eval_group_84(train_shuf, test, ["x", "volume_rank", "volume_ret_1"], "T2")
    assert r_full_s["metrics"]["oos_r2"] < 0.05
    assert r_vol_s["metrics"]["oos_r2"] < 0.05


# --- D. redundancy / data-inventory / m1-feasibility -------------------------
def test_redundancy_audit_shape(monkeypatch):
    rows = _frame(n=4000, seed=41)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    ds = p83.build_pooled_context_dataset("15m", 4, instruments=("EURUSD",))
    r = p84.redundancy_audit(ds)
    assert r["n_features"] == len(p83.BASELINE_D_COLUMNS)
    assert "mutual_info_with_targets" in r
    assert set(r["mutual_info_with_targets"].keys()) == {"T1", "T2"}
    assert 0 <= r["pca_explained_variance_ratio"][0] <= 1.0
    assert r["n_components_for_90pct_variance"] <= len(p83.BASELINE_D_COLUMNS)


def test_data_inventory_audit_is_live_not_hardcoded():
    inv = p84.data_inventory_audit()
    assert set(inv["canonical_universe"]) == set(p83.INSTRUMENTS_83)
    for inst in inv["canonical_universe"]:
        assert inst in inv["timeframes_populated_per_instrument"]
    assert isinstance(inv["m1_m5_available_for"], list)
    assert isinstance(inv["m1_m5_available_for_all_canonical_instruments"], bool)


def test_m1_resolution_feasibility_documents_a_verdict_not_silent_skip():
    inv = {"canonical_universe": ["A", "B", "C"], "m1_m5_available_for": ["A"]}
    out = p84.m1_resolution_feasibility(inv)
    assert out["verdict"] == "NOT_ATTEMPTED_DATA_INSUFFICIENT"
    assert "A" in out["reasoning"]
    assert len(out["reasoning"]) > 50  # a real justification, not a placeholder


def test_m1_resolution_feasibility_handles_zero_coverage():
    inv = {"canonical_universe": ["A", "B"], "m1_m5_available_for": []}
    out = p84.m1_resolution_feasibility(inv)
    assert "no instrument" in out["reasoning"]


# --- E. predictability ceiling table ------------------------------------------
def test_predictability_ceiling_table_reads_live_not_hardcoded(monkeypatch):
    fake_p83 = {"scorecard": [
        {"target": "T2", "baseline_r2_confirmation": 0.42},
        {"target": "T1", "baseline_r2_confirmation": 0.01},
    ]}
    monkeypatch.setattr(p84.p83, "get_result", lambda: fake_p83)
    monkeypatch.setattr(p84.p80, "get_result", lambda: None)
    monkeypatch.setattr(p84.p82, "get_result", lambda: None)
    rows = p84.predictability_ceiling_table()
    values = {r["target_class"].split()[0]: r["value"] for r in rows}
    assert values["MAGNITUDE"] == 0.42
    assert values["DIRECTION"] == 0.01


def test_predictability_ceiling_table_handles_missing_artifacts(monkeypatch):
    monkeypatch.setattr(p84.p83, "get_result", lambda: None)
    monkeypatch.setattr(p84.p80, "get_result", lambda: None)
    monkeypatch.setattr(p84.p82, "get_result", lambda: None)
    rows = p84.predictability_ceiling_table()
    assert rows == []


# --- F. information frontier matrix: schema & vocabulary ---------------------
_VALID_VERDICTS = {"REDUNDANT", "LOW_INFORMATION_VALUE", "DATA_INFEASIBLE",
                   "CAUSALLY_DIFFICULT", "PROMISING_RESEARCH_FRONTIER",
                   "HIGH_PRIORITY_RESEARCH_FRONTIER", "N/A_FOUNDATION"}
_VALID_PRIORITIES = {"P0", "P1", "P2", "P3", "N/A"}
_REQUIRED_MATRIX_KEYS = {"source", "category", "already_present", "orthogonal",
                         "historical_availability", "resolution", "causal_difficulty",
                         "cost", "priority", "verdict"}


def test_frontier_matrix_has_at_least_twenty_rows():
    assert len(p84.INFORMATION_FRONTIER_MATRIX) >= 20


def test_frontier_matrix_every_row_has_required_keys_and_valid_vocabulary():
    for row in p84.INFORMATION_FRONTIER_MATRIX:
        missing = _REQUIRED_MATRIX_KEYS - set(row.keys())
        assert not missing, f"{row.get('source')} missing {missing}"
        assert row["verdict"] in _VALID_VERDICTS, row["source"]
        assert row["priority"] in _VALID_PRIORITIES, row["source"]


def test_frontier_matrix_never_uses_the_word_edge_or_strategy_candidate():
    for row in p84.INFORMATION_FRONTIER_MATRIX:
        blob = " ".join(str(v) for v in row.values()).lower()
        assert "strategy_candidate" not in blob
        assert re.search(r"\bedge\b", blob) is None


def test_frontier_matrix_covers_required_minimum_categories():
    sources_blob = " ".join(r["source"].lower() for r in p84.INFORMATION_FRONTIER_MATRIX)
    for kw in ("ohlc", "volatility", "volume", "vwap", "structure", "order flow",
              "futures", "open interest", "options", "positioning", "macro",
              "news", "cross-market", "liquidity", "depth"):
        assert kw in sources_blob, f"missing category keyword: {kw}"


def test_tick_volume_row_reflects_the_empirical_ablation_finding():
    row = next(r for r in p84.INFORMATION_FRONTIER_MATRIX if "tick_volume" in r["source"])
    assert row["verdict"] == "HIGH_PRIORITY_RESEARCH_FRONTIER"
    assert row["priority"] == "P0"
    assert "0.0204" in row["note"] or "run_volume_ablation" in row["note"]


# --- G. module-level safety invariants ---------------------------------------
def test_module_source_has_no_execution_or_broker_imports():
    src = inspect.getsource(p84)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    forbidden = ["order_execution", "broker_adapter", "live_trading", "risk_engine"]
    for f in forbidden:
        assert not any(f in l for l in import_lines), f"forbidden import found: {f}"


def test_module_never_claims_a_strategy_or_an_edge_in_docstring():
    doc = p84.__doc__ or ""
    assert "STRATEGY_CANDIDATE" not in doc


def test_result_dataclass_reports_research_only_status():
    r = p84.Phase84Result(
        schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="h",
        universe=[], timeframe="15m", volume_column_audit={}, mt5_capability_audit={},
        macro_news_ai_audit={}, data_inventory={}, m1_resolution_feasibility={},
        feature_group_ablation={}, volume_ablation={}, volume_ablation_controls={},
        redundancy_audit={}, predictability_ceiling=[], information_frontier_matrix=[],
        determinism={},
    )
    assert r.strategy_status == "RESEARCH_ONLY_NO_STRATEGY_ARTIFACT"
    assert r.holdout_untouched is True
    d = r.to_dict()
    assert d["strategy_status"] == "RESEARCH_ONLY_NO_STRATEGY_ARTIFACT"


def test_persist_and_get_result_roundtrip(monkeypatch, tmp_path):
    saved = {}

    def fake_save(key, kind, payload):
        saved["key"] = key
        saved["payload"] = payload
        return "fake_hash_abc"

    def fake_load(key):
        return {"payload": saved["payload"]} if key == saved.get("key") else None

    monkeypatch.setattr(p84.store, "save_artifact", fake_save)
    monkeypatch.setattr(p84.store, "load_artifact", fake_load)

    fake_result = p84.Phase84Result(
        schema_version=p84.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00",
        git_commit="abc123", frozen_contract_hash="h", universe=["XAUUSD"], timeframe="15m",
        volume_column_audit={}, mt5_capability_audit={}, macro_news_ai_audit={},
        data_inventory={}, m1_resolution_feasibility={}, feature_group_ablation={},
        volume_ablation={}, volume_ablation_controls={}, redundancy_audit={},
        predictability_ceiling=[], information_frontier_matrix=[], determinism={"match": True},
        content_hash="deadbeef",
    )
    h = p84.persist(fake_result)
    assert h == "fake_hash_abc"
    got = p84.get_result()
    assert got["content_hash"] == "deadbeef"
    assert got["schema_version"] == p84.SCHEMA_VERSION


def test_run_is_deterministic_on_synthetic_ablation_identity(monkeypatch):
    rows = _frame(n=4000, seed=59)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    ds = p83.build_pooled_context_dataset("15m", 4, instruments=("EURUSD",))
    n = len(ds)
    disc, conf = ds.iloc[: int(n * 0.7)], ds.iloc[int(n * 0.7):]
    a1 = p84.run_feature_group_ablation(disc, conf)
    a2 = p84.run_feature_group_ablation(disc, conf)
    assert p84._ablation_identity(a1) == p84._ablation_identity(a2)
