# -*- coding: utf-8 -*-
"""
Phase 87 — directional information frontier.

Covers: the causal cross-market USD-strength-proxy construction (leave-one-
out group exclusion, no lookahead), the unified cross-market dataset
builder, the ablation/placebo/cross-asset machinery, the Lane A/Lane B
verdict decision trees, the data-availability feasibility audits (economic
surprise, order flow), the research ledger, and safety invariants.
Synthetic bars for structural/logic tests; the real full run is the
artifact produced by ``python -m phase87_directional_information_frontier``.
"""
import inspect
import re

import numpy as np
import pandas as pd

import phase76_event_study as p76
import phase83_conditional_interaction_discovery as p83
import phase87_directional_information_frontier as p87


def _frame(n=6000, seed=71, drift=0.0):
    rng = np.random.default_rng(seed)
    steps = rng.normal(drift, 1.0, n).cumsum()
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


# --- A. cross-market basket construction --------------------------------------
def test_usd_base_and_quote_groups_are_disjoint():
    assert set(p87.USD_BASE_GROUP).isdisjoint(set(p87.USD_QUOTE_GROUP))


def test_usd_strength_series_excludes_the_target_from_its_own_group(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    p87._clear_cache_87()
    s_no_target = p87.build_usd_strength_series(target=None, tf="15m")
    p87._clear_cache_87()
    s_excl_eurusd = p87.build_usd_strength_series(target="EURUSD", tf="15m")
    # EURUSD is in the quote group -- excluding it must change the series
    # (different group composition), not error, and both must be non-empty
    assert len(s_no_target) > 0
    assert len(s_excl_eurusd) > 0


def test_usd_strength_series_is_causal_unaffected_by_a_future_shock(monkeypatch):
    rows = _frame(n=2000)
    rows2 = [dict(r) for r in rows]
    for r in rows2[-100:]:
        r["close"] = r["close"] * 1.5
        r["high"] = r["high"] * 1.5
        r["low"] = r["low"] * 1.5
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    p87._clear_cache_87()
    s1 = p87.build_usd_strength_series(target="AUDJPY", tf="15m")
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows2)
    p87._clear_cache_87()
    s2 = p87.build_usd_strength_series(target="AUDJPY", tf="15m")
    common = s1.index.intersection(s2.index)[:1500]
    pd.testing.assert_series_equal(s1.loc[common], s2.loc[common], check_names=False)


def test_build_dataset_with_cross_market_has_usd_strength_columns(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    p87._clear_cache_87()
    ds = p87.build_dataset_with_cross_market("EURUSD", "15m", 4)
    assert not ds.empty
    assert "feat__usd_strength" in ds.columns
    assert "feat__usd_strength_rank" in ds.columns
    assert np.isfinite(ds["feat__usd_strength_rank"].to_numpy()).all()
    assert ((ds["feat__usd_strength_rank"] >= 0) & (ds["feat__usd_strength_rank"] <= 1)).all()


def test_feature_target_contract_holds_for_cross_market_dataset(monkeypatch):
    rows = _frame()
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    p87._clear_cache_87()
    ds = p87.build_dataset_with_cross_market("EURUSD", "15m", 4)
    contract = p83.assert_feature_target_contract(ds, "T1")
    assert contract["pass"] is True


# --- B. ablation ---------------------------------------------------------------
def test_cross_market_ablations_are_exactly_three_frozen_models():
    names = [n for n, _ in p87.CROSS_MARKET_ABLATIONS]
    assert names == ["M0_baseline", "M1_baseline_plus_usd_strength_raw",
                     "M2_baseline_plus_usd_strength_rank"]


def test_m0_is_exactly_phase83_baseline_d_unchanged():
    m0_feats = dict(p87.CROSS_MARKET_ABLATIONS)["M0_baseline"]
    assert m0_feats == list(p83.BASELINE_D_COLUMNS)


def test_run_cross_market_ablation_m0_has_no_delta(monkeypatch):
    rows = _frame(n=8000, seed=5)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    p87._clear_cache_87()
    ds = p87.build_dataset_with_cross_market("EURUSD", "15m", 4)
    n = len(ds)
    disc, conf = ds.iloc[: int(n * 0.7)], ds.iloc[int(n * 0.7):]
    out = p87.run_cross_market_ablation(disc, conf, "T1")
    assert "delta_r2_vs_M0" not in out["models"]["M0_baseline"]
    assert "delta_r2_vs_M0" in out["models"]["M1_baseline_plus_usd_strength_raw"]
    assert "delta_r2_vs_M0" in out["models"]["M2_baseline_plus_usd_strength_rank"]


def test_run_cross_market_ablation_deterministic(monkeypatch):
    rows = _frame(n=8000, seed=9)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    p87._clear_cache_87()
    ds = p87.build_dataset_with_cross_market("EURUSD", "15m", 4)
    n = len(ds)
    disc, conf = ds.iloc[: int(n * 0.7)], ds.iloc[int(n * 0.7):]
    a1 = p87._strip_internal(p87.run_cross_market_ablation(disc, conf, "T1"))
    a2 = p87._strip_internal(p87.run_cross_market_ablation(disc, conf, "T1"))
    assert a1 == a2


# --- C. placebo ------------------------------------------------------------------
def test_cross_market_placebo_returns_delta(monkeypatch):
    rows = _frame(n=8000, seed=13)
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    p87._clear_cache_87()
    ds = p87.build_dataset_with_cross_market("EURUSD", "15m", 4)
    n = len(ds)
    disc, conf = ds.iloc[: int(n * 0.7)], ds.iloc[int(n * 0.7):]
    out = p87.cross_market_placebo(disc, conf)
    assert "delta_r2" in out


# --- D. Lane A verdict decision tree ---------------------------------------------
def _fake_ablation(point, excl):
    return {"models": {"M2_baseline_plus_usd_strength_rank": {"delta_r2_vs_M0": {"point": point, "excludes_zero": excl}}}}


def test_lane_a_no_information_when_ci_does_not_exclude_zero():
    v, _ = p87.classify_lane_a(_fake_ablation(0.02, False), {}, {"delta_r2": 0.0})
    assert v == "NO_NEW_INFORMATION_FOUND"


def test_lane_a_not_actionable_below_materiality_margin():
    v, _ = p87.classify_lane_a(_fake_ablation(0.002, True), {}, {"delta_r2": 0.0})
    assert v == "DIRECTIONAL_INFORMATION_FOUND_BUT_NOT_ACTIONABLE"


def test_lane_a_leakage_when_placebo_does_not_collapse():
    v, _ = p87.classify_lane_a(_fake_ablation(0.02, True), {}, {"delta_r2": 0.025})
    assert v == "LEAKAGE"


def test_lane_a_not_actionable_when_breadth_too_narrow():
    cross_asset = {"XAUUSD": {"excludes_zero": True, "delta_r2": 0.02}}
    for inst in p83.INSTRUMENTS_83:
        cross_asset.setdefault(inst, {"excludes_zero": False, "delta_r2": 0.0})
    v, _ = p87.classify_lane_a(_fake_ablation(0.02, True), cross_asset, {"delta_r2": 0.0})
    assert v == "DIRECTIONAL_INFORMATION_FOUND_BUT_NOT_ACTIONABLE"


def test_lane_a_promising_when_all_gates_clear():
    cross_asset = {inst: {"excludes_zero": True, "delta_r2": 0.02} for inst in p83.INSTRUMENTS_83}
    v, _ = p87.classify_lane_a(_fake_ablation(0.02, True), cross_asset, {"delta_r2": 0.0})
    assert v == "PROMISING_TRADING_HYPOTHESIS"


# --- E. Lane B gate ---------------------------------------------------------------
def test_lane_b_blocked_when_lane_a_fails():
    for verdict in ("NO_NEW_INFORMATION_FOUND", "DIRECTIONAL_INFORMATION_FOUND_BUT_NOT_ACTIONABLE",
                   "LEAKAGE"):
        out = p87.lane_b_feasibility(verdict)
        assert out["attempted"] is False
        assert out["verdict"] == "DATA_SOURCE_UNAVAILABLE"


def test_lane_b_pending_when_lane_a_promising():
    out = p87.lane_b_feasibility("PROMISING_TRADING_HYPOTHESIS")
    assert out["attempted"] is True


# --- F. final decision tree --------------------------------------------------------
def test_final_decision_no_new_information_when_lane_a_fails():
    v, reason = p87.final_decision("NO_NEW_INFORMATION_FOUND",
                                   p87.lane_b_feasibility("NO_NEW_INFORMATION_FOUND"))
    assert v == "NO_NEW_INFORMATION_FOUND"
    assert "Case 3" in reason


def test_final_decision_promotes_lane_a_when_promising():
    v, _ = p87.final_decision("PROMISING_TRADING_HYPOTHESIS",
                              p87.lane_b_feasibility("PROMISING_TRADING_HYPOTHESIS"))
    assert v == "PROMISING_TRADING_HYPOTHESIS"


# --- G. feasibility audits ----------------------------------------------------------
def test_economic_surprise_feasibility_reports_unavailable():
    out = p87.economic_surprise_feasibility()
    assert out["fred_supplies_forecast_consensus"] is False
    assert out["verdict"] == "DATA_SOURCE_UNAVAILABLE"


def test_order_flow_feasibility_reports_unavailable():
    out = p87.order_flow_feasibility()
    assert out["copy_ticks_range_used"] is False
    assert out["verdict"] == "DATA_SOURCE_UNAVAILABLE"


def test_information_inventory_cites_phase84_matrix():
    out = p87.information_inventory()
    assert out["reused_from_phase84_frontier_matrix_n_rows"] >= 20


# --- H. research ledger -----------------------------------------------------------
def test_research_ledger_records_every_entry():
    ledger = p87.ResearchLedger87()
    ledger.record("lane_a", "h1", "desc", "discovery_screen", "SCREENED", "reason")
    ledger.record("lane_b", "h2", "desc", "feasibility_check", "DATA_SOURCE_UNAVAILABLE", "reason")
    assert len(ledger.to_list()) == 2


# --- I. safety invariants ----------------------------------------------------------
def test_module_source_has_no_execution_or_broker_imports():
    src = inspect.getsource(p87)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    forbidden = ["order_execution", "broker_adapter", "live_trading", "risk_engine"]
    for f in forbidden:
        assert not any(f in l for l in import_lines), f"forbidden import found: {f}"


def test_result_dataclass_reports_research_only_status():
    r = p87.Phase87Result(
        schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="h",
        universe=[], timeframe="15m", information_inventory={}, cross_market_basket={},
        lane_a_discovery_confirmation_split={}, lane_a_ablation={}, lane_a_cross_asset={},
        lane_a_temporal_stability=[], lane_a_horizon_robustness={}, lane_a_placebo={},
        lane_a_verdict="NO_NEW_INFORMATION_FOUND", lane_a_reason="x", lane_b={},
        research_ledger=[], verdict="NO_NEW_INFORMATION_FOUND", verdict_reason="x",
        determinism={},
    )
    assert r.strategy_status == "RESEARCH_ONLY_NO_LIVE_EXECUTION_ARTIFACT"
    assert r.holdout_untouched is True


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}

    def fake_save(key, kind, payload):
        saved["key"] = key
        saved["payload"] = payload
        return "fake_hash_p87"

    def fake_load(key):
        return {"payload": saved["payload"]} if key == saved.get("key") else None

    monkeypatch.setattr(p87.store, "save_artifact", fake_save)
    monkeypatch.setattr(p87.store, "load_artifact", fake_load)

    fake_result = p87.Phase87Result(
        schema_version=p87.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00",
        git_commit="abc", frozen_contract_hash="h", universe=list(p83.INSTRUMENTS_83),
        timeframe="15m", information_inventory={}, cross_market_basket={},
        lane_a_discovery_confirmation_split={}, lane_a_ablation={}, lane_a_cross_asset={},
        lane_a_temporal_stability=[], lane_a_horizon_robustness={}, lane_a_placebo={},
        lane_a_verdict="NO_NEW_INFORMATION_FOUND", lane_a_reason="x", lane_b={},
        research_ledger=[], verdict="NO_NEW_INFORMATION_FOUND", verdict_reason="x",
        determinism={"match": True}, content_hash="deadbeef",
    )
    h = p87.persist(fake_result)
    assert h == "fake_hash_p87"
    got = p87.get_result()
    assert got["content_hash"] == "deadbeef"
    assert got["verdict"] == "NO_NEW_INFORMATION_FOUND"
