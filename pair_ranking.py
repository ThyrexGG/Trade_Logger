# -*- coding: utf-8 -*-
"""
Pair x Strategy ranking & robustness (Phase 70).

Orchestrates ``strategy_discovery`` across the research universe, layers the
robustness checks (walk-forward, Monte Carlo, parameter sensitivity, temporal &
pair stability) on the promising candidates, and produces a single reproducible
leaderboard artifact.

Compute is expensive and MUST NOT run on an API request (§60). This module is
run offline:

    python -m pair_ranking --timeframe 1h                 # quick (discovery only)
    python -m pair_ranking --timeframe 1h --deep          # + WFO / MC / sensitivity

It persists to ``research_artifacts`` key ``pair_ranking``; the API only reads
that snapshot.

Ranking is NOT by raw profit (§21). The sort key is ``ResearchRankingScore``
(decomposable, every component visible — §22), and a candidate below the sample
floor is ``INSUFFICIENT_EVIDENCE``, never ranked on a tiny sample (§23).
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import backtester
import historical_data_store as store
import research_universe
import strategy_discovery as disc

ARTIFACT_KEY = "pair_ranking"
CODE_VERSION = "phase70.1"

# A candidate must clear this before robustness compute is spent on it.
_PROMISING_MIN_OOS_TRADES = 30
_PROMISING_MIN_OOS_EXPECTANCY = 0.0


# ==========================================================================
# Robustness layers
# ==========================================================================
def walk_forward(asset: str, strategy_id: str, timeframe: str = "1h",
                 windows: int = 3, oos_frac: float = 0.30,
                 coarse: bool = True) -> Dict[str, Any]:
    """Store-based walk-forward: split the base series into `windows` chronological
    slices; for each, grid-search sl/tp on the in-sample head and apply the best
    to the out-of-sample tail; stitch the OOS trades. A strategy that only works
    in one window is visibly penalised via `stability`."""
    sdef = disc.STRATEGY_DEFINITIONS.get(strategy_id)
    prepared, suf = disc.prepare_data(asset, timeframe)
    if prepared is None or sdef is None:
        return {"state": "INSUFFICIENT_EVIDENCE", "reason": suf.get("reason", "no data")}

    df = prepared.df
    n = len(df)
    step = n // windows
    if step < 400:
        return {"state": "INSUFFICIENT_EVIDENCE", "reason": f"window size {step} bars too small"}

    inst = research_universe.get_instrument(asset)
    fixed_spread = inst.pip_size * disc.SPREAD_PIPS
    slippage = inst.pip_size * disc.SLIPPAGE_PIPS
    if coarse:
        # 4 corner + centre combos instead of the full 3x3 — keeps a --deep run
        # tractable on the O(n*window) SMC strategies (TECHNICAL_DEBT P2-10).
        grid = [(1.0, 2.0), (1.5, 2.5), (2.0, 3.0), (1.0, 3.0), (2.0, 4.0)]
    else:
        grid = [(s, t) for s in sdef.parameter_schema["sl_atr"]["grid"]
                for t in sdef.parameter_schema["tp_atr"]["grid"]]

    per_window: List[Dict[str, Any]] = []
    stitched_r: List[float] = []
    for w in range(windows):
        a = w * step
        b = n if w == windows - 1 else (w + 1) * step
        sl_df = df.iloc[a:b]
        is_end = int(len(sl_df) * (1 - oos_frac))
        df_is, df_oos = sl_df.iloc[:is_end], sl_df.iloc[is_end:]
        if len(df_is) < 250 or len(df_oos) < 60:
            continue

        best, best_exp = None, -1e9
        for (s, t) in grid:
            r = backtester.run_backtest(
                symbol=asset, timeframe=timeframe, strategy=sdef.registry_name,
                sl_atr=s, tp_atr=t, slippage=slippage, commission_pct=disc.COMMISSION_PCT,
                fixed_spread=fixed_spread, train_split=1.0,
                preloaded_data={"df": df_is, "df_struct": prepared.df_struct,
                                "df_bias": prepared.df_bias})
            if "error" in r:
                continue
            m = disc._metric_block(r.get("trades", []))
            if m.get("total_trades", 0) >= 8 and m.get("expectancy_r", -9) > best_exp:
                best, best_exp = (s, t), m["expectancy_r"]
        if best is None:
            per_window.append({"window": w, "state": "NO_IS_EDGE"})
            continue

        r_oos = backtester.run_backtest(
            symbol=asset, timeframe=timeframe, strategy=sdef.registry_name,
            sl_atr=best[0], tp_atr=best[1], slippage=slippage,
            commission_pct=disc.COMMISSION_PCT, fixed_spread=fixed_spread, train_split=1.0,
            preloaded_data={"df": df_oos, "df_struct": prepared.df_struct,
                            "df_bias": prepared.df_bias})
        oos_trades = [] if "error" in r_oos else r_oos.get("trades", [])
        m_oos = disc._metric_block(oos_trades)
        stitched_r.extend(disc._r_multiples(oos_trades))
        per_window.append({"window": w, "best_params": {"sl_atr": best[0], "tp_atr": best[1]},
                           "is_expectancy_r": round(best_exp, 3),
                           "oos_expectancy_r": m_oos.get("expectancy_r"),
                           "oos_trades": m_oos.get("total_trades", 0)})

    positive = [w for w in per_window if isinstance(w.get("oos_expectancy_r"), (int, float))
                and w["oos_expectancy_r"] > 0]
    scored = [w for w in per_window if isinstance(w.get("oos_expectancy_r"), (int, float))]
    stability = round(len(positive) / len(scored), 2) if scored else 0.0
    stitched = disc._metric_block(
        [{"pnl": r, "entry_price": 1.0, "stop_loss": 0.0, "position_size": 1.0} for r in stitched_r]
    ) if stitched_r else {"total_trades": 0}
    return {
        "state": "AVAILABLE" if scored else "INSUFFICIENT_EVIDENCE",
        "windows": per_window,
        "stability": stability,
        "verdict": ("ROBUST" if stability >= 0.75 else "FRAGILE" if stability >= 0.5 else "UNSTABLE"),
        "stitched_oos": stitched,
        # P2-11 (Phase 73): the real per-trade OOS R sequence, so Monte Carlo runs
        # on actual trade outcomes rather than a synthesised list.
        "stitched_oos_r": [round(r, 4) for r in stitched_r],
    }


def monte_carlo(trades: List[Dict[str, Any]], iterations: int = 5000) -> Dict[str, Any]:
    if not trades or len(trades) < 10:
        return {"state": "INSUFFICIENT_EVIDENCE", "reason": "fewer than 10 trades"}
    mc = backtester.run_monte_carlo(trades, iterations=iterations)
    if "error" in mc:
        return {"state": "INSUFFICIENT_EVIDENCE", "reason": mc["error"]}
    mc["state"] = "AVAILABLE"
    return mc


def parameter_sensitivity(asset: str, strategy_id: str, timeframe: str = "1h",
                          base_params: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Perturb sl_atr / tp_atr by +/-10% and +/-20% and check the neighbourhood
    stays profitable. Profit vanishing on a tiny change => OVERFIT_RISK HIGH."""
    sdef = disc.STRATEGY_DEFINITIONS.get(strategy_id)
    if sdef is None:
        return {"state": "INSUFFICIENT_EVIDENCE"}
    base = {**sdef.defaults(), **(base_params or {})}
    results = []
    positive = 0
    total = 0
    for pname in ("sl_atr", "tp_atr"):
        for mult in (0.8, 0.9, 1.0, 1.1, 1.2):
            p = dict(base)
            p[pname] = round(base[pname] * mult, 3)
            r = disc.discover(asset, strategy_id, timeframe, params=p)
            exp = r.all_metrics.get("expectancy_r")
            if r.state == "AVAILABLE" and exp is not None:
                total += 1
                if exp > 0:
                    positive += 1
            results.append({"param": pname, "mult": mult, "value": p[pname],
                            "expectancy_r": exp, "trades": r.all_metrics.get("total_trades", 0),
                            "state": r.state})
    ratio = round(positive / total, 2) if total else 0.0
    return {
        "state": "AVAILABLE" if total >= 4 else "INSUFFICIENT_EVIDENCE",
        "grid": results,
        "neighbourhood_positive_ratio": ratio,
        "overfit_risk": "LOW" if ratio >= 0.8 else "MODERATE" if ratio >= 0.5 else "HIGH",
    }


def classify_pair_stability(per_asset: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """A strategy that only works on Gold is fine (§29) — just classify it."""
    positive = []
    for sym, res in per_asset.items():
        oos = res.get("oos_metrics", {})
        if res.get("state") == "AVAILABLE" and (oos.get("expectancy_r") or -9) > 0.03 \
                and (res.get("bootstrap_ci", {}).get("ci_lower") or -9) > 0:
            positive.append(sym)
    fx = [s for s in positive if research_universe.classify(s) in ("FX_MAJOR", "FX_CROSS")]
    jpy = [s for s in positive if s.endswith("JPY") or s == "USDJPY"]
    metal = [s for s in positive if research_universe.classify(s) == "METAL"]
    if not positive:
        klass = "NO_EDGE_ANYWHERE"
    elif set(positive) == {"XAUUSD"}:
        klass = "GOLD_SPECIFIC_EDGE"
    elif len(jpy) >= 2 and len(fx) == len(jpy):
        klass = "JPY_FAMILY_EDGE"
    elif len(fx) >= 4:
        klass = "FX_WIDE_EDGE"
    elif len(positive) >= 3:
        klass = "MULTI_ASSET_EDGE"
    else:
        klass = "NARROW_EDGE"
    return {"class": klass, "positive_instruments": positive,
            "fx": fx, "jpy_family": jpy, "metal": metal}


# ==========================================================================
# Full ranking
# ==========================================================================
@dataclass
class RankingRun:
    generated_at: str
    code_version: str
    timeframe: str
    deep: bool
    execution_assumptions: Dict[str, Any]
    universe: List[str]
    strategies: List[str]
    store_coverage: List[Dict[str, Any]]
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    pair_stability: Dict[str, Any] = field(default_factory=dict)
    leaderboard: List[Dict[str, Any]] = field(default_factory=list)
    verdict: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def compute_pair_ranking(instruments: Optional[List[str]] = None,
                         strategy_ids: Optional[List[str]] = None,
                         timeframe: str = "1h", deep: bool = False,
                         param_grid: bool = True, deep_top: int = 8) -> RankingRun:
    instruments = instruments or list(research_universe.RESEARCH_UNIVERSE)
    strategy_ids = strategy_ids or list(disc.STRATEGY_DEFINITIONS.keys())
    disc.clear_prepare_cache()  # fresh candle pulls for this run

    run = RankingRun(
        generated_at=datetime.now(timezone.utc).isoformat(),
        code_version=CODE_VERSION, timeframe=timeframe, deep=deep,
        execution_assumptions=disc._assumptions(0.0, 0.0),
        universe=instruments, strategies=strategy_ids,
        store_coverage=[c for c in store.list_available() if c["timeframe"] == timeframe],
    )

    per_strategy_assets: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for sid in strategy_ids:
        sdef = disc.STRATEGY_DEFINITIONS[sid]
        grids = [(sdef.defaults())]
        if param_grid:
            grids = [{"sl_atr": s, "tp_atr": t}
                     for s in sdef.parameter_schema["sl_atr"]["grid"]
                     for t in sdef.parameter_schema["tp_atr"]["grid"]]
        for asset in instruments:
            best_result = None
            best_key = -1e9
            for params in grids:
                r = disc.discover(asset, sid, timeframe, params=params)
                if r.state != "AVAILABLE":
                    if best_result is None:
                        best_result = r
                    continue
                # select by OOS lower-confidence-bound, not raw profit (§21)
                key = r.bootstrap_ci.get("ci_lower", -9)
                if key > best_key:
                    best_key, best_result = key, r
            per_strategy_assets.setdefault(sid, {})[asset] = best_result.to_dict()

            cand = {
                "strategy_id": sid, "strategy_family": sdef.family, "asset": asset,
                "timeframe": timeframe, "state": best_result.state,
                "params": best_result.params,
                "oos_metrics": best_result.oos_metrics,
                "all_metrics": best_result.all_metrics,
                "bootstrap_ci": best_result.bootstrap_ci,
                "scorecard": best_result.scorecard,
                "dataset_hash": best_result.dataset_hash,
                "session_breakdown": best_result.session_breakdown,
                "regime_breakdown": best_result.regime_breakdown,
                "temporal_breakdown": best_result.temporal_breakdown,
            }

            cand["_promising"] = (
                best_result.state == "AVAILABLE"
                and best_result.oos_metrics.get("total_trades", 0) >= _PROMISING_MIN_OOS_TRADES
                and best_result.oos_metrics.get("expectancy_r", -9) > _PROMISING_MIN_OOS_EXPECTANCY
            )
            cand["research_ranking_score"] = disc.research_ranking_score(best_result, None)
            run.candidates.append(cand)

    # pair stability per strategy
    run.pair_stability = {
        sid: classify_pair_stability(assets) for sid, assets in per_strategy_assets.items()
    }

    # Deep robustness (§25-§27) on only the top `deep_top` promising candidates by
    # the preliminary RankingScore — a full-universe deep run is hours (P2-10).
    if deep:
        promising = [c for c in run.candidates if c.pop("_promising", False)
                     and c["research_ranking_score"].get("score") is not None]
        promising.sort(key=lambda c: c["research_ranking_score"]["score"], reverse=True)
        for cand in promising[:deep_top]:
            asset, sid = cand["asset"], cand["strategy_id"]
            wfo = walk_forward(asset, sid, timeframe)
            cand["walk_forward"] = wfo
            wfo_stab = wfo.get("stability")
            # P2-11 fix: Monte Carlo on the real per-trade OOS R sequence from WFO.
            real_r = wfo.get("stitched_oos_r") or []
            if len(real_r) >= 10:
                cand["monte_carlo"] = monte_carlo(
                    [{"pnl": r} for r in real_r], iterations=3000)
                cand["monte_carlo"]["basis"] = "real_wfo_oos_trades"
            else:
                cand["monte_carlo"] = {"state": "INSUFFICIENT_EVIDENCE",
                                       "reason": f"only {len(real_r)} stitched OOS trades",
                                       "basis": "none"}
            cand["parameter_sensitivity"] = parameter_sensitivity(
                asset, sid, timeframe, cand["params"])
            best = disc.discover(asset, sid, timeframe, params=cand["params"])
            cand["research_ranking_score"] = disc.research_ranking_score(best, wfo_stab)
    for c in run.candidates:
        c.pop("_promising", None)

    # leaderboard — only scored candidates, sorted by ResearchRankingScore desc
    scored = [c for c in run.candidates
              if c.get("research_ranking_score", {}).get("score") is not None]
    scored.sort(key=lambda c: c["research_ranking_score"]["score"], reverse=True)
    run.leaderboard = [
        {
            "rank": i + 1, "asset": c["asset"], "strategy_id": c["strategy_id"],
            "strategy_family": c["strategy_family"],
            "oos_expectancy_r": c["oos_metrics"].get("expectancy_r"),
            "oos_profit_factor": c["oos_metrics"].get("profit_factor"),
            "oos_win_rate_pct": c["oos_metrics"].get("win_rate_pct"),
            "oos_trades": c["oos_metrics"].get("total_trades"),
            "oos_ci": c["bootstrap_ci"].get("ci_range_str"),
            "research_ranking_score": c["research_ranking_score"]["score"],
            "scorecard": c["scorecard"].get("status"),
            "wfo_stability": c.get("walk_forward", {}).get("stability"),
        }
        for i, c in enumerate(scored)
    ]
    run.verdict = _verdict(run.leaderboard, scored)
    return run


def base_result_params(r: "disc.DiscoveryResult") -> Dict[str, float]:
    return dict(r.params)


def _synth_trades(metric_block: Dict[str, Any]) -> List[Dict[str, Any]]:
    """DEPRECATED (Phase 73 / P2-11). No longer used in the ranking pipeline —
    Monte Carlo now runs on ``walk_forward()['stitched_oos_r']``, the real
    per-trade OOS R sequence. Kept only for the shape test / ad-hoc use; a
    synthesised list must never be labelled native trade-level evidence."""
    n = metric_block.get("total_trades", 0)
    if not n:
        return []
    exp = metric_block.get("expectancy_r", 0.0)
    wr = (metric_block.get("win_rate_pct", 50.0)) / 100.0
    win_r = 2.0
    # solve loss so that wr*win_r + (1-wr)*loss = exp
    loss_r = (exp - wr * win_r) / max(1e-9, (1 - wr))
    out = []
    for i in range(n):
        r = win_r if i < round(wr * n) else loss_r
        out.append({"pnl": r})
    return out


def _verdict(_leaderboard: List[Dict[str, Any]], scored: List[Dict[str, Any]]) -> str:
    robust = [c for c in scored
              if (c["bootstrap_ci"].get("ci_lower") or -9) > 0
              and c["oos_metrics"].get("total_trades", 0) >= 50
              and (c.get("walk_forward", {}).get("stability") or 0) >= 0.5]
    if not scored:
        return "NO CANDIDATE CLEARED THE SAMPLE FLOOR — INSUFFICIENT_EVIDENCE across the universe"
    if not robust:
        return ("NO ROBUST EDGE FOUND — candidates exist but none clears positive OOS lower-CI "
                "+ N>=50 + WFO stability >= 0.5 on the current data")
    top = robust[0]
    return (f"STRONGEST VALIDATED RESEARCH EDGE: {top['asset']} / {top['strategy_id']} "
            f"(OOS E[R] {top['oos_metrics'].get('expectancy_r')}R, "
            f"CI {top['bootstrap_ci'].get('ci_range_str')})")


def persist(run: RankingRun) -> str:
    return store.save_artifact(ARTIFACT_KEY, "pair_ranking", run.to_dict())


def get_pair_ranking() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="TradeLogger pair x strategy ranking (Phase 70)")
    p.add_argument("--timeframe", default="1h")
    p.add_argument("--deep", action="store_true", help="also run WFO / Monte Carlo / sensitivity")
    p.add_argument("--deep-top", type=int, default=8, help="deep robustness on the top-N candidates")
    p.add_argument("--assets", help="comma list; default = whole universe")
    p.add_argument("--strategies", help="comma list of strategy ids; default = all")
    p.add_argument("--no-grid", action="store_true", help="default params only (fast)")
    args = p.parse_args(argv)

    store.register_with_phase68()
    run = compute_pair_ranking(
        instruments=[s.strip().upper() for s in args.assets.split(",")] if args.assets else None,
        strategy_ids=[s.strip() for s in args.strategies.split(",")] if args.strategies else None,
        timeframe=args.timeframe, deep=args.deep, param_grid=not args.no_grid,
        deep_top=args.deep_top,
    )
    h = persist(run)
    print(f"\n=== PAIR x STRATEGY LEADERBOARD ({args.timeframe}, "
          f"{'deep' if args.deep else 'quick'}) ===")
    print(f"{'#':>2}  {'ASSET':<8} {'STRATEGY':<26} {'OOS E[R]':>9} {'PF':>6} "
          f"{'WR%':>6} {'N':>5} {'RRS':>6}  CARD")
    for row in run.leaderboard[:25]:
        print(f"{row['rank']:>2}  {row['asset']:<8} {row['strategy_id']:<26} "
              f"{str(row['oos_expectancy_r']):>9} {str(row['oos_profit_factor']):>6} "
              f"{str(row['oos_win_rate_pct']):>6} {str(row['oos_trades']):>5} "
              f"{str(row['research_ranking_score']):>6}  {row['scorecard']}")
    print(f"\nVERDICT: {run.verdict}")
    print(f"artifact: {ARTIFACT_KEY} @ {h[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
