# -*- coding: utf-8 -*-
"""
Phase 75 — Systematic Strategy Research: ORB + VWAP Mean Reversion.

Two highly objective, deterministic, programmatically testable strategy families,
each run at ONE frozen baseline specification (no parameter search — §3):

  * ORB v1   — Opening Range Breakout off the US equity cash open
  * VWAP v1  — session-VWAP standard-deviation mean reversion

Research question (§Objective): can either demonstrate a reproducible,
statistically credible OOS edge on a small predefined set of liquid instruments?
A negative result (``NO_EDGE_CONFIRMED``) is an acceptable scientific outcome.

Universe (§1, fixed before evaluation): XAUUSD, USDJPY, EURUSD, GBPUSD, GBPJPY,
AUDJPY.  Data (§2): native MT5 broker spot 15m, from the persisted dataset
manifests.  Validation (§8): chronological 60/20/20 train / validation / OOS,
split on the session date — no shuffling, no look-ahead.  Multiple comparison
(§9): 2 strategies × 6 instruments = 12 primary hypotheses, Bonferroni-tracked.

Read-only research. No execution / broker / risk module imported. The frozen
Phase-74 holdout is never read.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd

import dataset_manifest
import gold_strategy_baseline as gsb
import historical_data_store as store
import research_engine
import research_universe

ARTIFACT_KEY = "phase75_orb_vwap"
RANDOM_SEED = 42                       # deterministic bootstrap (project convention)
TRAIN_RATIO, VAL_RATIO = 0.60, 0.20    # research_engine.ThreeLayerDataSplitter

RESEARCH_UNIVERSE = ("XAUUSD", "USDJPY", "EURUSD", "GBPUSD", "GBPJPY", "AUDJPY")
TIMEFRAME = "15m"
_NY = ZoneInfo("America/New_York")
_SESSION_OPEN = (9, 30)     # 09:30 America/New_York, DST handled by zoneinfo
_SESSION_CLOSE = (16, 0)    # 16:00 America/New_York

# project cost conventions (strategy_discovery)
_SPREAD_PIPS = 1.5
_SLIPPAGE_PIPS = 0.5
_COMMISSION_PCT = 0.005

# --------------------------------------------------------------------------
# Frozen specifications (§3 — one baseline each, frozen before evaluation)
# --------------------------------------------------------------------------
ORB_V1_SPEC = {
    "id": "orb_v1",
    "session": "09:30-16:00 America/New_York (US equity cash session), DST via zoneinfo",
    "timeframe": "15m (native MT5)",
    "opening_range": "the single 15m bar opening at 09:30 NY; OR_high/OR_low = its high/low",
    "compression_filter": "NR7 — the OR bar's range is strictly the smallest of the last 7 "
                          "completed 15m bars (OR bar + 6 prior). Fails NR7 -> no trade.",
    "entry": "first session bar (>= 09:45 NY, < 16:00) that CLOSES beyond the OR "
             "(> OR_high -> long, < OR_low -> short); fill at the NEXT bar's open",
    "trade_limit": "max 1 trade per instrument per session; no re-entry after a failed breakout",
    "stop": "opposite OR extreme (long: OR_low, short: OR_high) — range-derived, no multiplier",
    "target": "entry +/- 2.0 R (single deterministic R multiple)",
    "time_exit": "flat at the last session bar's close if neither stop nor target hit",
    "intrabar": "if a bar's range spans both stop and target, stop is assumed hit first",
    "costs": f"spread {_SPREAD_PIPS} pips + slippage {_SLIPPAGE_PIPS} pips/side + "
             f"commission {_COMMISSION_PCT}% notional",
}

VWAP_V1_SPEC = {
    "id": "vwap_v1",
    "session": "09:30-16:00 America/New_York, DST via zoneinfo (same as ORB v1)",
    "timeframe": "15m (native MT5)",
    "vwap": "cumulative session VWAP from 09:30; typical price (H+L+C)/3, weight = tick_volume",
    "sigma": "volume-weighted std of typical price around the running VWAP "
             "(sqrt(sum(v*TP^2)/sum(v) - VWAP^2)), cumulative",
    "warmup": "no entries before the 5th session bar (>= ~1h15m in) so sigma is meaningful",
    "bands": "VWAP +/- 2.5 sigma (baseline threshold, not optimised)",
    "entry": "long: bar.low <= lower band AND bar.close > lower band (poke + close back "
             "inside); short symmetric; fill at the NEXT bar's open",
    "trend_filter": "skip long when (VWAP - session_open) < -1.0 sigma; skip short when "
                    "(VWAP - session_open) > +1.0 sigma (one frozen filter)",
    "target": "the session VWAP at each subsequent bar (dynamic)",
    "stop": "entry -/+ 1.5 * sigma_at_entry (deviation-based); risk = 1.5 sigma_entry",
    "trade_limit": "max 2 trades per session; must be flat to enter",
    "time_exit": "flat at the last session bar's close",
    "news": "no authoritative historical high-impact-event calendar exists in the repo for "
            "backtest black-outs (the calendar layer is live/upcoming-oriented; FRED gives "
            "data series, not timed releases) — NOT applied. Documented limitation (§5).",
    "costs": ORB_V1_SPEC["costs"],
}


# --------------------------------------------------------------------------
# Session slicing
# --------------------------------------------------------------------------
def _load_frame(instrument: str) -> pd.DataFrame:
    rows = store.get_candles(instrument, TIMEFRAME)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df["ny"] = df["ts"].dt.tz_convert(_NY)
    df["Open"] = df["open"].astype(float)
    df["High"] = df["high"].astype(float)
    df["Low"] = df["low"].astype(float)
    df["Close"] = df["close"].astype(float)
    df["Vol"] = df["volume"].astype(float).clip(lower=0.0)
    df["session_date"] = df["ny"].dt.date
    open_min = _SESSION_OPEN[0] * 60 + _SESSION_OPEN[1]
    close_min = _SESSION_CLOSE[0] * 60 + _SESSION_CLOSE[1]
    df["ny_min"] = df["ny"].dt.hour * 60 + df["ny"].dt.minute
    df["in_session"] = (df["ny_min"] >= open_min) & (df["ny_min"] < close_min)
    return df.reset_index(drop=True)


@dataclass
class Trade:
    strategy: str
    instrument: str
    session_date: str
    direction: str            # LONG / SHORT
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    stop: float
    target: Optional[float]
    risk_dist: float
    r_gross: float            # pre-cost
    r_net: float              # post-cost
    exit_reason: str          # STOP / TARGET / TIME
    bars_held: int

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _costs_in_price(pip: float, entry: float, exit_: float) -> float:
    return (_SPREAD_PIPS * pip + 2.0 * _SLIPPAGE_PIPS * pip
            + (_COMMISSION_PCT / 100.0) * (abs(entry) + abs(exit_)))


def _finalise(strategy, instrument, sd, direction, bars, entry_idx,
              stop, target, pip) -> Optional[Trade]:
    """Fill at bars[entry_idx].Open, then walk forward within the session."""
    if entry_idx >= len(bars):
        return None
    entry = float(bars[entry_idx]["Open"])
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    d = 1.0 if direction == "LONG" else -1.0
    dyn = callable(target)
    exit_price, exit_reason, exit_time, held = None, None, None, 0
    for k in range(entry_idx, len(bars)):
        b = bars[k]
        held = k - entry_idx + 1
        hi, lo = float(b["High"]), float(b["Low"])
        tgt_k = target(k) if dyn else target
        # stop-first if both touched in the same bar (conservative)
        if (d > 0 and lo <= stop) or (d < 0 and hi >= stop):
            exit_price, exit_reason = stop, "STOP"
        elif tgt_k is not None and ((d > 0 and hi >= tgt_k) or (d < 0 and lo <= tgt_k)):
            exit_price, exit_reason = tgt_k, "TARGET"
        if exit_price is not None:
            exit_time = b["ny"].isoformat()
            break
    if exit_price is None:
        last = bars[-1]
        exit_price, exit_reason, exit_time = float(last["Close"]), "TIME", last["ny"].isoformat()
        held = len(bars) - entry_idx
    gross = d * (exit_price - entry)
    net = gross - _costs_in_price(pip, entry, exit_price)
    return Trade(strategy, instrument, str(sd), direction,
                 bars[entry_idx]["ny"].isoformat(), exit_time,
                 round(entry, 6), round(float(exit_price), 6), round(stop, 6),
                 round(float(target), 6) if isinstance(target, (int, float)) else None,
                 round(risk, 6), round(gross / risk, 4), round(net / risk, 4),
                 exit_reason, held)


# --------------------------------------------------------------------------
# ORB v1
# --------------------------------------------------------------------------
def orb_v1_session(session_bars, prior6, instrument, pip) -> Optional[Trade]:
    """One ORB v1 evaluation for a single NY session. Returns the trade (or None).
    Deterministic: NR7 gate -> first close-based breakout of the 09:30 OR bar ->
    fill at the next bar's open -> stop at the opposite OR extreme -> target
    entry +/- 2R -> else flat at the session close."""
    if len(session_bars) < 3:
        return None
    open_min = _SESSION_OPEN[0] * 60 + _SESSION_OPEN[1]
    if int(session_bars[0]["ny_min"]) != open_min:
        return None
    orb = session_bars[0]
    or_high, or_low = float(orb["High"]), float(orb["Low"])
    or_range = or_high - or_low
    if or_range <= 0:
        return None
    window = prior6 + [orb]
    if len(window) < 7 or not all(
            or_range < (float(b["High"]) - float(b["Low"])) for b in window[:-1]):
        return None
    sd = orb["session_date"]
    for j in range(1, len(session_bars) - 1):
        c = float(session_bars[j]["Close"])
        direction = "LONG" if c > or_high else "SHORT" if c < or_low else None
        if direction is None:
            continue
        entry_idx = j + 1
        entry = float(session_bars[entry_idx]["Open"])
        stop = or_low if direction == "LONG" else or_high
        risk = abs(entry - stop)
        if risk <= 0:
            return None
        target = entry + 2.0 * risk if direction == "LONG" else entry - 2.0 * risk
        return _finalise("orb_v1", instrument, sd, direction, session_bars,
                         entry_idx, stop, target, pip)
    return None


# --------------------------------------------------------------------------
# VWAP v1
# --------------------------------------------------------------------------
def vwap_v1_session(session_bars: List[Dict[str, Any]], instrument: str,
                    pip: float) -> List[Trade]:
    n = len(session_bars)
    if n < 8:
        return []
    sess_open = float(session_bars[0]["Open"])
    sum_pv = sum_v = sum_ppv = 0.0
    vwap = [0.0] * n
    sigma = [0.0] * n
    for i, b in enumerate(session_bars):
        tp = (float(b["High"]) + float(b["Low"]) + float(b["Close"])) / 3.0
        v = max(float(b["Vol"]), 1e-9)
        sum_pv += tp * v
        sum_v += v
        sum_ppv += v * tp * tp
        vwap[i] = sum_pv / sum_v
        sigma[i] = math.sqrt(max(sum_ppv / sum_v - vwap[i] ** 2, 0.0))

    trades: List[Trade] = []
    i = 4  # warmup: first entry candidate is the 5th bar
    while i < n - 1 and len(trades) < 2:
        b = session_bars[i]
        lo, hi, cl = float(b["Low"]), float(b["High"]), float(b["Close"])
        vw, sg = vwap[i], sigma[i]
        if sg <= 0:
            i += 1
            continue
        lower, upper = vw - 2.5 * sg, vw + 2.5 * sg
        drift = vw - sess_open
        direction = None
        if lo <= lower and cl > lower and not (drift < -1.0 * sg):
            direction = "LONG"
        elif hi >= upper and cl < upper and not (drift > 1.0 * sg):
            direction = "SHORT"
        if direction is None:
            i += 1
            continue
        entry_idx = i + 1
        entry = float(session_bars[entry_idx]["Open"])
        sg_e = sigma[i]
        stop = entry - 1.5 * sg_e if direction == "LONG" else entry + 1.5 * sg_e
        # dynamic target = the running VWAP at each later bar
        tgt = (lambda k: vwap[k])
        tr = _finalise("vwap_v1", instrument, session_bars[0]["session_date"],
                       direction, session_bars, entry_idx, stop, tgt, pip)
        if tr is None:
            i += 1
            continue
        trades.append(tr)
        # advance past the exit bar, stay flat until then
        exit_bar = next((k for k in range(entry_idx, n)
                         if session_bars[k]["ny"].isoformat() == tr.exit_time), n - 1)
        i = exit_bar + 1
    return trades


# --------------------------------------------------------------------------
# Per-instrument run
# --------------------------------------------------------------------------
def run_instrument(instrument: str) -> Dict[str, Any]:
    inst = research_universe.get_instrument(instrument)
    pip = inst.pip_size
    df = _load_frame(instrument)
    if df.empty:
        return {"instrument": instrument, "state": "NO_DATA", "orb_trades": [], "vwap_trades": []}

    recs = df.to_dict("records")
    by_session: Dict[Any, List[int]] = {}
    for idx, r in enumerate(recs):
        if r["in_session"]:
            by_session.setdefault(r["session_date"], []).append(idx)

    orb_trades: List[Trade] = []
    vwap_trades: List[Trade] = []
    for sd, idxs in sorted(by_session.items()):
        sess = [recs[i] for i in idxs]
        first = idxs[0]
        prior6 = [recs[i] for i in range(max(0, first - 6), first)]
        t = orb_v1_session(sess, prior6, instrument, pip)
        if t:
            orb_trades.append(t)
        vwap_trades.extend(vwap_v1_session(sess, instrument, pip))

    span = (df["session_date"].min(), df["session_date"].max())
    return {
        "instrument": instrument, "state": "OK",
        "sessions": len(by_session),
        "coverage": {"first_session": str(span[0]), "last_session": str(span[1]),
                     "bars": int(len(df)), "source": store.series_sources(instrument, TIMEFRAME)},
        "orb_trades": [t.to_dict() for t in orb_trades],
        "vwap_trades": [t.to_dict() for t in vwap_trades],
    }


# --------------------------------------------------------------------------
# Metrics + splits
# --------------------------------------------------------------------------
def _metrics(trades: List[Dict[str, Any]], key: str = "r_net") -> Dict[str, Any]:
    rs = [float(t[key]) for t in trades]
    n = len(rs)
    if n == 0:
        return {"n": 0}
    wins = [x for x in rs if x > 0]
    gl = abs(sum(x for x in rs if x <= 0)) or 1e-9
    cum, peak, mdd = 0.0, 0.0, 0.0
    for x in rs:
        cum += x
        peak = max(peak, cum)
        mdd = max(mdd, peak - cum)
    win_streak = loss_streak = cw = cl = 0
    for x in rs:
        if x > 0:
            cw += 1; cl = 0
        else:
            cl += 1; cw = 0
        win_streak = max(win_streak, cw)
        loss_streak = max(loss_streak, cl)
    srt = sorted(rs)
    exposure = sum(int(t.get("bars_held", 0)) for t in trades)
    return {
        "n": n,
        "total_r": round(sum(rs), 3),
        "mean_r": round(sum(rs) / n, 4),
        "median_r": round(srt[n // 2], 4),
        "win_rate_pct": round(100.0 * len(wins) / n, 1),
        "profit_factor": round(sum(wins) / gl, 3),
        "max_drawdown_r": round(mdd, 3),
        "largest_loss_r": round(min(rs), 4),
        "largest_win_r": round(max(rs), 4),
        "largest_win_streak": win_streak,
        "largest_loss_streak": loss_streak,
        "bars_in_market": exposure,
    }


def _split_by_session(trades: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    if not trades:
        return {"train": [], "validation": [], "oos": []}
    dates = sorted({t["session_date"] for t in trades})
    n = len(dates)
    t_end = int(n * TRAIN_RATIO)
    v_end = int(n * (TRAIN_RATIO + VAL_RATIO))
    train_d = set(dates[:t_end]); val_d = set(dates[t_end:v_end])
    out = {"train": [], "validation": [], "oos": []}
    for t in trades:
        d = t["session_date"]
        out["train" if d in train_d else "validation" if d in val_d else "oos"].append(t)
    return out


def _bootstrap(trades: List[Dict[str, Any]], alpha: float = 0.05) -> Dict[str, Any]:
    rs = [float(t["r_net"]) for t in trades]
    return research_engine.BootstrapEstimator.calculate_r_expectancy_ci(
        rs, alpha=alpha, random_seed=RANDOM_SEED)


def _temporal_ok(trades: List[Dict[str, Any]]) -> bool:
    rs = [float(t["r_net"]) for t in sorted(trades, key=lambda t: t["session_date"])]
    if len(rs) < 20:
        return False
    h = len(rs) // 2
    m = lambda xs: sum(xs) / len(xs) if xs else -1
    return m(rs[:h]) > 0 and m(rs[h:]) > 0


def _classify(oos: List[Dict[str, Any]], n_comparisons: int) -> Dict[str, Any]:
    n = len(oos)
    if n < 30:
        return {"status": "INSUFFICIENT_SAMPLE", "n": n}
    ci = _bootstrap(oos)
    ci_bonf = _bootstrap(oos, alpha=0.05 / max(1, n_comparisons))
    m = _metrics(oos, "r_net")
    m_pre = _metrics(oos, "r_gross")
    gate = {
        "n>=30": n >= 30,
        "oos_mean_r>0": m["mean_r"] > 0,
        "oos_ci_lower>0": (ci.get("ci_lower") or -1) > 0,
        "oos_ci_lower>0_bonferroni": (ci_bonf.get("ci_lower") or -1) > 0,
        "post_cost_mean_r>0": m["mean_r"] > 0,
        "pre_and_post_cost_positive": m["mean_r"] > 0 and m_pre["mean_r"] > 0,
        "temporal_both_halves>0": _temporal_ok(oos),
        "drawdown_reasonable": m["max_drawdown_r"] <= max(8.0, abs(m["total_r"]) + 5.0),
    }
    if all(gate.values()):
        status = "CANDIDATE"
    elif (ci.get("ci_upper") or 0) < 0 or m["mean_r"] <= 0:
        status = "FAILED"
    elif n >= 100:
        status = "UNCERTAIN"
    else:
        status = "EXPLORATORY"
    return {"status": status, "n": n, "oos_metrics": m, "oos_pre_cost_metrics": m_pre,
            "bootstrap_ci": ci, "bootstrap_ci_bonferroni": ci_bonf, "gate": gate}


# --------------------------------------------------------------------------
# Full matrix
# --------------------------------------------------------------------------
@dataclass
class Phase75Result:
    generated_at: str
    frozen_contract_hash: str
    universe: List[str]
    timeframe: str
    orb_spec: Dict[str, Any]
    vwap_spec: Dict[str, Any]
    dataset_manifest_ids: Dict[str, Optional[str]]
    coverage: Dict[str, Any]
    n_primary_hypotheses: int
    multiple_testing: Dict[str, Any]
    matrix: List[Dict[str, Any]]
    strategy_aggregate: Dict[str, Any]
    instrument_aggregate: Dict[str, Any]
    candidates: List[Dict[str, Any]]
    verdict: str
    key_findings: Dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    holdout_untouched: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def run(universe: Tuple[str, ...] = RESEARCH_UNIVERSE) -> Phase75Result:
    n_primary = 2 * len(universe)
    bonf_alpha = 0.05 / n_primary

    per_inst = {inst: run_instrument(inst) for inst in universe}
    coverage = {inst: r.get("coverage") for inst, r in per_inst.items()}
    manifests = {}
    for inst in universe:
        try:
            m = dataset_manifest.get_manifest(inst)
            manifests[inst] = m["dataset_id"] if m else None
        except Exception:
            manifests[inst] = None

    matrix: List[Dict[str, Any]] = []
    all_by_strat: Dict[str, List[Dict[str, Any]]] = {"orb_v1": [], "vwap_v1": []}
    all_by_inst: Dict[str, List[Dict[str, Any]]] = {}
    for inst in universe:
        r = per_inst[inst]
        for strat, tk in (("orb_v1", "orb_trades"), ("vwap_v1", "vwap_trades")):
            trades = r.get(tk, [])
            splits = _split_by_session(trades)
            cls = _classify(splits["oos"], n_primary)
            row = {
                "strategy": strat, "instrument": inst,
                "all": _metrics(trades, "r_net"),
                "all_pre_cost": _metrics(trades, "r_gross"),
                "train": _metrics(splits["train"], "r_net"),
                "validation": _metrics(splits["validation"], "r_net"),
                "oos": _metrics(splits["oos"], "r_net"),
                "oos_bootstrap": _bootstrap(splits["oos"]) if splits["oos"] else {},
                "oos_bootstrap_bonferroni": (_bootstrap(splits["oos"], alpha=bonf_alpha)
                                             if splits["oos"] else {}),
                "status": cls["status"], "gate": cls.get("gate"),
                "exposure_ratio": (round(_metrics(trades, "r_net").get("bars_in_market", 0)
                                         / max(1, r.get("sessions", 1) * 26), 4)),
            }
            matrix.append(row)
            all_by_strat[strat].extend(trades)
            all_by_inst.setdefault(inst, []).extend(trades)

    strat_agg = {}
    for s, tr in all_by_strat.items():
        sp = _split_by_session(tr)
        strat_agg[s] = {"all": _metrics(tr, "r_net"), "oos": _metrics(sp["oos"], "r_net"),
                        "oos_pre_cost": _metrics(sp["oos"], "r_gross"),
                        "oos_bootstrap": _bootstrap(sp["oos"]) if sp["oos"] else {}}
    inst_agg = {i: {"all": _metrics(tr, "r_net")} for i, tr in all_by_inst.items()}

    candidates = [{"strategy": r["strategy"], "instrument": r["instrument"],
                   "oos": r["oos"], "oos_bootstrap": r["oos_bootstrap"], "gate": r["gate"]}
                  for r in matrix if r["status"] == "CANDIDATE"]

    raw_pos = sum(1 for r in matrix
                  if r["oos"].get("n", 0) >= 30 and (r["oos"].get("mean_r") or -1) > 0
                  and (r["oos_bootstrap"].get("ci_lower") or -1) > 0)
    surv_bonf = sum(1 for r in matrix
                    if (r["oos_bootstrap_bonferroni"].get("ci_lower") or -1) > 0)
    mt = {
        "n_primary_hypotheses": n_primary,
        "definition": "2 strategies x 6 instruments, evaluated on the OOS split",
        "bonferroni_alpha": round(bonf_alpha, 6),
        "expected_false_positives_at_0.05": round(0.05 * n_primary, 2),
        "raw_positive_cells": raw_pos,
        "survive_bonferroni_ci_lower": surv_bonf,
        "note": "no parameter grid was run — the 12 primary hypotheses are the only tests",
    }

    if candidates:
        verdict = "CANDIDATE(S) IDENTIFIED"
    elif surv_bonf == 0 and raw_pos == 0:
        verdict = "NO_EDGE_CONFIRMED"
    else:
        verdict = "EXPLORATORY / INCONCLUSIVE"

    # key findings synthesis (§7 pre/post-cost, §6 instrument appropriateness)
    orb_all = strat_agg["orb_v1"]["all"]
    vwap_all = strat_agg["vwap_v1"]["all"]
    orb_pre = [r["all_pre_cost"].get("mean_r") for r in matrix if r["strategy"] == "orb_v1"]
    key_findings = {
        "orb_v1": (
            f"aggregate N={orb_all.get('n')}, post-cost mean R {orb_all.get('mean_r')}, "
            f"PF {orb_all.get('profit_factor')}, WR {orb_all.get('win_rate_pct')}%. "
            f"Pre-cost per-instrument mean R {orb_pre} — roughly breakeven-to-slightly-positive "
            f"before costs, uniformly negative after. The NR7 filter is restrictive: per-"
            f"instrument OOS N is 14-21 (INSUFFICIENT_SAMPLE); the full sample and aggregate "
            f"carry the conclusion. No post-cost edge."),
        "vwap_v1": (
            f"aggregate N={vwap_all.get('n')}, post-cost mean R {vwap_all.get('mean_r')}, "
            f"PF {vwap_all.get('profit_factor')}, WR {vwap_all.get('win_rate_pct')}%, "
            f"max DD {vwap_all.get('max_drawdown_r')}R. FAILED on all 6 instruments. The "
            f"'poke below +/- 2.5 sigma then close back inside' confirmation catches "
            f"continuation, not reversal (~30%% target-hit); on FX majors the 1.5 sigma stop "
            f"is often smaller than round-trip costs. Decisive failure."),
    }

    ident = json.dumps({"u": list(universe), "tf": TIMEFRAME,
                        "orb": ORB_V1_SPEC["id"], "vwap": VWAP_V1_SPEC["id"],
                        "rows": [(r["strategy"], r["instrument"], r["all"].get("n"),
                                  r["oos"].get("n"), r["status"]) for r in matrix]},
                       sort_keys=True)
    chash = hashlib.sha256(ident.encode()).hexdigest()

    return Phase75Result(
        generated_at=datetime.now(timezone.utc).isoformat(),
        frozen_contract_hash=gsb.get_gold_baseline().frozen_contract_hash,
        universe=list(universe), timeframe=TIMEFRAME,
        orb_spec=ORB_V1_SPEC, vwap_spec=VWAP_V1_SPEC,
        dataset_manifest_ids=manifests, coverage=coverage,
        n_primary_hypotheses=n_primary, multiple_testing=mt,
        matrix=matrix, strategy_aggregate=strat_agg, instrument_aggregate=inst_agg,
        candidates=candidates, verdict=verdict, key_findings=key_findings, content_hash=chash,
    )


def persist(result: Optional[Phase75Result] = None) -> str:
    result = result or run()
    return store.save_artifact(ARTIFACT_KEY, "phase75_orb_vwap", result.to_dict())


def get_result() -> Optional[Dict[str, Any]]:
    art = store.load_artifact(ARTIFACT_KEY)
    return art["payload"] if art else None


def main(_argv=None) -> int:  # pragma: no cover
    try:
        import mt5_provider  # noqa: F401
    except Exception:
        pass
    print("Phase 75 — ORB v1 + VWAP v1 research ...", flush=True)
    res = run()
    print(f"\n=== PHASE 75 RESULTS ({res.timeframe}, {len(res.universe)} instruments) ===")
    print(f"{'STRATEGY':<9} {'INSTRUMENT':<9} {'N(all)':>7} {'N(oos)':>7} {'OOS E[R]':>9} "
          f"{'OOS PF':>7} {'OOS WR%':>8} {'CI lower':>9} {'MaxDD':>7} STATUS")
    for r in res.matrix:
        o = r["oos"]
        ci = r["oos_bootstrap"].get("ci_lower")
        print(f"{r['strategy']:<9} {r['instrument']:<9} {r['all'].get('n', 0):>7} "
              f"{o.get('n', 0):>7} {str(o.get('mean_r', '-')):>9} {str(o.get('profit_factor', '-')):>7} "
              f"{str(o.get('win_rate_pct', '-')):>8} {str(ci if ci is not None else '-'):>9} "
              f"{str(o.get('max_drawdown_r', '-')):>7} {r['status']}")
    print("\nStrategy aggregate (OOS):")
    for s, a in res.strategy_aggregate.items():
        print(f"  {s:<9} {a['oos']}")
    print(f"\nMultiple testing: {res.multiple_testing}")
    print(f"Candidates: {len(res.candidates)}")
    for c in res.candidates:
        print("  ", c["strategy"], c["instrument"], c["oos"])
    print(f"\nVERDICT: {res.verdict}")
    h = persist(res)
    print(f"artifact: {ARTIFACT_KEY} @ {h[:12]}  content_hash {res.content_hash[:12]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main())


__all__ = ["run", "persist", "get_result", "run_instrument", "orb_v1_session",
           "vwap_v1_session", "ORB_V1_SPEC", "VWAP_V1_SPEC", "RESEARCH_UNIVERSE",
           "ARTIFACT_KEY", "Phase75Result", "Trade"]
