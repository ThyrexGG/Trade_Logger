# -*- coding: utf-8 -*-
"""
Gold (XAUUSD) strategy revalidation (Phase 71, §30/§31).

Runs the frozen Gold contract's *closest available approximation* through the
Phase-70 discovery + robustness pipeline on the timeframes the Phase-69 store can
actually supply (1h / 1d), and produces the old-vs-new comparison.

**Timeframe-substitution caveat (stated up front, not buried):**
the frozen contract executes on **1-minute** structure with tight structural
stops. yfinance provides ~7 days of 1m data (Phase 68 P1-6), so a like-for-like
revalidation of the N=82 / +0.637R / 1-minute holdout is **not possible**. This
module runs the sweep + MSS + FVG logic on **1h** (struct 4h, bias 1d) and **1d**
as the nearest defensible proxy and reports the substitution explicitly. It never
claims equivalence to the frozen holdout, and it never touches the holdout.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import gold_strategy_baseline as gsb
import historical_data_store as store
import pair_ranking
import strategy_discovery as disc

# The registry strategy that most closely matches the frozen contract's
# entry logic (15M liquidity sweep -> MSS -> displacement FVG retrace).
REVAL_STRATEGY_ID = "ict_2022_sweep_mss_fvg"
REVAL_TIMEFRAMES = ("1h", "1d")
ARTIFACT_KEY = "gold_revalidation"


@dataclass
class GoldRevalidation:
    generated_at: str
    strategy_id: str
    approximated_contract: str
    timeframe_substitution_note: str
    frozen_contract_hash: str
    per_timeframe: Dict[str, Dict[str, Any]]
    walk_forward: Dict[str, Any]
    comparison: List[Dict[str, Any]]
    edge_status: str
    edge_status_reason: str
    verdict: str
    holdout_untouched: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _compare_row(metric: str, old: Optional[float], new: Optional[float],
                 unit: str, better: str = "higher") -> Dict[str, Any]:
    diff = None
    interp = "no comparable new value"
    if old is not None and new is not None:
        diff = round(new - old, 3)
        if better == "higher":
            interp = ("new is materially lower" if diff < -0.15
                      else "new is broadly in line" if abs(diff) <= 0.15
                      else "new is higher")
        else:
            interp = ("new is materially worse" if diff > 0.15
                      else "new is broadly in line" if abs(diff) <= 0.15
                      else "new is better")
    return {"metric": metric, "old": old, "new": new, "unit": unit,
            "difference": diff, "interpretation": interp}


def revalidate() -> GoldRevalidation:
    disc.clear_prepare_cache()
    baseline = gsb.get_gold_baseline()
    prev = {m.name: m.value for m in baseline.previous_discovery.metrics}
    holdout_n = float(baseline.previous_discovery.holdout_sample_n)

    per_tf: Dict[str, Dict[str, Any]] = {}
    for tf in REVAL_TIMEFRAMES:
        r = disc.discover("XAUUSD", REVAL_STRATEGY_ID, tf)
        rs = disc.research_ranking_score(r)
        per_tf[tf] = {
            "state": r.state,
            "reason": r.reason,
            "dataset_id": r.dataset_id,
            "dataset_hash": r.dataset_hash,
            "all_metrics": r.all_metrics,
            "is_metrics": r.is_metrics,
            "oos_metrics": r.oos_metrics,
            "bootstrap_ci": r.bootstrap_ci,
            "scorecard": r.scorecard,
            "session_breakdown": r.session_breakdown,
            "regime_breakdown": r.regime_breakdown,
            "temporal_breakdown": r.temporal_breakdown,
            "research_ranking_score": rs,
            "execution_assumptions": r.execution_assumptions,
        }

    wfo = pair_ranking.walk_forward("XAUUSD", REVAL_STRATEGY_ID, "1h")

    # old-vs-new on the metrics that have any comparability
    h1 = per_tf.get("1h", {})
    oos = h1.get("oos_metrics", {}) or {}
    all_m = h1.get("all_metrics", {}) or {}
    comparison = [
        _compare_row("expectancy_r (holdout vs 1h OOS)", prev.get("holdout_expectancy_r"),
                     oos.get("expectancy_r"), "R"),
        _compare_row("win_rate_pct", prev.get("holdout_win_rate_pct"),
                     oos.get("win_rate_pct"), "%"),
        _compare_row("profit_factor", prev.get("holdout_profit_factor"),
                     oos.get("profit_factor"), "ratio"),
        _compare_row("max_drawdown_r", prev.get("holdout_max_drawdown_r"),
                     oos.get("max_drawdown_r"), "R", better="lower"),
        _compare_row("sample_n (holdout vs 1h all)", holdout_n,
                     float(all_m.get("total_trades") or 0) or None, "trades"),
    ]

    edge_status, reason, verdict = _classify(per_tf, wfo)

    return GoldRevalidation(
        generated_at=datetime.now(timezone.utc).isoformat(),
        strategy_id=REVAL_STRATEGY_ID,
        approximated_contract="Phase-21 XAUUSD True MTF ICT/SMC (1D->4H->15M->5M->1M FVG limit)",
        timeframe_substitution_note=(
            "Frozen contract executes on 1-minute structure. yfinance supplies ~7 days of 1m "
            "(P1-6), so the N=82 / +0.637R holdout cannot be reproduced. This revalidation runs "
            "the sweep+MSS+FVG logic on 1h (struct 4h, bias 1d) and 1d as the nearest available "
            "proxy. It is NOT equivalent to the frozen holdout."
        ),
        frozen_contract_hash=baseline.frozen_contract_hash,
        per_timeframe=per_tf,
        walk_forward=wfo,
        comparison=comparison,
        edge_status=edge_status,
        edge_status_reason=reason,
        verdict=verdict,
    )


def _classify(per_tf: Dict[str, Dict[str, Any]], wfo: Dict[str, Any]):
    h1 = per_tf.get("1h", {})
    oos = h1.get("oos_metrics", {}) or {}
    ci = h1.get("bootstrap_ci", {}) or {}
    n_oos = oos.get("total_trades", 0)
    ci_low = ci.get("ci_lower")
    exp = oos.get("expectancy_r")
    stability = wfo.get("stability")

    if h1.get("state") != "AVAILABLE" or n_oos < 20:
        return (gsb.EdgeStatus.INSUFFICIENT_EVIDENCE.value,
                f"1h OOS sample is {n_oos} trades (< 20) — cannot revalidate on available data; "
                f"native 1m revalidation needs an intraday provider.",
                "UNVERIFIABLE ON AVAILABLE DATA")

    if exp is not None and exp <= 0 and (ci.get("ci_upper") or 1) < 0:
        return (gsb.EdgeStatus.INVALIDATED.value,
                f"1h approximation has negative OOS expectancy ({exp:+.3f}R) with CI upper < 0.",
                "APPROXIMATION FAILED ON 1h — native contract UNVERIFIABLE")

    if ci_low is not None and ci_low > 0 and n_oos >= 50 and (stability or 0) >= 0.5:
        return (gsb.EdgeStatus.VALIDATED.value,
                f"1h approximation: OOS E[R] {exp:+.3f}R, CI lower {ci_low:+.3f}R > 0, N={n_oos}, "
                f"WFO stability {stability}. NOTE: this is a timeframe substitution, not the frozen contract.",
                "1h APPROXIMATION VALIDATED (timeframe-substituted — not the frozen 1m holdout)")

    return (gsb.EdgeStatus.DEGRADED.value,
            f"1h approximation shows a weak/uncertain edge (OOS E[R] {exp}, CI lower {ci_low}, "
            f"N={n_oos}, WFO stability {stability}). Positive but not statistically confirmed; "
            f"far below the frozen +0.637R holdout. The native 1m contract remains UNVERIFIABLE.",
            "DEGRADED / UNVERIFIABLE — 1h proxy weak-positive, native contract not testable on available data")


def persist_revalidation(reval: Optional[GoldRevalidation] = None) -> str:
    reval = reval or revalidate()
    return store.save_artifact(ARTIFACT_KEY, "gold_revalidation", reval.to_dict())


def get_revalidation() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:
    store.register_with_phase68()
    reval = revalidate()
    h = persist_revalidation(reval)
    print("\n=== XAUUSD REVALIDATION (Phase 71) ===")
    print(reval.timeframe_substitution_note)
    print("\nmetric                                   old        new     diff  interpretation")
    print("-" * 92)
    for row in reval.comparison:
        print(f"{row['metric']:<40} {str(row['old']):>8} {str(row['new']):>10} "
              f"{str(row['difference']):>8}  {row['interpretation']}")
    for tf, d in reval.per_timeframe.items():
        oos = d.get("oos_metrics", {})
        print(f"\n{tf}: state={d['state']} OOS E[R]={oos.get('expectancy_r')} "
              f"PF={oos.get('profit_factor')} N={oos.get('total_trades')} "
              f"CI={d.get('bootstrap_ci', {}).get('ci_range_str')} card={d.get('scorecard', {}).get('status')}")
    print(f"\nWFO stability: {reval.walk_forward.get('stability')} "
          f"({reval.walk_forward.get('verdict')})")
    print(f"\nEDGE STATUS: {reval.edge_status}")
    print(f"VERDICT: {reval.verdict}")
    print(f"artifact: {ARTIFACT_KEY} @ {h[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())
