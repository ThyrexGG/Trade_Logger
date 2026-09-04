# -*- coding: utf-8 -*-
"""
Research Diagnostic Matrix (research tooling).

Phase 74 concluded ``NO_VALIDATED_EDGE`` / ``NO ROBUST EDGE FOUND`` across the
11-instrument MT5 universe on native 15m data, and ``EDGE INVALIDATED`` for the
frozen Gold contract's core logic on native 1m. This module answers the
follow-up question **diagnostically**:

    Is the lack of edge broad and structural, or does the current strategy
    framework fail only in particular instruments / sessions / regimes /
    directions / setups / periods?

It is a **diagnosis, not an optimisation**. No parameter is searched — every
strategy runs at its registered defaults (``StrategyDefinition.defaults()``).
Every segmentation rule is declared *before* it is evaluated (``SEGMENTATIONS``
below), and every subgroup carries N, expectancy, a deterministic bootstrap CI,
a sample-size class and a multiple-comparison-aware status.

The frozen holdout is never read. No execution / broker / risk module is
imported. Output is a persisted artifact (``research_diagnostic_matrix``).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

import backtester
import dataset_manifest
import gold_strategy_baseline as gsb
import historical_data_store as store
import research_engine
import research_universe
import strategy_discovery as disc

ARTIFACT_KEY = "research_diagnostic_matrix"
RANDOM_SEED = disc.RANDOM_SEED  # 42 — deterministic bootstrap
_PROGRESS = False  # main() flips this on so a long run prints per-pair progress

# --------------------------------------------------------------------------
# Sample-size classification (§3) — pre-declared, aligned with
# research_engine.BootstrapEstimator's own tiers.
# --------------------------------------------------------------------------
SAMPLE_CLASSES = (
    ("INSUFFICIENT_SAMPLE", 0, 30),
    ("EXPLORATORY", 30, 100),
    ("UNCERTAIN", 100, 300),
    ("ROBUST", 300, math.inf),
)


def sample_class(n: int) -> str:
    for name, lo, hi in SAMPLE_CLASSES:
        if lo <= n < hi:
            return name
    return "INSUFFICIENT_SAMPLE"


# --------------------------------------------------------------------------
# §13 candidate promotion gate — every criterion must hold. Pre-declared.
# --------------------------------------------------------------------------
GATE = {
    "min_trades": 200,           # ROBUST-tier, comfortably
    "require_mean_r_positive": True,
    "require_ci_lower_positive": True,          # nominal 95%
    "require_ci_lower_positive_bonferroni": True,  # at alpha / n_comparisons
    "require_temporal_both_halves_positive": True,
    "max_single_trade_r_share": 0.60,          # no bucket carried by one trade
}

# --------------------------------------------------------------------------
# Declared segmentation dimensions (§2). Each maps a trade dict -> a bucket
# label using an EXISTING project definition. Nothing invented post-hoc.
# --------------------------------------------------------------------------
_DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _entry_ts(t: Dict[str, Any]) -> pd.Timestamp:
    return pd.Timestamp(t["entry_time"])


def _session(t: Dict[str, Any]) -> str:
    # strategy_discovery._session_of — the project's canonical session windows
    return t.get("session") if t.get("session") in disc.SESSIONS else disc._session_of(_entry_ts(t))


def _dow(t: Dict[str, Any]) -> str:
    return _DOW[_entry_ts(t).dayofweek]


def _direction(t: Dict[str, Any]) -> str:
    d = str(t.get("direction", "")).upper()
    return {"BUY": "LONG", "SELL": "SHORT"}.get(d, d or "UNKNOWN")


def _liquidity(t: Dict[str, Any]) -> str:
    return str(t.get("liquidity_type") or "UNKNOWN")


def _year(t: Dict[str, Any]) -> str:
    return str(_entry_ts(t).year)


def _split_pos(t: Dict[str, Any]) -> str:
    return "IS" if not t.get("is_oos") else "OOS"


# regime is computed per (asset, strategy) from the prepared base frame, so it is
# attached to each trade at run time (see _tag_regime) rather than by a pure fn.
SEGMENTATIONS: Dict[str, Callable[[Dict[str, Any]], str]] = {
    "session": _session,
    "day_of_week": _dow,
    "direction": _direction,
    "liquidity_type": _liquidity,
    "year": _year,
    "is_oos_split": _split_pos,
    "regime": lambda t: t.get("_regime", "UNKNOWN"),
}

SEGMENTATION_RULES_DOC = {
    "session": "strategy_discovery._session_of — ASIA / LONDON / LONDON_NY_OVERLAP / NEW_YORK "
               "(UTC hour windows); trade's own 'session' field used when it is one of these",
    "day_of_week": "pandas Timestamp.dayofweek on entry_time (UTC)",
    "direction": "trade 'direction' field: BUY->LONG, SELL->SHORT",
    "liquidity_type": "trade 'liquidity_type' field from the setup meta (PDH/PDL/SWING_HIGH/"
                      "SWING_LOW/ASIAN_HIGH/ASIAN_LOW/EQH/EQL/...)",
    "year": "calendar year of entry_time (UTC) — the existing temporal_breakdown key",
    "is_oos_split": "backtester 'is_oos' flag (train_split=0.70, chronological)",
    "regime": "strategy_discovery._regime_breakdown classifier on the prepared base frame: "
              "TRENDING (|EMA20-EMA50|/close > 0.1%) / HIGH_VOLATILITY (ATR%% > rolling median) / "
              "RANGING (neither)",
}


# --------------------------------------------------------------------------
# R-multiple helpers
# --------------------------------------------------------------------------
def _trade_r(t: Dict[str, Any]) -> Optional[float]:
    entry, sl, pnl = t.get("entry_price"), t.get("stop_loss"), t.get("pnl")
    size = t.get("position_size") or 0.0
    if entry is None or sl is None or pnl is None:
        return None
    risk = abs(float(entry) - float(sl)) * float(size)
    if risk <= 0:
        return None
    return float(pnl) / risk


def _bucket_stats(rs: List[float], n_comparisons: int = 1) -> Dict[str, Any]:
    n = len(rs)
    out: Dict[str, Any] = {"n": n, "sample_class": sample_class(n)}
    if n == 0:
        out.update({"mean_r": None, "status": "INSUFFICIENT_SAMPLE"})
        return out
    arr = sorted(rs)
    total = sum(rs)
    wins = [x for x in rs if x > 0]
    gross_w = sum(wins)
    gross_l = abs(sum(x for x in rs if x <= 0)) or 1e-9
    ci = research_engine.BootstrapEstimator.calculate_r_expectancy_ci(rs, random_seed=RANDOM_SEED)
    # multiple-comparison-aware CI: widen alpha to Bonferroni 0.05 / M
    bonf_alpha = 0.05 / max(1, n_comparisons)
    ci_bonf = research_engine.BootstrapEstimator.calculate_r_expectancy_ci(
        rs, alpha=bonf_alpha, random_seed=RANDOM_SEED)
    largest_abs = max((abs(x) for x in rs), default=0.0)
    out.update({
        "mean_r": round(total / n, 4),
        "median_r": round(arr[n // 2], 4),
        "gross_return_r": round(total, 2),
        "profit_factor": round(gross_w / gross_l, 3),
        "win_rate_pct": round(100.0 * len(wins) / n, 1),
        "ci_lower": ci.get("ci_lower"),
        "ci_upper": ci.get("ci_upper"),
        "ci_range": ci.get("ci_range_str"),
        "ci_lower_bonferroni": ci_bonf.get("ci_lower"),
        "bonferroni_alpha": round(bonf_alpha, 6),
        "largest_single_trade_r_share": round(largest_abs / (abs(total) or 1e-9), 3),
        "bootstrap_verdict": ci.get("verdict"),
    })
    out["status"] = _bucket_status(out)
    return out


def _bucket_status(s: Dict[str, Any]) -> str:
    n, cl = s["n"], s["sample_class"]
    if cl == "INSUFFICIENT_SAMPLE":
        return "INSUFFICIENT_SAMPLE"
    lo, hi = s.get("ci_lower"), s.get("ci_upper")
    if hi is not None and hi < 0:
        return "NEGATIVE"
    if lo is not None and lo > 0:
        return "POSITIVE_CANDIDATE" if cl in ("UNCERTAIN", "ROBUST") else "POSITIVE_EXPLORATORY"
    return cl  # EXPLORATORY / UNCERTAIN / ROBUST with CI crossing zero


# --------------------------------------------------------------------------
# Regime tagging (needs the prepared base frame)
# --------------------------------------------------------------------------
def _regime_classifier(prepared) -> Callable[[Any], str]:
    df = prepared.df
    ema20 = df["Close"].ewm(span=20, adjust=False).mean()
    ema50 = df["Close"].ewm(span=50, adjust=False).mean()
    tr = pd.concat([df["High"] - df["Low"],
                    (df["High"] - df["Close"].shift()).abs(),
                    (df["Low"] - df["Close"].shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    atr_pct = (atr / df["Close"]) * 100.0
    atr_med = atr_pct.rolling(200, min_periods=30).median()

    def classify(ts) -> str:
        try:
            i = df.index.get_indexer([pd.Timestamp(ts)], method="nearest")[0]
        except Exception:
            return "UNKNOWN"
        trending = abs(ema20.iloc[i] - ema50.iloc[i]) / max(df["Close"].iloc[i], 1e-9) > 0.001
        if trending:
            return "TRENDING"
        hot = bool(atr_pct.iloc[i] > (atr_med.iloc[i] or atr_pct.iloc[i]))
        return "HIGH_VOLATILITY" if hot else "RANGING"

    return classify


# --------------------------------------------------------------------------
# One (asset, strategy) run at default params
# --------------------------------------------------------------------------
def run_pair(asset: str, strategy_id: str, timeframe: str = "15m") -> Dict[str, Any]:
    asset = research_universe.normalise(asset)
    sdef = disc.STRATEGY_DEFINITIONS[strategy_id]
    prepared, suf = disc.prepare_data(asset, timeframe)
    if prepared is None:
        return {"asset": asset, "strategy_id": strategy_id, "timeframe": timeframe,
                "state": "INSUFFICIENT_EVIDENCE", "reason": suf.get("reason"), "trades": []}

    inst = research_universe.get_instrument(asset)
    p = sdef.defaults()
    res = backtester.run_backtest(
        symbol=asset, timeframe=timeframe, strategy=sdef.registry_name, risk_pct=1.0,
        sl_atr=p.get("sl_atr", 1.5), tp_atr=p.get("tp_atr", 2.5),
        slippage=inst.pip_size * disc.SLIPPAGE_PIPS, commission_pct=disc.COMMISSION_PCT,
        fixed_spread=inst.pip_size * disc.SPREAD_PIPS, train_split=disc.TRAIN_SPLIT,
        preloaded_data={"df": prepared.df, "df_struct": prepared.df_struct,
                        "df_bias": prepared.df_bias})
    if "error" in res:
        return {"asset": asset, "strategy_id": strategy_id, "timeframe": timeframe,
                "state": "INSUFFICIENT_EVIDENCE", "reason": res["error"], "trades": []}

    raw = res.get("trades", [])
    regime_of = _regime_classifier(prepared)
    trades: List[Dict[str, Any]] = []
    for t in raw:
        r = _trade_r(t)
        if r is None:
            continue
        t = dict(t)
        t["_r"] = r
        t["_regime"] = regime_of(t["entry_time"])
        trades.append(t)

    return {
        "asset": asset, "strategy_id": strategy_id,
        "strategy_family": sdef.family, "timeframe": timeframe,
        "state": "AVAILABLE" if len(trades) >= disc._MIN_TRADES_FOR_EDGE else "INSUFFICIENT_EVIDENCE",
        "params": p, "dataset_id": prepared.dataset_id, "dataset_hash": prepared.dataset_hash,
        "coverage": prepared.coverage, "n_trades": len(trades), "trades": trades,
    }


# --------------------------------------------------------------------------
# Temporal stability (§7) — chronological, not reshuffled
# --------------------------------------------------------------------------
def _temporal_stability(rs_by_time: List[Tuple[pd.Timestamp, float]]) -> Dict[str, Any]:
    if len(rs_by_time) < 20:
        return {"state": "INSUFFICIENT_SAMPLE", "n": len(rs_by_time)}
    ordered = [r for _, r in sorted(rs_by_time, key=lambda x: x[0])]
    n = len(ordered)
    half = n // 2
    third = n // 3
    first, second = ordered[:half], ordered[half:]
    thirds = [ordered[:third], ordered[third:2 * third], ordered[2 * third:]]
    m = lambda xs: round(sum(xs) / len(xs), 4) if xs else None
    both_pos = (m(first) or -1) > 0 and (m(second) or -1) > 0
    thirds_pos = sum(1 for x in thirds if (m(x) or -1) > 0)
    return {
        "state": "AVAILABLE", "n": n,
        "first_half_mean_r": m(first), "second_half_mean_r": m(second),
        "both_halves_positive": bool(both_pos),
        "thirds_mean_r": [m(x) for x in thirds],
        "positive_thirds": thirds_pos,
        "degradation": round((m(second) or 0) - (m(first) or 0), 4),
    }


# --------------------------------------------------------------------------
# Matrix build (§12)
# --------------------------------------------------------------------------
@dataclass
class DiagnosticMatrix:
    generated_at: str
    timeframe: str
    frozen_contract_hash: str
    universe: List[str]
    strategies: List[str]
    dataset_manifest_ids: Dict[str, Optional[str]]
    n_comparisons: int
    multiple_testing: Dict[str, Any]
    rows: List[Dict[str, Any]]
    summary: Dict[str, Any]
    promoted_candidates: List[Dict[str, Any]]
    conclusion: str
    scope_note: str = ""
    holdout_untouched: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _instrument_consistency(rows: List[Dict[str, Any]], strategy_id: str) -> Dict[str, Any]:
    """Per-strategy, how the FULL-sample per-instrument expectancy is distributed."""
    per = [r for r in rows
           if r["strategy_id"] == strategy_id and r["dimension"] == "__overall__"]
    pos = [r["asset"] for r in per if (r["stats"].get("mean_r") or -1) > 0]
    ci_pos = [r["asset"] for r in per if (r["stats"].get("ci_lower") or -1) > 0]
    return {"instruments_evaluated": len(per),
            "mean_r_positive": sorted(pos), "ci_lower_positive": sorted(ci_pos),
            "class": ("NO_EDGE_ANYWHERE" if not ci_pos
                      else "SINGLE_INSTRUMENT" if len(ci_pos) == 1
                      else "MULTI_INSTRUMENT")}


def build_matrix(timeframe: str = "15m",
                 assets: Optional[List[str]] = None,
                 strategies: Optional[List[str]] = None) -> DiagnosticMatrix:
    assets = assets or [i.symbol for i in research_universe.universe()]
    strategies = strategies or list(disc.STRATEGY_DEFINITIONS.keys())
    disc.clear_prepare_cache()

    # Streaming design (§9 memory): process each (asset, strategy) immediately,
    # keep only lightweight per-bucket samples (r, is_oos, entry-epoch), discard
    # the trade dicts and the prepared frames per asset.
    #   bucket_samples[(asset, sid, dim, bucket)] = [(r, is_oos, epoch), ...]
    bucket_samples: Dict[Tuple[str, str, str, str], List[Tuple[float, bool, float]]] = {}
    pair_state: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def _accumulate(run: Dict[str, Any]) -> None:
        key0 = (run["asset"], run["strategy_id"])
        pair_state[key0] = {k: run.get(k) for k in ("state", "reason", "n_trades",
                                                    "dataset_hash", "params")}
        if run["state"] != "AVAILABLE":
            return
        samples = [(t["_r"], bool(t.get("is_oos")), _entry_ts(t).timestamp())
                   for t in run["trades"]]
        bucket_samples[(run["asset"], run["strategy_id"], "__overall__", "ALL")] = samples
        for dim, fn in SEGMENTATIONS.items():
            for t in run["trades"]:
                try:
                    k = str(fn(t))
                except Exception:
                    k = "UNKNOWN"
                bucket_samples.setdefault(
                    (run["asset"], run["strategy_id"], dim, k), []).append(
                    (t["_r"], bool(t.get("is_oos")), _entry_ts(t).timestamp()))

    _verbose = bool(_PROGRESS)
    for ai, a in enumerate(assets, 1):
        for s in strategies:
            try:
                run = run_pair(a, s, timeframe)
                _accumulate(run)
                if _verbose:
                    print(f"  [{ai}/{len(assets)}] {a:8} {s:26} "
                          f"{run.get('state'):20} n={run.get('n_trades', 0)}", flush=True)
            except Exception as e:  # transient DB / data error — record, don't abort
                pair_state[(research_universe.normalise(a), s)] = {
                    "state": "ERROR", "reason": repr(e), "n_trades": 0}
                if _verbose:
                    print(f"  [{ai}/{len(assets)}] {a:8} {s:26} ERROR {e!r}", flush=True)
        disc.clear_prepare_cache()  # free this asset's prepared frames

    # comparisons = buckets with a testable sample (N >= EXPLORATORY floor)
    n_comparisons = sum(1 for v in bucket_samples.values() if len(v) >= 30)

    # ---- stats with multiple-comparison-aware CI
    rows: List[Dict[str, Any]] = []
    for (asset, sid, dim, bucket), samp in sorted(bucket_samples.items()):
        rs = [r for r, _o, _e in samp]
        oos_rs = [r for r, o, _e in samp if o]
        stats = _bucket_stats(rs, n_comparisons=n_comparisons)
        oos_ci = (research_engine.BootstrapEstimator.calculate_r_expectancy_ci(
            oos_rs, random_seed=RANDOM_SEED) if len(oos_rs) >= 5 else {})
        stats["oos_n"] = len(oos_rs)
        stats["oos_mean_r"] = round(sum(oos_rs) / len(oos_rs), 4) if oos_rs else None
        stats["oos_ci_lower"] = oos_ci.get("ci_lower")
        row = {"asset": asset, "strategy_id": sid,
               "strategy_family": disc.STRATEGY_DEFINITIONS[sid].family,
               "dimension": dim, "bucket": bucket, "stats": stats}
        if stats.get("status", "").startswith("POSITIVE"):
            row["temporal_stability"] = _temporal_stability(
                [(pd.Timestamp(e, unit="s", tz="UTC"), r) for r, _o, e in samp])
        rows.append(row)

    pair_runs = [{"asset": a, "strategy_id": s, **st}
                 for (a, s), st in sorted(pair_state.items())]

    # Multiple-comparison accounting (§4). Same risk thresholds as
    # research_engine.MultipleTestingTracker.get_risk_status, computed inline over
    # the segment hypotheses rather than parameter experiments.
    if n_comparisons <= 5:
        risk_level = "LOW"
    elif n_comparisons <= 25:
        risk_level = "MODERATE"
    else:
        risk_level = "HIGH (DATA-MINING RISK)"
    positives = [r for r in rows if r["stats"].get("status", "").startswith("POSITIVE")]
    mt_status = {
        "n_comparisons": n_comparisons,
        "definition": "one hypothesis per (asset x strategy x dimension x bucket) with N >= 30",
        "risk_level": risk_level,
        "bonferroni_alpha": round(0.05 / max(1, n_comparisons), 6),
        "expected_false_positives_at_0.05": round(0.05 * n_comparisons, 1),
        "raw_positive_buckets": len(positives),
        "survive_bonferroni": sum(
            1 for r in positives if (r["stats"].get("ci_lower_bonferroni") or -1) > 0),
    }

    # ---- promotion gate (§13) — every criterion must hold
    promoted: List[Dict[str, Any]] = []
    for r in rows:
        s = r["stats"]
        checks = {
            "n>=min_trades": s["n"] >= GATE["min_trades"],
            "mean_r>0": (s.get("mean_r") or -1) > 0,
            "ci_lower>0": (s.get("ci_lower") or -1) > 0,
            "ci_lower>0_bonferroni": (s.get("ci_lower_bonferroni") or -1) > 0,
            "oos_mean_r>0": (s.get("oos_mean_r") or -1) > 0,
            "single_trade_share<=0.6":
                (s.get("largest_single_trade_r_share") or 1) <= GATE["max_single_trade_r_share"],
            "temporal_both_halves>0":
                bool(r.get("temporal_stability", {}).get("both_halves_positive")),
        }
        if all(checks.values()):
            promoted.append({k: r[k] for k in ("asset", "strategy_id", "dimension", "bucket")}
                            | {"stats": s, "temporal_stability": r.get("temporal_stability"),
                               "gate_checks": checks})

    # ---- summary
    overall_rows = [r for r in rows if r["dimension"] == "__overall__"]
    by_status: Dict[str, int] = {}
    for r in rows:
        by_status[r["stats"].get("status", "?")] = by_status.get(r["stats"].get("status", "?"), 0) + 1

    def _extreme(key, positive=True):
        cand = [r for r in rows if r["dimension"] != "__overall__"
                and r["stats"].get("mean_r") is not None and r["stats"]["n"] >= 100]
        if not cand:
            return None
        r = max(cand, key=lambda x: x["stats"]["mean_r"]) if positive \
            else min(cand, key=lambda x: x["stats"]["mean_r"])
        return {"asset": r["asset"], "strategy_id": r["strategy_id"],
                "dimension": r["dimension"], "bucket": r["bucket"],
                "n": r["stats"]["n"], "mean_r": r["stats"]["mean_r"],
                "ci_range": r["stats"].get("ci_range")}

    largest = max(rows, key=lambda r: r["stats"]["n"]) if rows else None
    summary = {
        "pairs_evaluated": sum(1 for r in pair_runs if r["state"] == "AVAILABLE"),
        "pairs_insufficient": sum(1 for r in pair_runs if r["state"] == "INSUFFICIENT_EVIDENCE"),
        "pairs_errored": [f"{r['asset']}:{r['strategy_id']}" for r in pair_runs
                          if r["state"] == "ERROR"],
        "buckets_total": len(rows),
        "buckets_by_status": by_status,
        "overall_mean_r_by_pair": sorted(
            ({"asset": r["asset"], "strategy_id": r["strategy_id"],
              "n": r["stats"]["n"], "mean_r": r["stats"].get("mean_r"),
              "ci_lower": r["stats"].get("ci_lower"), "status": r["stats"].get("status")}
             for r in overall_rows),
            key=lambda x: (x["mean_r"] if x["mean_r"] is not None else -9), reverse=True),
        "strongest_positive_subgroup": _extreme("mean_r", positive=True),
        "strongest_negative_subgroup": _extreme("mean_r", positive=False),
        "largest_sample": None if not largest else {
            "asset": largest["asset"], "strategy_id": largest["strategy_id"],
            "dimension": largest["dimension"], "bucket": largest["bucket"],
            "n": largest["stats"]["n"]},
        "instrument_consistency": {s: _instrument_consistency(rows, s) for s in strategies},
    }

    # ---- conclusion (§15.Q)
    if promoted:
        conclusion = "EXPLORATORY_CANDIDATE"
    elif mt_status["survive_bonferroni"] == 0:
        conclusion = "NO_EDGE_CONFIRMED"
    else:
        conclusion = "NO_EDGE_CONFIRMED (isolated buckets survive Bonferroni but fail the promotion gate)"

    manifests = {}
    for a in assets:
        try:
            m = dataset_manifest.get_manifest(a)
            manifests[a] = m["dataset_id"] if m else None
        except Exception:
            manifests[a] = None

    # scope note (§4 honesty): if a strategy subset was run, record which
    # strategies were excluded and their standing Phase-74 verdict so the
    # matrix stays auditable and un-cherry-picked.
    excluded = [s for s in disc.STRATEGY_DEFINITIONS if s not in strategies]
    excluded_note = {}
    if excluded:
        try:
            import pair_ranking
            pr = pair_ranking.get_pair_ranking() or {}
            ps = pr.get("pair_stability") or {}
            for s in excluded:
                excluded_note[s] = (ps.get(s) or {}).get("class", "unknown")
        except Exception:
            for s in excluded:
                excluded_note[s] = "unknown"

    return DiagnosticMatrix(
        generated_at=datetime.now(timezone.utc).isoformat(),
        timeframe=timeframe,
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        universe=list(assets), strategies=list(strategies),
        dataset_manifest_ids=manifests,
        n_comparisons=n_comparisons, multiple_testing=mt_status,
        rows=rows, summary=summary, promoted_candidates=promoted,
        conclusion=conclusion,
        scope_note=(
            "" if not excluded else
            f"Diagnosed {len(strategies)}/{len(disc.STRATEGY_DEFINITIONS)} strategies. "
            f"Excluded (already NO_EDGE_ANYWHERE in the Phase-74 pair_ranking, so re-"
            f"diagnosing them only strengthens NO_EDGE_CONFIRMED): "
            + ", ".join(f"{s} [{c}]" for s, c in excluded_note.items())),
    )


def persist(matrix: Optional[DiagnosticMatrix] = None, timeframe: str = "15m") -> str:
    matrix = matrix or build_matrix(timeframe)
    return store.save_artifact(ARTIFACT_KEY, "research_diagnostic_matrix", matrix.to_dict())


def get_matrix() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    import sys
    global _PROGRESS
    tf = sys.argv[1] if len(sys.argv) > 1 else "15m"
    strat_arg = sys.argv[2] if len(sys.argv) > 2 else None
    strategies = [s.strip() for s in strat_arg.split(",")] if strat_arg else None
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    _PROGRESS = True
    print(f"building research diagnostic matrix ({tf}) "
          f"strategies={strategies or 'ALL'} ...", flush=True)
    m = build_matrix(tf, strategies=strategies)
    print(f"\n=== RESEARCH DIAGNOSTIC MATRIX ({tf}) ===")
    print(f"pairs: {m.summary['pairs_evaluated']} evaluated / {m.summary['pairs_insufficient']} insufficient")
    print(f"buckets: {m.summary['buckets_total']}  |  comparisons (N>=30): {m.n_comparisons}")
    print(f"multiple-testing: {m.multiple_testing['risk_level']}  "
          f"expected false positives @0.05 ~ {m.multiple_testing['expected_false_positives_at_0.05']}  "
          f"raw positives {m.multiple_testing['raw_positive_buckets']}  "
          f"survive Bonferroni {m.multiple_testing['survive_bonferroni']}")
    print("\nOVERALL E[R] BY PAIR (full sample, default params):")
    for r in m.summary["overall_mean_r_by_pair"][:15]:
        print(f"  {r['asset']:8} {r['strategy_id']:26} N={r['n']:>5} E[R]={str(r['mean_r']):>8} "
              f"ci_lo={str(r['ci_lower']):>8} {r['status']}")
    print("\nstrongest positive subgroup:", m.summary["strongest_positive_subgroup"])
    print("strongest negative subgroup:", m.summary["strongest_negative_subgroup"])
    print("\ninstrument consistency:")
    for s, ic in m.summary["instrument_consistency"].items():
        print(f"  {s:26} {ic['class']:18} ci_lower_positive={ic['ci_lower_positive']}")
    print(f"\npromoted candidates: {len(m.promoted_candidates)}")
    for c in m.promoted_candidates:
        print("  ", c["asset"], c["strategy_id"], c["dimension"], c["bucket"], c["stats"].get("ci_range"))
    if m.scope_note:
        print(f"\nSCOPE: {m.scope_note}")
    print(f"\nCONCLUSION: {m.conclusion}")
    h = persist(m, tf)
    print(f"artifact: {ARTIFACT_KEY} @ {h[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = ["build_matrix", "persist", "get_matrix", "run_pair", "sample_class",
           "SEGMENTATIONS", "SEGMENTATION_RULES_DOC", "GATE", "ARTIFACT_KEY",
           "DiagnosticMatrix"]
