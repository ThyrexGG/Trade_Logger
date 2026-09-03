# -*- coding: utf-8 -*-
"""
Native / near-native Gold revalidation (Phase 73, extended Phase 74).

Runs the frozen Gold contract's entry logic (``ict_2022_sweep_mss_fvg`` =
liquidity sweep -> MSS -> displacement FVG) at the contract's actual timeframes
against **real broker data** (Phase 74: MT5), and labels every result
NATIVE / NEAR_NATIVE / PROXY.

Timeframe roles in the frozen contract (PHASE_21):
    1D bias -> 4H DOL -> 15M setup -> 5M confirm -> 1M FVG limit

    1m  -> NATIVE       (execution timeframe)
    5m  -> NEAR_NATIVE  (confirmation timeframe)
    15m -> NEAR_NATIVE  (setup timeframe)
    1h  -> PROXY
    1d  -> PROXY

**This runs a 3-frame approximation** (base + struct + bias via the existing
backtester), not the literal 5-frame contract, and it uses an independent
dataset. It is therefore an *independent revalidation of the contract's core
logic*, not a reproduction of the frozen holdout — the two are never compared as
if the datasets were the same, and the frozen holdout is never read.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import gold_strategy_baseline as gsb
import historical_data_store as store
import historical_provider as provider
import strategy_discovery as disc

REVAL_STRATEGY_ID = "ict_2022_sweep_mss_fvg"
ARTIFACT_KEY = "native_gold_revalidation"

_TF_ROLE = {
    "1m": ("NATIVE", "execution timeframe of the frozen contract"),
    "5m": ("NEAR_NATIVE", "confirmation timeframe"),
    "15m": ("NEAR_NATIVE", "setup timeframe"),
    "1h": ("PROXY", "coarse proxy"),
    "1d": ("PROXY", "coarse proxy"),
}
_MIN_SPAN_DAYS = 25
_STRONG_NEGATIVE_N = 150


@dataclass
class NativeGoldRevalidation:
    generated_at: str
    strategy_id: str
    frozen_contract_hash: str
    dataset_manifest_id: Optional[str]
    approximation_note: str
    caveat: str
    per_timeframe: List[Dict[str, Any]]
    native_summary: Dict[str, Any]
    frozen_comparison: List[Dict[str, Any]]
    edge_status: str
    edge_status_reason: str
    native_verdict: str
    holdout_untouched: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _evaluate_tf(tf: str, deep: bool = True) -> Dict[str, Any]:
    role, role_note = _TF_ROLE.get(tf, ("PROXY", ""))
    cap = provider.get_provider().capability("XAUUSD", tf)
    cov = store.get_coverage("XAUUSD", tf)
    span_days = (round((cov.last_open_time - cov.first_open_time) / 86400.0, 1)
                if cov.first_open_time and cov.last_open_time else None)

    row: Dict[str, Any] = {
        "timeframe": tf, "role": role, "role_note": role_note,
        "provider_state": cap.state, "provider_reason": cap.reason,
        "vendor_symbol": cap.__dict__.get("vendor_symbol"),
        "stored_bars": cov.count, "stored_span_days": span_days,
    }

    if cov.count < disc._PARTIAL_MIN_BASE_BARS or (span_days or 0) < _MIN_SPAN_DAYS:
        row["state"] = "INSUFFICIENT_HISTORICAL_DEPTH"
        row["reason"] = (f"{cov.count} {tf} bars over ~{span_days or 0:.0f}d — below the "
                         f"exploratory floor. {cap.reason or ''}")
        return row

    r = disc.discover("XAUUSD", REVAL_STRATEGY_ID, tf, allow_partial=True)
    row.update({
        "state": r.state, "data_tier": r.data_tier, "reason": r.reason,
        "dataset_id": r.dataset_id, "dataset_hash": r.dataset_hash,
        "all_metrics": r.all_metrics, "is_metrics": r.is_metrics,
        "oos_metrics": r.oos_metrics, "bootstrap_ci": r.bootstrap_ci,
        "scorecard": (r.scorecard or {}).get("status"),
        "session_breakdown": r.session_breakdown,
        "regime_breakdown": r.regime_breakdown,
        "temporal_breakdown": r.temporal_breakdown,
        "research_ranking_score": disc.research_ranking_score(r),
        "execution_assumptions": r.execution_assumptions,
    })

    # WFO on the contract's own timeframes (1m execution, 15m setup). The
    # 5m/1h/1d proxies don't need it and a 100k-bar WFO is minutes.
    if deep and r.state in ("AVAILABLE", "PARTIAL") and tf in ("1m", "15m"):
        try:
            import pair_ranking
            wfo = pair_ranking.walk_forward("XAUUSD", REVAL_STRATEGY_ID, tf, windows=3)
            row["walk_forward"] = {k: wfo.get(k) for k in
                                   ("state", "stability", "verdict", "stitched_oos")}
            real_r = wfo.get("stitched_oos_r") or []
            if len(real_r) >= 10:
                mc = pair_ranking.monte_carlo([{"pnl": x} for x in real_r], iterations=3000)
                mc["basis"] = "real_wfo_oos_trades"
                row["monte_carlo"] = mc
        except Exception as e:  # pragma: no cover
            row["walk_forward"] = {"state": "ERROR", "reason": repr(e)}
    return row


def _classify(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    native = next((r for r in rows if r["role"] == "NATIVE"), {})
    near = [r for r in rows if r["role"] == "NEAR_NATIVE"
            and r.get("state") in ("AVAILABLE", "PARTIAL")]

    if native.get("state") == "INSUFFICIENT_HISTORICAL_DEPTH":
        return {"edge_status": gsb.EdgeStatus.INSUFFICIENT_EVIDENCE.value,
                "native_state": "INSUFFICIENT_HISTORICAL_DEPTH",
                "verdict": "BLOCKED BY DATA AVAILABILITY at the native 1m timeframe"}

    n_all = (native.get("all_metrics") or {}).get("total_trades", 0)
    e_all = (native.get("all_metrics") or {}).get("expectancy_r")
    oos = native.get("oos_metrics") or {}
    ci = native.get("bootstrap_ci") or {}
    n_oos = oos.get("total_trades", 0)
    ci_low = ci.get("ci_lower")
    ci_up = ci.get("ci_upper")
    wfo_stab = (native.get("walk_forward") or {}).get("stability")

    if e_all is not None and e_all < -0.02 and n_all >= _STRONG_NEGATIVE_N:
        near_pos = any((r["oos_metrics"].get("expectancy_r") or -9) > 0.05
                       and (r["bootstrap_ci"].get("ci_lower") or -9) > 0 for r in near)
        return {
            "edge_status": gsb.EdgeStatus.INVALIDATED.value,
            "native_state": "NO_EDGE",
            "verdict": (
                f"NO NATIVE EDGE — the contract's sweep->MSS->FVG logic run at 1m on an "
                f"independent real dataset (N={n_all}) has NEGATIVE expectancy ({e_all:+.3f}R). "
                + ("Near-native timeframes also show no confirmed edge. " if not near_pos else
                   "A near-native timeframe shows a weak positive — but the native TF does not. ")
                + "This does NOT invalidate the frozen contract's own forward-validation "
                "(untouched); it is an independent test of the same logic on a different "
                "dataset, and it does not support a persistent edge."),
        }

    if (ci_low is not None and ci_low > 0 and n_oos >= 50
            and (wfo_stab or 0) >= 0.5):
        return {"edge_status": gsb.EdgeStatus.VALIDATED.value, "native_state": "VALIDATED",
                "verdict": (f"NATIVE 1m independent revalidation PASSES: OOS E[R] "
                            f"{oos.get('expectancy_r'):+.3f}R, CI lower {ci_low:+.3f}R > 0, "
                            f"N={n_oos}, WFO stability {wfo_stab}. Independent dataset — not a "
                            f"reproduction of the frozen holdout.")}

    if ci_up is not None and ci_up < 0:
        return {"edge_status": gsb.EdgeStatus.INVALIDATED.value, "native_state": "NEGATIVE",
                "verdict": f"NATIVE 1m OOS expectancy negative with CI upper < 0 ({ci_up:+.3f}R)."}

    return {"edge_status": gsb.EdgeStatus.DEGRADED.value, "native_state": "UNCERTAIN",
            "verdict": (f"NATIVE 1m independent revalidation is UNCERTAIN — OOS E[R] "
                        f"{oos.get('expectancy_r')}, CI {ci.get('ci_range_str')}, N={n_oos}, "
                        f"WFO stability {wfo_stab}. Not a confirmed edge; not comparable to the "
                        f"frozen holdout.")}


def _frozen_comparison(native: Dict[str, Any]) -> List[Dict[str, Any]]:
    b = gsb.get_gold_baseline()
    prev = {m.name: m.value for m in b.previous_discovery.metrics}
    oos = native.get("oos_metrics") or {}
    allm = native.get("all_metrics") or {}
    return [
        {"metric": "dataset", "frozen_1m_holdout": "N=82, 1-minute, Phase 19-20 window",
         "independent_native": f"MT5 broker spot, 1m, ~{native.get('stored_span_days')}d, "
                               f"full N={allm.get('total_trades')}",
         "note": "INDEPENDENT DATASETS — not comparable as a delta"},
        {"metric": "expectancy_r", "frozen_1m_holdout": prev.get("holdout_expectancy_r"),
         "independent_native": oos.get("expectancy_r"),
         "note": "frozen = final holdout; native = OOS split of the independent set"},
        {"metric": "win_rate_pct", "frozen_1m_holdout": prev.get("holdout_win_rate_pct"),
         "independent_native": oos.get("win_rate_pct"), "note": ""},
        {"metric": "profit_factor", "frozen_1m_holdout": prev.get("holdout_profit_factor"),
         "independent_native": oos.get("profit_factor"), "note": ""},
        {"metric": "sample_n", "frozen_1m_holdout": 82,
         "independent_native": allm.get("total_trades"), "note": ""},
    ]


def revalidate(deep: bool = True) -> NativeGoldRevalidation:
    disc.clear_prepare_cache()
    baseline = gsb.get_gold_baseline()

    manifest_id = None
    try:
        import dataset_manifest
        manifest_id = dataset_manifest.build_and_persist("XAUUSD").dataset_id
    except Exception:
        pass

    rows = [_evaluate_tf(tf, deep=deep) for tf in ("1m", "5m", "15m", "1h", "1d")]
    native = next((r for r in rows if r["role"] == "NATIVE"), {})
    cls = _classify(rows)

    return NativeGoldRevalidation(
        generated_at=datetime.now(timezone.utc).isoformat(),
        strategy_id=REVAL_STRATEGY_ID,
        frozen_contract_hash=baseline.frozen_contract_hash,
        dataset_manifest_id=manifest_id,
        approximation_note=(
            "3-frame approximation (base + struct + bias via the existing backtester), NOT the "
            "literal 5-frame 1D->4H->15M->5M->1M contract. Independent revalidation of the "
            "contract's core sweep->MSS->FVG logic."),
        caveat=(
            "NATIVE = the frozen contract's execution timeframe. NEAR_NATIVE = its setup/confirm "
            "timeframe. PROXY = coarser. This is an INDEPENDENT dataset (MT5 broker spot) — never "
            "compared to the frozen N=82 / +0.637R holdout as a delta, and the holdout is never "
            "read."),
        per_timeframe=rows,
        native_summary={
            "state": cls["native_state"],
            "oos": native.get("oos_metrics"),
            "all": native.get("all_metrics"),
            "bootstrap_ci": native.get("bootstrap_ci"),
            "walk_forward": native.get("walk_forward"),
            "monte_carlo": native.get("monte_carlo"),
            "scorecard": native.get("scorecard"),
        },
        frozen_comparison=_frozen_comparison(native),
        edge_status=cls["edge_status"],
        edge_status_reason=cls["verdict"],
        native_verdict=cls["verdict"],
    )


def persist(reval: Optional[NativeGoldRevalidation] = None) -> str:
    reval = reval or revalidate()
    return store.save_artifact(ARTIFACT_KEY, "native_gold_revalidation", reval.to_dict())


def get_native_revalidation() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    store.register_with_phase68()
    try:
        import mt5_provider  # noqa: F401 - registers itself if configured
    except Exception:
        pass
    r = revalidate()
    print("\n=== NATIVE / NEAR-NATIVE XAUUSD REVALIDATION (Phase 74) ===")
    print(r.caveat)
    print(r.approximation_note)
    print(f"\n{'TF':<4} {'ROLE':<12} {'STATE':<26} {'BARS':>8} {'SPAN(d)':>8} "
          f"{'OOS E[R]':>9} {'N':>5} {'ALL E[R]':>9} {'WFO':>5} CARD")
    for row in r.per_timeframe:
        oos = row.get("oos_metrics", {}) or {}
        allm = row.get("all_metrics", {}) or {}
        wf = (row.get("walk_forward") or {}).get("stability")
        print(f"{row['timeframe']:<4} {row['role']:<12} {row['state']:<26} "
              f"{row.get('stored_bars', 0):>8} {str(row.get('stored_span_days') or '-'):>8} "
              f"{str(oos.get('expectancy_r', '-')):>9} {str(oos.get('total_trades', '-')):>5} "
              f"{str(allm.get('expectancy_r', '-')):>9} {str(wf or '-'):>5} {row.get('scorecard', '-')}")
    print("\nFROZEN vs INDEPENDENT NATIVE (independent datasets — not a delta):")
    for c in r.frozen_comparison:
        print(f"  {c['metric']:<16} frozen={c['frozen_1m_holdout']!s:<28} native={c['independent_native']}")
    print(f"\nEDGE STATUS: {r.edge_status}")
    print(f"NATIVE VERDICT: {r.native_verdict}")
    h = persist(r)
    print(f"artifact: {ARTIFACT_KEY} @ {h[:12]}  |  dataset: {r.dataset_manifest_id}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = ["NativeGoldRevalidation", "revalidate", "persist", "get_native_revalidation",
           "REVAL_STRATEGY_ID", "ARTIFACT_KEY"]
