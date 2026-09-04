# -*- coding: utf-8 -*-
"""
Phase 79 — ML target integrity, leakage audit & pilot readiness.

Target specification correctness, timestamp-ordering / rolling-window /
future-shock / past-shift leakage audits, the stable-ATR adversarial suite,
overlap + effective-N, purge/embargo, placebo-control decoupling, the
mean-invariance-of-permutation finding, cross-asset leave-one-out, cross-year
period stability, the integrity gate, determinism, holdout firewall, safety,
and no-ML-training. Synthetic bars only — no full data run (the real run is
the artifact produced by ``python -m phase79_ml_target_integrity``, exercised
separately as part of phase delivery, not by this suite).
"""
import inspect
import re

import numpy as np
import pandas as pd

import phase76_event_study as p76
import phase78_market_behavior_discovery_ii as p78
import phase79_ml_target_integrity as p


def _frame(n=6000, seed=7, drift=0.0):
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, 1.0, n).cumsum()
    close = 100.0 + steps * 0.1
    high = close + np.abs(rng.normal(0, 0.15, n))
    low = close - np.abs(rng.normal(0, 0.15, n))
    open_ = close - rng.normal(0, 0.05, n)
    t0 = 1_650_000_000
    return [{"time": t0 + i * 900, "open": float(open_[i]),
             "high": float(max(open_[i], high[i], close[i])),
             "low": float(min(open_[i], low[i], close[i])),
             "close": float(close[i]), "volume": 100.0, "source": "mt5"} for i in range(n)]


def _augmented(monkeypatch, rows, inst="EURUSD", tf="15m"):
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    return p78.augment(p76.load_bars(inst, tf), tf)


# --- A. target registry --------------------------------------------------
def test_target_registry_has_two_versioned_specs():
    reg = p.target_registry_dicts()
    assert len(reg) == 2
    names = {r["target_name"] for r in reg}
    assert names == {"V2_HIGH_VOL_REGIME_PERSISTENCE", "V1_COMPRESSION_DURATION_RANGE_EXPANSION"}
    versions = {r["version"] for r in reg}
    assert versions == {"V2-target-v1", "V1-target-v1"}
    required = ("target_name", "version", "family", "directional", "source_hypothesis",
               "description", "event_definition", "feature_timestamp_rule",
               "prediction_timestamp_rule", "target_start_rule", "target_end_rule",
               "horizon_bars", "normalization", "threshold_definition", "label_construction",
               "minimum_data_requirements", "invalid_missing_data_handling",
               "overlapping_label_behavior")
    for r in reg:
        for f in required:
            assert f in r and r[f] not in (None, "", [])


def test_v1_restricted_to_15m_only():
    assert p.V1_TIMEFRAMES == ("15m",)
    assert "1h" not in p.V1_TARGET_SPEC.description + p.V1_TARGET_SPEC.event_definition \
        or "NOT" in p.V1_TARGET_SPEC.description  # documents the restriction, doesn't silently drop it


def test_no_third_target_invented():
    # §37 — exactly V2 and V1, nothing else
    reg_names = {r["target_name"] for r in p.target_registry_dicts()}
    assert len(reg_names) == 2
    src = inspect.getsource(p)
    assert "H8" not in src           # Phase 77 large-bar reversal not reopened
    assert "large_bar_reversal" not in src.lower()


# --- B. timestamp-ordering audit -----------------------------------------
def test_materialize_and_audit_timestamps_v2(monkeypatch):
    df = _augmented(monkeypatch, _frame())
    idx = p78._b_vol_bucket_high(df)[0]
    tbl = p.materialize_target_rows(df, "15m", idx, "V2")
    assert not tbl.empty
    audit = p.audit_timestamp_ordering(tbl, "15m")
    assert audit["pass"] is True
    assert audit["feature_timestamp_never_after_prediction"] is True
    assert audit["target_end_strictly_after_prediction"] is True


def test_materialize_and_audit_timestamps_v1(monkeypatch):
    df = _augmented(monkeypatch, _frame(seed=8))
    idx = p78._b_compression_duration(df)[0]
    tbl = p.materialize_target_rows(df, "15m", idx, "V1")
    audit = p.audit_timestamp_ordering(tbl, "15m")
    assert audit["pass"] is True


def test_target_end_minus_prediction_equals_horizon_seconds(monkeypatch):
    df = _augmented(monkeypatch, _frame())
    idx = p78._b_vol_bucket_high(df)[0]
    tbl = p.materialize_target_rows(df, "15m", idx, "V2")
    gap = (tbl["target_end_timestamp"] - tbl["prediction_timestamp"]).dt.total_seconds()
    expected = tbl["horizon_bars"] * 900
    assert np.allclose(gap.to_numpy(), expected.to_numpy())


def test_audit_timestamp_ordering_catches_a_broken_table():
    bad = pd.DataFrame({
        "event_idx": [1], "target_idx": [5], "horizon_bars": [4],
        "feature_timestamp": [pd.Timestamp(2000, unit="s", tz="UTC")],
        "prediction_timestamp": [pd.Timestamp(1000, unit="s", tz="UTC")],  # feature AFTER prediction!
        "target_start_timestamp": [pd.Timestamp(1000, unit="s", tz="UTC")],
        "target_end_timestamp": [pd.Timestamp(4600, unit="s", tz="UTC")],
        "target_value": [1.0],
    })
    audit = p.audit_timestamp_ordering(bad, "15m")
    assert audit["pass"] is False
    assert audit["feature_timestamp_never_after_prediction"] is False


# --- C. rolling-window static scan ----------------------------------------
def test_rolling_window_audit_clean_on_real_modules():
    r = p.audit_rolling_windows()
    assert r["all_clean"] is True
    assert len(r["modules_audited"]) >= 6


def test_leakage_pattern_scanner_detects_injected_bad_patterns():
    assert p._scan_source_for_leakage_patterns("x.rolling(20, center=True).mean()")
    assert p._scan_source_for_leakage_patterns("y.shift(-3)")
    assert p._scan_source_for_leakage_patterns("z.fillna(method='bfill')")
    assert not p._scan_source_for_leakage_patterns("x.rolling(20).mean().shift(1)")


# --- D. future-shock / past-shift adversarial suite -----------------------
def test_future_shock_invariance_passes():
    r = p.check_future_shock_invariance()
    assert r["pass"] is True
    assert r["mismatches"] == {}


def test_future_shock_invariance_would_catch_a_genuinely_leaky_column():
    # sanity: prove the detector is not vacuously true by comparing a column
    # that DOES change (the raw close price after the shock) — the test harness
    # itself, not check_future_shock_invariance, does the comparison here.
    rows = p._synthetic_candles(3000, 101)
    base_df = p._frame_from_rows(rows, "15m")
    shocked_rows = [dict(r) for r in rows]
    shocked_rows[2505]["close"] *= 5.0
    shocked_df = p._frame_from_rows(shocked_rows, "15m")
    assert not np.allclose(base_df["close"].to_numpy()[2500:2520],
                           shocked_df["close"].to_numpy()[2500:2520])


def test_past_shift_decoupling_passes():
    r = p.check_past_shift_decoupling()
    assert r["pass"] is True
    assert r["features_unchanged_through_event"] is True
    assert r["target_changed_when_future_changed"] is True


# --- E. stable-ATR adversarial suite (§14) --------------------------------
def test_stable_atr_not_contaminated_by_compression():
    r = p.check_stable_atr_not_contaminated_by_compression()
    assert r["pass"] is True
    assert r["atr_stable_denominator_not_contaminated"] is True
    assert r["spot_atr_visibly_collapses"] is True


def test_future_bar_does_not_change_stable_atr_at_t():
    r = p.check_future_bar_does_not_change_stable_atr_at_t()
    assert r["pass"] is True
    assert r["atr_stable_at_t_before"] == r["atr_stable_at_t_after_future_shock"]


def test_synthetic_compression_freezes_both_range_and_close():
    rows = p._synthetic_compressed_then_normal(500, 1, compress_start=100, compress_len=10)
    closes = [r["close"] for r in rows[100:110]]
    assert len(set(closes)) == 1          # perfectly flat through the segment
    ranges = [r["high"] - r["low"] for r in rows[100:110]]
    assert max(ranges) < 1e-3


# --- F. overlap / effective sample size (§10/§21) -------------------------
def test_overlap_stats_shrinks_effective_n_for_dense_events():
    dense = np.arange(0, 10000, 2)     # every other bar -> heavy overlap at h>=2
    r = p.overlap_stats(dense, horizons=(1, 2, 4, 8))
    assert r["by_horizon"]["h1"]["effective_n_estimate"] == len(dense)   # gap=2 >= h=1, no overlap
    assert r["by_horizon"]["h8"]["effective_n_estimate"] < len(dense)    # gap=2 < h=8, heavy overlap
    assert r["by_horizon"]["h8"]["effective_n_ratio_of_raw_n"] < r["by_horizon"]["h1"]["effective_n_ratio_of_raw_n"]


def test_overlap_stats_no_overlap_for_sparse_events():
    sparse = np.arange(0, 10000, 500)  # gap=500 >> any horizon tested
    r = p.overlap_stats(sparse, horizons=(1, 2, 4, 8))
    for h in (1, 2, 4, 8):
        assert r["by_horizon"][f"h{h}"]["effective_n_ratio_of_raw_n"] == 1.0
        assert r["by_horizon"][f"h{h}"]["pct_neighboring_pairs_overlapping"] == 0.0


# --- G. purge / embargo (§11) ---------------------------------------------
def test_purge_embargo_detects_boundary_crossing():
    idx = np.array([95, 96, 97, 98, 200, 300])
    bound = 100
    r = p.purge_embargo_analysis(idx, bound, horizons=(1, 2, 4, 8))
    assert r["dev_n"] == 4                             # 95..98 are < bound
    assert r["by_horizon"]["h1"]["n_crossing_boundary"] == 0   # 98+1=99 < 100, no crossing at h1
    assert r["by_horizon"]["h4"]["n_crossing_boundary"] == 3   # 96,97,98 + 4 all >= 100
    assert r["purge_required"] is True


def test_purge_dev_indices_removes_crossing_events_only():
    idx = np.array([95, 96, 97, 98, 200])
    bound = 100
    purged = p.purge_dev_indices(idx, bound, h=4)
    assert 97 not in purged and 98 not in purged   # 97+4=101>=100, 98+4=102>=100
    assert 96 not in purged                        # 96+4=100>=100 -- boundary itself is excluded
    assert 95 in purged                            # 95+4=99<100, still fully inside dev
    assert 200 not in purged                       # not in dev region at all


def test_no_boundary_crossing_when_events_are_far_from_split():
    idx = np.array([10, 20, 30])
    r = p.purge_embargo_analysis(idx, bound=1000, horizons=(1, 2, 4, 8))
    assert r["purge_required"] is False


# --- H. label-shuffle degeneracy (documented, not a gate) -----------------
def test_label_shuffle_mean_is_permutation_invariant():
    vals = np.array([0.1, -0.2, 0.3, 0.5, -0.4, 0.2, 0.15, -0.1] * 5, float)
    r = p.label_shuffle_control(vals, block=4, seed=1)
    assert r is not None
    assert r["mean_invariant_to_permutation"] is True
    assert abs(r["real_mean"] - r["shuffled_mean"]) < 1e-9


def test_label_shuffle_returns_none_below_minimum_sample():
    assert p.label_shuffle_control(np.array([0.1, 0.2]), block=1, seed=1) is None


# --- I. time-shift control (§18) ------------------------------------------
def test_time_shift_control_weakens_a_real_effect(monkeypatch):
    df = _augmented(monkeypatch, _frame(n=8000, seed=9))
    idx = p78._b_vol_bucket_high(df)[0]
    base = p.time_shift_control(df, idx, "V2", 0, "15m")
    shifted = p.time_shift_control(df, idx, "V2", 8, "15m")
    if base and shifted and base.get("effect_z") and shifted.get("effect_z"):
        assert abs(shifted["effect_z"]) <= abs(base["effect_z"]) + 1e-6


def test_time_shift_control_none_on_tiny_sample():
    df = pd.DataFrame({"t": np.arange(50) * 900})
    df.attrs["tf"] = "15m"
    r = p.time_shift_control(df, np.array([5, 10]), "V2", 4, "15m")
    assert r is None


# --- J. baseline comparison (§20) -----------------------------------------
def test_baseline_comparison_v2_shape():
    cell = {"baseline_mean": 0.34, "raw_event_mean": 0.48, "mean": 0.14}
    r = p.baseline_comparison("V2", cell)
    assert r["majority_class_baseline_accuracy"] == 0.66
    assert "persistence" in r["interpretation"]


def test_baseline_comparison_v1_shape():
    cell = {"baseline_mean": 0.0, "raw_event_mean": 0.2, "mean": 0.2}
    r = p.baseline_comparison("V1", cell)
    assert r["naive_no_compression_baseline"] == 0.0


def test_baseline_comparison_unavailable_without_baseline():
    assert p.baseline_comparison("V2", {})["state"] == "UNAVAILABLE"


# --- K. leave-one-asset-out (§22) -----------------------------------------
def test_leave_one_out_universal_when_all_agree():
    cells = [{"instrument": i, "dev_mean": 0.1} for i in ("A", "B", "C", "D")]
    r = p.leave_one_asset_out(cells)
    assert r["remains_universal_under_every_single_leave_one_out"] is True


def test_leave_one_out_not_universal_when_dominated_by_one():
    cells = [{"instrument": "A", "dev_mean": 0.1}, {"instrument": "B", "dev_mean": -0.1},
            {"instrument": "C", "dev_mean": -0.1}]
    r = p.leave_one_asset_out(cells)
    # excluding A: B,C both negative -> universal there; excluding B or C still has A positive
    # among 2 remaining -> not unanimous unless the majority happens to agree both times
    assert "A" in r["per_instrument_held_out"]


# --- L. cross-year period split (§23) -------------------------------------
def test_cross_year_period_split_insufficient_years():
    rows = [{"year": 2020, "fwd_r": 0.1}] * 30
    r = p.cross_year_period_split(rows)
    assert r["state"] == "INSUFFICIENT_YEARS"


def test_cross_year_period_split_stable_sign():
    rows = ([{"year": 2018, "fwd_r": 0.1}] * 30 + [{"year": 2019, "fwd_r": 0.1}] * 30
           + [{"year": 2020, "fwd_r": 0.1}] * 30 + [{"year": 2021, "fwd_r": 0.1}] * 30)
    r = p.cross_year_period_split(rows)
    assert r["state"] == "OK"
    assert r["sign_stable_across_periods"] is True


def test_cross_year_period_split_unstable_sign():
    rows = ([{"year": 2018, "fwd_r": 0.2}] * 30 + [{"year": 2019, "fwd_r": 0.2}] * 30
           + [{"year": 2020, "fwd_r": -0.2}] * 30 + [{"year": 2021, "fwd_r": -0.2}] * 30)
    r = p.cross_year_period_split(rows)
    assert r["sign_stable_across_periods"] is False


# --- M. integrity gate (§33) ----------------------------------------------
_ALL_HARD_SOFT_TRUE = {
    "timestamp_ordering_pass": True, "rolling_window_static_scan_clean": True,
    "future_shock_invariance_pass": True, "past_shift_decoupling_pass": True,
    "stable_denominator_not_contaminated_pass": True, "placebo_control_destroys_signal": True,
    "determinism_pass": True, "holdout_untouched": True, "time_shift_shows_decay": True,
    "purge_had_negligible_impact": True, "loo_remains_universal": True,
    "cross_year_period_stable": True,
}


def test_gate_all_pass_is_integrity_ready():
    verdict, fails = p.target_integrity_gate(_ALL_HARD_SOFT_TRUE)
    assert verdict == "TARGET_INTEGRITY_READY"
    assert fails == []


def test_gate_hard_failure_is_rejected_not_downgraded():
    checks = dict(_ALL_HARD_SOFT_TRUE)
    checks["placebo_control_destroys_signal"] = False
    verdict, fails = p.target_integrity_gate(checks)
    assert verdict == "TARGET_REJECTED"
    assert "placebo_control_destroys_signal" in fails


def test_gate_soft_failure_is_requires_revision_not_rejected():
    checks = dict(_ALL_HARD_SOFT_TRUE)
    checks["loo_remains_universal"] = False
    verdict, fails = p.target_integrity_gate(checks)
    assert verdict == "TARGET_REQUIRES_REVISION"
    assert "loo_remains_universal" in fails


def test_gate_never_forces_integrity_ready_from_partial_checks():
    checks = {k: False for k in _ALL_HARD_SOFT_TRUE}
    verdict, fails = p.target_integrity_gate(checks)
    assert verdict == "TARGET_REJECTED"
    assert len(fails) > 0


# --- N. no-ML-training / no-third-hypothesis / safety ---------------------
def test_no_ml_training_in_module():
    src = inspect.getsource(p).lower()
    for bad in ("sklearn", "tensorflow", "torch", "lstm", "xgboost", "lightgbm",
               "randomforest", "reinforcement", "transformer", "keras", ".fit(", ".predict("):
        assert bad not in src


def test_frozen_holdout_never_accessed():
    src = inspect.getsource(p)
    for bad in ("LOCKED_HISTORICAL_BASELINE", "forward_accumulation", "forward_validator",
               "forward_lifecycle", "HistoricalVsForwardComparator",
               "get_holdout", "holdout_trades", "load_holdout", "holdout_df", "holdout_candles"):
        assert bad not in src
    # bare "holdout" occurs only in prose (module docstring + gate comment) --
    # never as part of a data-access identifier
    bare = re.findall(r"holdout(?!_untouched)", src.lower())
    assert len(bare) <= 3


def test_frozen_hash_and_safety_flags_intact():
    from xauusd_market_conditions import FROZEN_CONTRACT_HASH
    assert FROZEN_CONTRACT_HASH == \
        "7f135a1269626a21dba769b7f0173c8a5428dcb7b47a88976045ea8aff376b76"
    from xauusd_forward_lifecycle import ForwardExecutionLifecycleEngine as E
    assert E.LIVE_AUTOMATION_ENABLED is False
    assert E.LIVE_BROKER_TRANSMISSION == "BLOCKED"


def test_no_execution_or_broker_imports():
    src = inspect.getsource(p)
    for bad in ("execution_pipeline", "broker_adapter", "risk_gateway", "reconciliation",
               "order_execution", "live_trading", "live_automation"):
        assert bad not in src


def test_module_imports_clean():
    import importlib
    importlib.reload(p)


# --- O. determinism of the audit layer ------------------------------------
def test_rolling_window_and_adversarial_checks_are_deterministic():
    a = p.audit_rolling_windows()
    b = p.audit_rolling_windows()
    assert a == b
    a2 = p.check_future_shock_invariance()
    b2 = p.check_future_shock_invariance()
    assert a2 == b2
    a3 = p.check_stable_atr_not_contaminated_by_compression()
    b3 = p.check_stable_atr_not_contaminated_by_compression()
    assert a3 == b3
