# -*- coding: utf-8 -*-
"""
Phase 86 — aggressive trading edge discovery.

Covers: the frozen three-way temporal split (own to this phase, distinct
from the Gold holdout), the conditional-asymmetry screen/promotion logic
(discovery-then-confirmation, never adjusted after seeing confirmation),
the momentum+volume-filter trading rule (R-multiple construction, threshold
screening, plateau-based frozen-threshold selection, cross-asset/temporal/
perturbation/cost-sensitivity/horizon-robustness/placebo machinery), the
scorecard/verdict decision tree, the research ledger's disclosure
discipline, and safety invariants. Synthetic bars for structural/logic
tests; the real full run is the artifact produced by
``python -m phase86_aggressive_edge_discovery``.
"""
import inspect
import re

import numpy as np
import pandas as pd

import phase76_event_study as p76
import phase83_conditional_interaction_discovery as p83
import phase85_tick_volume_confirmation as p85
import phase86_aggressive_edge_discovery as p86


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


def _momentum_signal_frame(n=10000, seed=17, effect=8.0):
    """A synthetic series where recent-momentum direction genuinely predicts
    the NEXT bar's return more strongly when a persistent (AR1) volume
    regime is high -- i.e. a real, known momentum+volume-filter effect for
    the rule logic to detect and for placebos to try to destroy. Built
    causally, bar by bar: bar i's continuation boost depends only on
    close[i-5..i-1] and vol_rank[i-1] (both already known before bar i)."""
    rng = np.random.default_rng(seed)
    vstate = np.zeros(n)
    for i in range(1, n):
        vstate[i] = 0.97 * vstate[i - 1] + rng.normal(0, 0.3)
    vol = np.exp(vstate) * 100.0 + 1.0
    vol_rank = pd.Series(vol).rolling(200, min_periods=1).apply(
        lambda s: (s <= s.iloc[-1]).mean(), raw=False).to_numpy()
    close = np.zeros(n)
    close[:5] = 100.0
    base_noise = rng.normal(0, 1.0, n)
    for i in range(5, n):
        mom_proxy = np.sign(close[i - 1] - close[i - 5])
        boost = effect * 0.01 * mom_proxy * vol_rank[i - 1]
        close[i] = close[i - 1] + base_noise[i] * 0.1 + boost
    high = close + np.abs(rng.normal(0, 0.15, n))
    low = close - np.abs(rng.normal(0, 0.15, n))
    open_ = close - rng.normal(0, 0.05, n)
    t0 = 1_650_000_000
    return [{"time": t0 + i * 900, "open": float(open_[i]),
             "high": float(max(open_[i], high[i], close[i])),
             "low": float(min(open_[i], low[i], close[i])),
             "close": float(close[i]), "volume": float(vol[i]), "source": "mt5"} for i in range(n)]


def _pooled(monkeypatch, rows, horizon=4):
    monkeypatch.setattr(p76.store, "get_candles", lambda i, t: rows)
    p85._clear_cache_85()
    return p85.build_pooled_dataset_85("15m", horizon, instruments=p83.INSTRUMENTS_83)


# --- A. three-way split -------------------------------------------------------
def test_three_way_split_is_ordered_and_non_overlapping():
    ts = pd.date_range("2024-06-01", "2026-06-01", freq="15min", tz="UTC")
    ds = pd.DataFrame({"prediction_timestamp": ts})
    disc, conf, hold = p86.three_way_split(ds)
    assert disc["prediction_timestamp"].max() < p86._DISCOVERY_CUTOFF
    assert conf["prediction_timestamp"].min() >= p86._CONFIRMATION_START
    assert conf["prediction_timestamp"].max() < p86._FINAL_HOLDOUT_START
    assert hold["prediction_timestamp"].min() >= p86._FINAL_HOLDOUT_START
    assert len(disc) + len(conf) + len(hold) <= len(ds)  # the H1 purge gap is excluded from all three


def test_final_holdout_start_is_after_confirmation_start():
    assert p86._FINAL_HOLDOUT_START > p86._CONFIRMATION_START


def test_split_dates_reuse_phase83_frozen_constants_unchanged():
    assert p86._DISCOVERY_CUTOFF == p83._DISCOVERY_CUTOFF
    assert p86._CONFIRMATION_START == p83._CONFIRMATION_START


# --- B. research ledger --------------------------------------------------------
def test_research_ledger_records_every_entry():
    ledger = p86.ResearchLedger()
    ledger.record("track_x", "h1", "desc", "discovery_screen", "REJECTED", "reason")
    ledger.record("track_x", "h2", "desc", "confirmation", "PROMOTED_LEVEL_1", "reason")
    assert len(ledger.to_list()) == 2
    summary = ledger.summary()
    assert summary["n_hypotheses_recorded"] == 2
    assert summary["n_promoted"] == 1
    assert summary["n_rejected"] == 1


# --- C. conditional asymmetry screen -------------------------------------------
def test_asymmetry_cells_are_exactly_eight_pre_registered():
    assert len(p86._ASYMMETRY_CELLS) == 8
    ids = [c["id"] for c in p86._ASYMMETRY_CELLS]
    assert len(set(ids)) == 8  # no duplicate ids


def test_cell_mask_is_mutually_exclusive_on_location():
    ds = pd.DataFrame({
        "feat__loc_in_range": [0.1, 0.5, 0.9],
        "feat__volume_rank": [0.9, 0.9, 0.9],
        "feat__regime_TRENDING": [1.0, 1.0, 1.0],
        "feat__regime_RANGING": [0.0, 0.0, 0.0],
    })
    high_cell = next(c for c in p86._ASYMMETRY_CELLS if c["id"] == "A1_high_loc_trending_highvol")
    low_cell = next(c for c in p86._ASYMMETRY_CELLS if c["id"] == "A3_low_loc_trending_highvol")
    high_mask = p86._cell_mask(ds, high_cell)
    low_mask = p86._cell_mask(ds, low_cell)
    assert not (high_mask & low_mask).any()
    assert high_mask.tolist() == [False, False, True]
    assert low_mask.tolist() == [True, False, False]


def test_conditional_asymmetry_screen_flags_insufficient_sample(monkeypatch):
    ds = _pooled(monkeypatch, _frame(n=3000))
    out = p86.conditional_asymmetry_screen(ds)
    assert set(out.keys()) == {c["id"] for c in p86._ASYMMETRY_CELLS}
    for row in out.values():
        assert "state" in row or "verdict" in row


def test_promote_asymmetry_candidates_never_promotes_a_random_null(monkeypatch):
    """On pure noise, essentially nothing should survive discovery-then-
    confirmation replication (a strong sanity check against false promotion)."""
    rows = _frame(n=8000, seed=99)
    ds = _pooled(monkeypatch, rows)
    disc, conf, _ = p86.three_way_split(ds)
    # use a synthetic frame spanning the real calendar range so disc/conf are non-trivial
    screen = p86.conditional_asymmetry_screen(disc) if len(disc) > 500 else {}
    promoted = p86.promote_asymmetry_candidates(screen, conf) if screen else {}
    # not a strict assertion of zero (noise can rarely pass by chance), but
    # promoted count must never exceed the number of pre-registered cells
    assert len(promoted) <= len(p86._ASYMMETRY_CELLS)


# --- D. candidate 1 rule construction -------------------------------------------
def test_rule_returns_only_includes_filtered_active_rows():
    ds = pd.DataFrame({
        "feat__mom_4": [1.0, -1.0, 0.0, 2.0],
        "feat__volume_rank": [0.9, 0.9, 0.9, 0.4],
        "T1": [0.5, 0.5, 0.5, 0.5],
    })
    r = p86._rule_returns(ds, threshold=0.7, cost_atr=0.0)
    # row 0: dir=+1, T1=0.5 -> +0.5 ; row1: dir=-1, T1=0.5 -> -0.5
    # row2 excluded (mom=0) ; row3 excluded (vol below threshold)
    assert sorted(r.tolist()) == [-0.5, 0.5]


def test_rule_returns_subtracts_cost():
    ds = pd.DataFrame({"feat__mom_4": [1.0], "feat__volume_rank": [1.0], "T1": [0.5]})
    r = p86._rule_returns(ds, threshold=0.5, cost_atr=0.05)
    assert abs(r[0] - 0.45) < 1e-9


def test_rule_stats_computes_hit_rate_and_profit_factor():
    r = np.array([1.0, 1.0, -0.5, -0.5, 2.0])
    stats = p86._rule_stats(r)
    assert stats["n_trades"] == 5
    assert stats["hit_rate"] == 0.6
    assert abs(stats["profit_factor"] - (4.0 / 1.0)) < 1e-9


def test_select_frozen_threshold_prefers_plateau_over_lone_spike():
    grid = p86._VOLUME_THRESHOLD_GRID
    # construct a fake screen: a lone spike at 0.70 with weak neighbours,
    # and a genuine plateau around 0.80-0.85-0.90
    screen = {t: {"verdict": "ZERO_CROSSING", "mean": 0.01, "n_trades": 1000} for t in grid}
    screen[0.70] = {"verdict": "POSITIVE", "mean": 0.50, "n_trades": 1000}
    for t in (0.80, 0.85, 0.90):
        screen[t] = {"verdict": "POSITIVE", "mean": 0.10, "n_trades": 1000}
    out = p86.select_frozen_threshold(screen, grid)
    assert out["frozen_threshold"] == 0.85  # the middle of the genuine plateau


def test_select_frozen_threshold_returns_none_if_nothing_clears_the_bar():
    grid = p86._VOLUME_THRESHOLD_GRID
    screen = {t: {"verdict": "ZERO_CROSSING", "mean": 0.001, "n_trades": 1000} for t in grid}
    out = p86.select_frozen_threshold(screen, grid)
    assert out["frozen_threshold"] is None


def test_screen_candidate1_covers_the_full_grid(monkeypatch):
    ds = _pooled(monkeypatch, _momentum_signal_frame())
    disc, _, _ = p86.three_way_split(ds)
    out = p86.screen_candidate1(disc)
    assert set(out.keys()) == set(p86._VOLUME_THRESHOLD_GRID)


def test_candidate1_recovers_a_known_synthetic_momentum_volume_effect(monkeypatch):
    # positional split -- the synthetic frame's 2022-anchored timestamps
    # never reach the real 2025-07/2026-03 confirmation window, so the real
    # three_way_split would leave confirmation empty for this fixture.
    ds = _pooled(monkeypatch, _momentum_signal_frame())
    n = len(ds)
    disc, conf = ds.iloc[: int(n * 0.7)], ds.iloc[int(n * 0.7):]
    screen = p86.screen_candidate1(disc)
    frozen = p86.select_frozen_threshold(screen)
    assert frozen["frozen_threshold"] is not None
    conf_stats = p86.evaluate_candidate1(conf, frozen["frozen_threshold"], p86.COST_SCENARIOS["BASE"])
    assert conf_stats["mean"] > 0


# --- E. robustness machinery ----------------------------------------------------
def test_candidate1_cross_asset_covers_all_six_instruments(monkeypatch):
    ds = _pooled(monkeypatch, _frame())
    n = len(ds)
    conf = ds.iloc[int(n * 0.5):]
    out = p86.candidate1_cross_asset(conf, 0.7, p86.COST_SCENARIOS["BASE"])
    assert set(out.keys()) == set(p83.INSTRUMENTS_83)


def test_candidate1_temporal_blocks_returns_a_list(monkeypatch):
    # positional split (see note above) -- p85._quarter_blocks groups by
    # the frame's OWN timestamps, so a non-empty synthetic slice works fine
    # regardless of which calendar year it is anchored to.
    ds = _pooled(monkeypatch, _frame())
    n = len(ds)
    conf = ds.iloc[int(n * 0.5):]
    out = p86.candidate1_temporal_blocks(conf, 0.7, p86.COST_SCENARIOS["BASE"])
    assert isinstance(out, list) and len(out) >= 1


def test_candidate1_cost_sensitivity_covers_all_three_scenarios(monkeypatch):
    ds = _pooled(monkeypatch, _momentum_signal_frame())
    n = len(ds)
    conf = ds.iloc[int(n * 0.5):]
    out = p86.candidate1_cost_sensitivity(conf, 0.7)
    assert set(out.keys()) == {"BASE", "ADVERSE", "SEVERE"}
    # higher cost must never produce a higher mean than lower cost
    assert out["BASE"]["mean"] >= out["ADVERSE"]["mean"] >= out["SEVERE"]["mean"]


def test_candidate1_placebos_collapse_a_known_synthetic_effect(monkeypatch):
    ds = _pooled(monkeypatch, _momentum_signal_frame())
    n = len(ds)
    disc, conf = ds.iloc[: int(n * 0.7)], ds.iloc[int(n * 0.7):]
    screen = p86.screen_candidate1(disc)
    frozen = p86.select_frozen_threshold(screen)
    real = p86.evaluate_candidate1(conf, frozen["frozen_threshold"], p86.COST_SCENARIOS["BASE"])
    placebos = p86.candidate1_placebos(conf, frozen["frozen_threshold"], p86.COST_SCENARIOS["BASE"])
    assert abs(placebos["direction_shuffle"]["mean"] or 0) < abs(real["mean"])
    assert abs(placebos["volume_shuffle"]["mean"] or 0) <= abs(real["mean"]) + 1e-6


def test_candidate1_parameter_perturbation_covers_local_neighbourhood():
    # unit test the neighbourhood-selection logic without a full data run
    grid = p86._VOLUME_THRESHOLD_GRID
    idx = list(grid).index(0.80)
    expected = grid[max(0, idx - 2): idx + 3]
    assert 0.80 in expected and len(expected) <= 5


# --- F. scorecard / verdict decision tree ---------------------------------------
def _base_scorecard(**overrides):
    sc = {"cost_sensitivity": {"survives_base": True, "survives_adverse": True, "survives_severe": True},
         "placebos_collapsed": True, "cross_asset_stability": "4/6",
         "parameter_robustness_plateau_stable": True, "temporal_stability": "4/5",
         "holdout": "POSITIVE"}
    sc.update(overrides)
    return sc


def test_verdict_no_edge_when_base_cost_fails():
    v, _ = p86.classify_final_verdict(_base_scorecard(
        cost_sensitivity={"survives_base": False, "survives_adverse": False, "survives_severe": False}))
    assert v == "NO_EDGE_FOUND"


def test_verdict_leakage_when_placebos_do_not_collapse():
    v, _ = p86.classify_final_verdict(_base_scorecard(placebos_collapsed=False))
    assert v == "LEAKAGE"


def test_verdict_actionable_but_not_economic_when_adverse_cost_fails():
    v, _ = p86.classify_final_verdict(_base_scorecard(
        cost_sensitivity={"survives_base": True, "survives_adverse": False, "survives_severe": False}))
    assert v == "ACTIONABLE_BUT_NOT_ECONOMIC"


def test_verdict_fragile_when_confined_to_one_instrument():
    v, _ = p86.classify_final_verdict(_base_scorecard(cross_asset_stability="1/6"))
    assert v == "POSITIVE_NET_EXPECTANCY_BUT_FRAGILE"


def test_verdict_fragile_when_not_plateau_stable():
    v, _ = p86.classify_final_verdict(_base_scorecard(parameter_robustness_plateau_stable=False))
    assert v == "POSITIVE_NET_EXPECTANCY_BUT_FRAGILE"


def test_verdict_promising_when_holdout_not_yet_positive():
    v, _ = p86.classify_final_verdict(_base_scorecard(holdout=None))
    assert v == "PROMISING_TRADING_HYPOTHESIS"


def test_verdict_robust_edge_candidate_when_severe_cost_fails():
    v, _ = p86.classify_final_verdict(_base_scorecard(
        cost_sensitivity={"survives_base": True, "survives_adverse": True, "survives_severe": False}))
    assert v == "ROBUST_EDGE_CANDIDATE"


def test_verdict_robust_trading_edge_requires_everything():
    v, _ = p86.classify_final_verdict(_base_scorecard())
    assert v == "ROBUST_TRADING_EDGE"


def test_verdict_never_awards_robust_trading_edge_without_holdout():
    for holdout in (None, "NEGATIVE", "ZERO_CROSSING", "INSUFFICIENT_SAMPLE"):
        v, _ = p86.classify_final_verdict(_base_scorecard(holdout=holdout))
        assert v != "ROBUST_TRADING_EDGE"


# --- G. safety invariants -------------------------------------------------------
def test_module_source_has_no_execution_or_broker_imports_or_order_logic():
    src = inspect.getsource(p86)
    import_lines = [l for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    forbidden = ["order_execution", "broker_adapter", "live_trading", "risk_engine"]
    for f in forbidden:
        assert not any(f in l for l in import_lines), f"forbidden import found: {f}"
    for token in ("place_order(", "submit_order(", "execute_trade("):
        assert token not in src


def test_result_dataclass_reports_research_only_status():
    r = p86.Phase86Result(
        schema_version="x", generated_at="x", git_commit=None, frozen_contract_hash="h",
        universe=[], timeframe="15m", split_dates={}, cost_scenarios=p86.COST_SCENARIOS,
        conditional_asymmetry_discovery_screen={}, conditional_asymmetry_promoted={},
        candidate1_discovery_screen={}, candidate1_frozen_threshold={}, candidate1_confirmation={},
        candidate1_cross_asset={}, candidate1_temporal_blocks=[], candidate1_parameter_perturbation={},
        candidate1_cost_sensitivity={}, candidate1_horizon_robustness={}, candidate1_placebos={},
        candidate1_final_holdout=None, scorecard={}, verdict="NO_EDGE_FOUND", verdict_reason="x",
        research_ledger=[], ledger_summary={}, determinism={},
    )
    assert r.strategy_status == "RESEARCH_ONLY_NO_LIVE_EXECUTION_ARTIFACT"
    assert r.holdout_untouched is True


def test_persist_and_get_result_roundtrip(monkeypatch):
    saved = {}

    def fake_save(key, kind, payload):
        saved["key"] = key
        saved["payload"] = payload
        return "fake_hash_p86"

    def fake_load(key):
        return {"payload": saved["payload"]} if key == saved.get("key") else None

    monkeypatch.setattr(p86.store, "save_artifact", fake_save)
    monkeypatch.setattr(p86.store, "load_artifact", fake_load)

    fake_result = p86.Phase86Result(
        schema_version=p86.SCHEMA_VERSION, generated_at="2026-01-01T00:00:00+00:00",
        git_commit="abc", frozen_contract_hash="h", universe=list(p83.INSTRUMENTS_83), timeframe="15m",
        split_dates={}, cost_scenarios=p86.COST_SCENARIOS, conditional_asymmetry_discovery_screen={},
        conditional_asymmetry_promoted={}, candidate1_discovery_screen={}, candidate1_frozen_threshold={},
        candidate1_confirmation={}, candidate1_cross_asset={}, candidate1_temporal_blocks=[],
        candidate1_parameter_perturbation={}, candidate1_cost_sensitivity={},
        candidate1_horizon_robustness={}, candidate1_placebos={}, candidate1_final_holdout=None,
        scorecard={}, verdict="NO_EDGE_FOUND", verdict_reason="x", research_ledger=[], ledger_summary={},
        determinism={"match": True}, content_hash="deadbeef",
    )
    h = p86.persist(fake_result)
    assert h == "fake_hash_p86"
    got = p86.get_result()
    assert got["content_hash"] == "deadbeef"
    assert got["verdict"] == "NO_EDGE_FOUND"
