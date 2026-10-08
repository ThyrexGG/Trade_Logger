"""Phase 102 — Phase 101's NY-open sweep entries + TJR's own filters.

Research only; reuses phase101's data loader, levels, entry logic and exit
simulator unchanged. Pre-registered before any Phase-102 result was seen:

Filters / variants (each applied to both instruments x both entry models = 16 cells):
  SMT        take an NQ sweep only if ES did NOT trade beyond ITS same level
             between the window start and our entry bar (and vice versa).
  BIAS       longs only when the prior regular-session close > its 20-day
             average of closes; shorts only when below.
  SMT_BIAS   both.
  FULL_TJR   both + liquidity target: the nearest opposite key level of the
             day (OR/ON/LDN/PD highs for longs, lows for shorts) at least 1R
             away, capped at 4R; none -> 2R.

Per day, per instrument, per entry model, per variant: the FIRST setup (any
of the four levels, either side) that passes the variant's filters. Stops,
time window, costs, one-trade-per-day and the CANDIDATE / PROMISING bar are
exactly Phase 101's (Bonferroni over these 16 cells). NONE (no filter, same
pooling) is reported for reference only and is not a hypothesis.

    python -m phase102_tjr_filters
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from dataclasses import asdict, replace
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1

VARIANTS = ("SMT", "BIAS", "SMT_BIAS", "FULL_TJR")
REFERENCE = "NONE"
N_CELLS = len(VARIANTS) * len(p1.ENTRIES) * len(p1.SYMBOLS)
BIAS_DAYS = 20
LIQ_MIN_R, LIQ_MAX_R = 1.0, 4.0
TF = "M5"
OTHER = {"NQ": "ES", "ES": "NQ"}
RESULT_PATH = os.path.join(p1.CACHE, "phase102_result.json")


def candidates(symbol: str, df: pd.DataFrame) -> Dict[str, List[dict]]:
    """day -> every first-sweep setup (both sides, every level, both entry models),
    each with its level geometry, as phase101 builds them."""
    out: Dict[str, List[dict]] = {}
    h, l, o, c, spr = (df[k].to_numpy() for k in ("high", "low", "open", "close", "spread"))
    idx = df.index
    prev_rth = None
    for day in sorted({d for d in idx.normalize() if d.weekday() < 5}):
        t930 = day + pd.Timedelta(hours=9, minutes=30)
        rth = df.loc[t930: day + pd.Timedelta(hours=16) - pd.Timedelta(seconds=1)]
        if len(rth) < 20:
            prev_rth = rth if len(rth) else prev_rth
            continue
        levels = p1._levels_for_day(df, day, prev_rth, TF)
        i_end = idx.searchsorted(day + pd.Timedelta(hours=12))
        i_last = idx.searchsorted(day + pd.Timedelta(hours=11))
        rows = []
        for level, (lh, ll, allowed_from) in levels.items():
            i0 = idx.searchsorted(allowed_from)
            for model in p1.ENTRIES:
                for swept in ("HIGH", "LOW"):
                    t = p1._setup_for_side(symbol, TF, model, level, swept, h, l, o, c, spr, idx, i0, i_last, i_end, lh, ll, day)
                    if t is not None:
                        rows.append({"trade": t, "allowed_from": allowed_from, "swept": swept})
        out[str(day.date())] = rows
        out.setdefault("_levels", {})[str(day.date())] = levels  # type: ignore[index]
        prev_rth = rth
    return out


def daily_bias(df: pd.DataFrame) -> Dict[str, int]:
    """day -> +1 / -1 / 0 from the PRIOR regular-session close vs its 20-day average."""
    rth = df[(df.index.time >= dt.time(9, 30)) & (df.index.time < dt.time(16, 0))]
    closes = rth["close"].groupby(rth.index.date).last()
    sma = closes.rolling(BIAS_DAYS).mean()
    out: Dict[str, int] = {}
    days = list(closes.index)
    for i in range(1, len(days)):
        prev_c, prev_sma = closes.iloc[i - 1], sma.iloc[i - 1]
        out[str(days[i])] = 0 if pd.isna(prev_sma) else (1 if prev_c > prev_sma else -1)
    return out


def smt_ok(t: p1.Trade, swept: str, allowed_from: pd.Timestamp, other_df: pd.DataFrame, other_levels: dict) -> bool:
    """True when the OTHER index did not take out its own same-type level by our entry."""
    lv = other_levels.get(t.level)
    if lv is None:
        return False
    oh, ol, _ = lv
    win = other_df.loc[allowed_from: pd.Timestamp(t.entry_time)]
    if not len(win):
        return False
    if swept == "HIGH":
        return bool(win["high"].max() <= oh)
    return bool(win["low"].min() >= ol)


def with_liquidity_target(t: p1.Trade, df: pd.DataFrame, levels: dict) -> p1.Trade:
    side = 1 if t.side == "LONG" else -1
    prices = [x for (hi, lo, _) in levels.values() for x in (hi, lo)]
    lo_px = t.entry + side * LIQ_MIN_R * t.risk
    hi_px = t.entry + side * LIQ_MAX_R * t.risk
    ahead = [x for x in prices if (side > 0 and lo_px <= x <= hi_px) or (side < 0 and hi_px <= x <= lo_px)]
    target = (min(ahead) if side > 0 else max(ahead)) if ahead else t.entry + side * p1.TARGET_R * t.risk
    h, l, o, spr = (df[k].to_numpy() for k in ("high", "low", "open", "spread"))
    idx = df.index
    eb = idx.get_loc(pd.Timestamp(t.entry_time))
    i_end = idx.searchsorted(pd.Timestamp(t.day) + pd.Timedelta(hours=12))
    fill_bar = eb if t.entry_model == "TJR" else None
    k, px, reason = p1._simulate_exit(h, l, o, idx, eb + 1, i_end, side, t.entry, t.stop, target, fill_bar)
    gross = side * (px - t.entry)
    slip = p1.SLIPPAGE[t.symbol]
    cost = float(spr[eb]) + (slip if t.entry_model == "RECLAIM" else 0.0) + (slip if reason in ("stop", "time") else 0.0)
    return replace(t, target=round(target, 2), exit_time=str(idx[min(k, len(idx) - 1)]), exit_reason=reason,
                   r_gross=round(gross / t.risk, 4), cost_r=round(cost / t.risk, 4), r=round((gross - cost) / t.risk, 4))


def placebo_p(trades: List[p1.Trade], df: pd.DataFrame, rng: np.random.Generator, n: int = p1.PLACEBO) -> float:
    """Same entries, stop and target DISTANCES, random direction."""
    if len(trades) < 10:
        return float("nan")
    h, l, o = (df[k].to_numpy() for k in ("high", "low", "open"))
    idx = df.index
    pre = []
    for t in trades:
        eb = idx.get_loc(pd.Timestamp(t.entry_time))
        i_end = idx.searchsorted(pd.Timestamp(t.day) + pd.Timedelta(hours=12))
        tgt_dist = abs(t.target - t.entry)
        res = {}
        for side in (1, -1):
            k, px, _ = p1._simulate_exit(h, l, o, idx, eb + 1, i_end, side, t.entry, t.entry - side * t.risk, t.entry + side * tgt_dist, None)
            res[side] = (side * (px - t.entry) - t.cost_r * t.risk) / t.risk
        pre.append(res)
    actual = np.mean([t.r for t in trades])
    sims = np.array([np.mean([q[1] if f else q[-1] for q, f in zip(pre, rng.integers(0, 2, len(pre)))]) for _ in range(n)])
    return round(float((sims >= actual).mean()), 4)


def run() -> Dict:
    rng = np.random.default_rng(102)
    data = {s: p1.load(s, TF) for s in p1.SYMBOLS}
    cands = {s: candidates(s, data[s]) for s in p1.SYMBOLS}
    bias = {s: daily_bias(data[s]) for s in p1.SYMBOLS}
    out: Dict = {"phase": 102, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                 "variants": VARIANTS, "cells": [], "reference": []}
    trades_out: Dict[str, List[dict]] = {}
    for s in p1.SYMBOLS:
        df = data[s]
        all_days = sorted({str(d.date()) for d in df.index.normalize() if d.weekday() < 5})
        cut = all_days[int(len(all_days) * (1 - p1.OOS_FRACTION))]
        lv_s = cands[s]["_levels"]
        lv_o = cands[OTHER[s]]["_levels"]
        for model in p1.ENTRIES:
            for variant in (REFERENCE,) + VARIANTS:
                chosen: List[p1.Trade] = []
                for day, rows in cands[s].items():
                    if day == "_levels":
                        continue
                    ok = []
                    for row in rows:
                        t = row["trade"]
                        if t.entry_model != model:
                            continue
                        side = 1 if t.side == "LONG" else -1
                        if variant in ("SMT", "SMT_BIAS", "FULL_TJR"):
                            if day not in lv_o or not smt_ok(t, row["swept"], row["allowed_from"], data[OTHER[s]], lv_o[day]):
                                continue
                        if variant in ("BIAS", "SMT_BIAS", "FULL_TJR"):
                            if bias[s].get(day, 0) != side:
                                continue
                        ok.append(t)
                    if not ok:
                        continue
                    t = min(ok, key=lambda x: x.entry_time)
                    if variant == "FULL_TJR":
                        t = with_liquidity_target(t, df, lv_s[day])
                    chosen.append(t)
                full = np.array([t.r for t in chosen])
                is_ = np.array([t.r for t in chosen if t.day < cut])
                oos_t = [t for t in chosen if t.day >= cut]
                oos = np.array([t.r for t in oos_t])
                st_full, st_is, st_oos = (p1.summarize(x, rng) for x in (full, is_, oos))
                row = {"symbol": s, "entry": model, "variant": variant, "oos_from": cut,
                       "full": st_full, "in_sample": st_is, "out_of_sample": st_oos,
                       "gross_mean_r": round(float(np.mean([t.r_gross for t in chosen])), 3) if chosen else None,
                       "avg_target_r": round(float(np.mean([abs(t.target - t.entry) / t.risk for t in chosen])), 2) if chosen else None,
                       "exit_mix": {k: sum(1 for t in chosen if t.exit_reason == k) for k in ("target", "stop", "time")}}
                trades_out[f"{s}_{model}_{variant}"] = [asdict(t) for t in chosen]
                if variant == REFERENCE:
                    out["reference"].append(row)
                    continue
                pv = placebo_p(oos_t, df, rng)
                row["placebo_p_oos"] = pv
                v = "NO_EDGE"
                if st_oos.get("n", 0) and st_oos.get("mean_r", -1) > 0 and st_oos["ci95"][0] > 0:
                    v = "PROMISING"
                    lob = p1._boot_ci(oos, 0.05 / N_CELLS, rng)[0]
                    row["out_of_sample"]["ci_bonf_16"] = round(lob, 3)
                    if st_oos["n"] >= 30 and lob > 0 and st_is.get("mean_r", -1) > 0 and pv == pv and pv < 0.05:
                        v = "CANDIDATE"
                row["verdict"] = v
                out["cells"].append(row)
    out["verdict"] = ("CANDIDATE_FOUND" if any(c["verdict"] == "CANDIDATE" for c in out["cells"])
                      else "PROMISING_ONLY" if any(c["verdict"] == "PROMISING" for c in out["cells"]) else "NO_EDGE")
    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    with open(os.path.join(p1.CACHE, "phase102_trades.json"), "w", encoding="utf-8") as f:
        json.dump(trades_out, f, default=str)
    return out


def main(argv=None) -> int:  # pragma: no cover
    res = run()
    print("verdict:", res["verdict"])
    for c in res["reference"] + res["cells"]:
        f, o = c["full"], c["out_of_sample"]
        print(f"{c['symbol']} {c['entry']:<8} {c['variant']:<9} N={f.get('n',0):>3} win={f.get('win_rate','-')} mean={f.get('mean_r','-'):>6} "
              f"gross={c['gross_mean_r']} tgtR={c['avg_target_r']} | IS={c['in_sample'].get('mean_r','-')} | OOS N={o.get('n',0)} "
              f"mean={o.get('mean_r','-')} ci={o.get('ci95')} p={c.get('placebo_p_oos','')} {c.get('verdict','(reference)')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
