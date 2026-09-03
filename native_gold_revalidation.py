# -*- coding: utf-8 -*-
"""
Native / near-native Gold revalidation (Phase 73, §11/§12/§21).

Phase 71 revalidated the frozen Gold contract's entry logic on **1h** as a
*proxy*. This module pushes to the contract's actual timeframes — **15m setup,
5m confirmation, 1m execution** — using whatever real intraday data the wired
provider (yfinance) can supply, and labels every result NATIVE / NEAR_NATIVE /
PROXY. It never claims a proxy is native and never fabricates candles.

Timeframe roles in the frozen contract (PHASE_21):
    1D bias -> 4H DOL -> 15M setup (sweep+MSS+FVG) -> 5M confirm -> 1M FVG limit

    1m  -> NATIVE       (the execution timeframe)
    5m  -> NEAR_NATIVE  (confirmation timeframe)
    15m -> NEAR_NATIVE  (setup timeframe — closest testable proxy for the contract)
    1h  -> PROXY        (Phase 71)
    1d  -> PROXY

yfinance depth (probed 2026-09, GC=F): 1m ~8d, 5m ~70d, 15m ~70d. None reaches a
statistically valid sample, so the native question resolves to
``INSUFFICIENT_HISTORICAL_DEPTH``; the 15m/5m reads are exploratory PARTIAL only.
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
    "15m": ("NEAR_NATIVE", "setup timeframe — closest testable proxy for the contract"),
    "1h": ("PROXY", "Phase 71 proxy"),
    "1d": ("PROXY", "coarse proxy"),
}


@dataclass
class NativeGoldRevalidation:
    generated_at: str
    strategy_id: str
    frozen_contract_hash: str
    caveat: str
    per_timeframe: List[Dict[str, Any]]
    best_available: Dict[str, Any]
    edge_status: str
    edge_status_reason: str
    native_verdict: str
    holdout_untouched: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _evaluate_tf(tf: str) -> Dict[str, Any]:
    role, role_note = _TF_ROLE.get(tf, ("PROXY", ""))
    cap = provider.get_provider().capability("XAUUSD", tf)
    cov = store.get_coverage("XAUUSD", tf)

    row: Dict[str, Any] = {
        "timeframe": tf,
        "role": role,
        "role_note": role_note,
        "provider_state": cap.state,
        "provider_reason": cap.reason,
        "stored_bars": cov.count,
        "stored_span_days": (round((cov.last_open_time - cov.first_open_time) / 86400.0, 1)
                             if cov.first_open_time and cov.last_open_time else None),
    }

    span_days = row["stored_span_days"] or 0
    # An exploratory PARTIAL read needs a real *calendar* window, not just a bar
    # count. 1m at ~7d fails this even though it has thousands of bars.
    _MIN_SPAN_DAYS = 25
    if cov.count < disc._PARTIAL_MIN_BASE_BARS or span_days < _MIN_SPAN_DAYS:
        row["state"] = "INSUFFICIENT_HISTORICAL_DEPTH"
        row["reason"] = (
            f"{cov.count} {tf} bars over ~{span_days:.0f}d (need >= "
            f"{disc._PARTIAL_MIN_BASE_BARS} bars AND >= {_MIN_SPAN_DAYS}d for an exploratory "
            f"read). {cap.reason or 'provider cannot supply more.'}")
        return row

    r = disc.discover("XAUUSD", REVAL_STRATEGY_ID, tf, allow_partial=True)
    row["state"] = r.state
    row["data_tier"] = r.data_tier
    row["reason"] = r.reason
    row["dataset_id"] = r.dataset_id
    row["dataset_hash"] = r.dataset_hash
    row["all_metrics"] = r.all_metrics
    row["oos_metrics"] = r.oos_metrics
    row["bootstrap_ci"] = r.bootstrap_ci
    row["scorecard"] = (r.scorecard or {}).get("status")
    row["session_breakdown"] = r.session_breakdown
    row["regime_breakdown"] = r.regime_breakdown
    row["research_ranking_score"] = disc.research_ranking_score(r)
    return row


def revalidate() -> NativeGoldRevalidation:
    disc.clear_prepare_cache()
    baseline = gsb.get_gold_baseline()

    rows = [_evaluate_tf(tf) for tf in ("1m", "5m", "15m", "1h", "1d")]

    # best-available real evidence = the finest timeframe that actually produced a
    # backtest with a usable trade count
    usable = [r for r in rows
              if r.get("state") in ("PARTIAL", "AVAILABLE")
              and (r.get("all_metrics") or {}).get("total_trades", 0) >= 20]
    best = usable[0] if usable else {}

    native_row = next((r for r in rows if r["role"] == "NATIVE"), {})
    native_ok = native_row.get("state") not in (
        "INSUFFICIENT_HISTORICAL_DEPTH", "INSUFFICIENT_EVIDENCE", None)

    if native_ok and native_row.get("state") == "AVAILABLE":
        edge_status = native_row["research_ranking_score"].get("state", "INSUFFICIENT_EVIDENCE")
        native_verdict = "NATIVE 1m revalidation ran — see per_timeframe['1m']"
    else:
        edge_status = gsb.EdgeStatus.DEGRADED.value if best else gsb.EdgeStatus.INSUFFICIENT_EVIDENCE.value
        native_verdict = (
            "BLOCKED BY DATA AVAILABILITY — the frozen contract's native 1-minute timeframe "
            f"has only ~{native_row.get('stored_span_days', 8)}d of yfinance history "
            "(INSUFFICIENT_HISTORICAL_DEPTH). "
            + (f"Best available real evidence: {best.get('timeframe')} "
               f"({best.get('role')}), OOS E[R] {best.get('oos_metrics', {}).get('expectancy_r')}, "
               f"N {best.get('oos_metrics', {}).get('total_trades')} — PARTIAL / exploratory, "
               f"NOT validation-grade and NOT the frozen holdout."
               if best else "No timeframe reached even the exploratory floor."))

    edge_reason = (
        "Native 1m: INSUFFICIENT_HISTORICAL_DEPTH (yfinance ~8d). "
        "15m/5m near-native: PARTIAL (~70d, single regime, no multi-year temporal coverage — "
        "cannot run validation-grade WFO / temporal stability). "
        "The frozen contract stays DEGRADED / UNVERIFIABLE at its native timeframe; only a "
        "deeper intraday provider can change that."
    )

    return NativeGoldRevalidation(
        generated_at=datetime.now(timezone.utc).isoformat(),
        strategy_id=REVAL_STRATEGY_ID,
        frozen_contract_hash=baseline.frozen_contract_hash,
        caveat=(
            "NATIVE = the frozen contract's own timeframe. NEAR_NATIVE = its setup/confirm "
            "timeframe. PROXY = a coarser substitute. A PROXY or PARTIAL result is NEVER the "
            "Gold strategy result and is NEVER comparable to the frozen N=82 / +0.637R holdout."
        ),
        per_timeframe=rows,
        best_available=best,
        edge_status=edge_status,
        edge_status_reason=edge_reason,
        native_verdict=native_verdict,
    )


def persist(reval: Optional[NativeGoldRevalidation] = None) -> str:
    reval = reval or revalidate()
    return store.save_artifact(ARTIFACT_KEY, "native_gold_revalidation", reval.to_dict())


def get_native_revalidation() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    store.register_with_phase68()
    r = revalidate()
    h = persist(r)
    print("\n=== NATIVE / NEAR-NATIVE XAUUSD REVALIDATION (Phase 73) ===")
    print(r.caveat)
    print(f"\n{'TF':<4} {'ROLE':<12} {'STATE':<28} {'BARS':>7} {'SPAN(d)':>8} "
          f"{'OOS E[R]':>9} {'N':>5}")
    for row in r.per_timeframe:
        oos = row.get("oos_metrics", {})
        print(f"{row['timeframe']:<4} {row['role']:<12} {row['state']:<28} "
              f"{row.get('stored_bars', 0):>7} {str(row.get('stored_span_days') or '-'):>8} "
              f"{str(oos.get('expectancy_r', '-')):>9} {str(oos.get('total_trades', '-')):>5}")
    print(f"\nEDGE STATUS: {r.edge_status}")
    print(f"NATIVE VERDICT: {r.native_verdict}")
    print(f"artifact: {ARTIFACT_KEY} @ {h[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = ["NativeGoldRevalidation", "revalidate", "persist", "get_native_revalidation",
           "REVAL_STRATEGY_ID", "ARTIFACT_KEY"]
