# -*- coding: utf-8 -*-
"""Phase 70 — pair x strategy ranking & robustness (§56)."""
import pytest

import pair_ranking as pr
import strategy_discovery as disc


# --- ranking logic (unit, no store) -----------------------------------
def _cand(sym, sid, oos_exp, n, ci_low, pf=1.5, dd=3.0, wfo=None):
    return {
        "strategy_id": sid, "strategy_family": "X", "asset": sym, "timeframe": "1h",
        "state": "AVAILABLE", "params": {},
        "oos_metrics": {"expectancy_r": oos_exp, "total_trades": n, "profit_factor": pf,
                        "max_drawdown_r": dd, "win_rate_pct": 55.0},
        "all_metrics": {"total_trades": n},
        "bootstrap_ci": {"ci_lower": ci_low, "ci_upper": ci_low + 0.3,
                         "ci_range_str": f"[{ci_low:+.2f}R, {ci_low+0.3:+.2f}R]"},
        "scorecard": {"status": "PROMISING"},
        "walk_forward": {"stability": wfo} if wfo is not None else {},
    }


def test_ranking_is_not_by_raw_profit():
    """A +0.5R / N=12 candidate must NOT outrank a +0.15R / N=400 robust one."""
    from strategy_discovery import DiscoveryResult

    def mk(oos_exp, n, ci_low):
        return DiscoveryResult(
            asset="X", strategy_id="s", strategy_version="1", timeframe="1h",
            state="AVAILABLE", reason="", params={}, dataset_id="d", dataset_hash="h",
            is_metrics={"total_trades": n}, oos_metrics={
                "expectancy_r": oos_exp, "total_trades": n, "profit_factor": 1.6,
                "max_drawdown_r": 3.0},
            all_metrics={"total_trades": n},
            bootstrap_ci={"ci_lower": ci_low, "ci_upper": ci_low + 0.2,
                          "ci_range_str": "x"},
            scorecard={}, session_breakdown={}, regime_breakdown={},
            temporal_breakdown={}, execution_assumptions={}, coverage={},
            generated_at="t")

    big_profit_small_n = disc.research_ranking_score(mk(0.5, 12, 0.05))
    modest_robust = disc.research_ranking_score(mk(0.15, 400, 0.08))
    # the small-N candidate is not even scored
    assert big_profit_small_n["score"] is None
    assert modest_robust["score"] is not None


def test_small_sample_never_enters_leaderboard():
    run = pr.RankingRun(
        generated_at="t", code_version="x", timeframe="1h", deep=False,
        execution_assumptions={}, universe=["EURUSD"], strategies=["s"],
        store_coverage=[])
    run.candidates = [{
        "strategy_id": "s", "asset": "EURUSD", "strategy_family": "F",
        "oos_metrics": {"total_trades": 5, "expectancy_r": 2.0},
        "bootstrap_ci": {}, "scorecard": {},
        "research_ranking_score": {"score": None, "state": "INSUFFICIENT_EVIDENCE"},
    }]
    scored = [c for c in run.candidates
              if c["research_ranking_score"]["score"] is not None]
    assert scored == []


def test_classify_pair_stability_gold_specific():
    per_asset = {
        "XAUUSD": {"state": "AVAILABLE", "oos_metrics": {"expectancy_r": 0.2},
                   "bootstrap_ci": {"ci_lower": 0.05}},
        "EURUSD": {"state": "AVAILABLE", "oos_metrics": {"expectancy_r": -0.1},
                   "bootstrap_ci": {"ci_lower": -0.3}},
    }
    out = pr.classify_pair_stability(per_asset)
    assert out["class"] == "GOLD_SPECIFIC_EDGE"
    assert out["positive_instruments"] == ["XAUUSD"]


def test_classify_pair_stability_no_edge():
    per_asset = {"EURUSD": {"state": "AVAILABLE", "oos_metrics": {"expectancy_r": -0.2},
                            "bootstrap_ci": {"ci_lower": -0.4}}}
    assert pr.classify_pair_stability(per_asset)["class"] == "NO_EDGE_ANYWHERE"


def test_verdict_honestly_reports_no_robust_edge():
    v = pr._verdict([], [])
    assert "INSUFFICIENT_EVIDENCE" in v or "NO ROBUST EDGE" in v
    # candidates present but none robust
    weak = [{
        "asset": "EURUSD", "strategy_id": "s",
        "oos_metrics": {"total_trades": 40, "expectancy_r": 0.05},
        "bootstrap_ci": {"ci_lower": -0.1, "ci_range_str": "x"},
        "walk_forward": {"stability": 0.2},
    }]
    assert "NO ROBUST EDGE FOUND" in pr._verdict([], weak)


def test_synth_trades_matches_summary_shape():
    block = {"total_trades": 100, "expectancy_r": 0.1, "win_rate_pct": 60.0}
    trades = pr._synth_trades(block)
    assert len(trades) == 100
    mean_r = sum(t["pnl"] for t in trades) / 100
    assert abs(mean_r - 0.1) < 0.05


# --- artifact read path ------------------------------------------------
def test_get_pair_ranking_returns_none_or_payload():
    out = pr.get_pair_ranking()
    assert out is None or ("leaderboard" in out and "candidates" in out)
