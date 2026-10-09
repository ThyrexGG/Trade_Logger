"""Phase 117 — the opening gap fill, tested as a trade (NQ, ES).

Research only. Phase 109 measured that small 09:30 gaps fill ~70% of the time by noon and
big ones ~25%, but never priced it as a trade (entry after the open, a stop, costs). The
user watches 09:30 and trades from 09:45, so entries are at 09:45 and 10:00.

Pre-registered (before running):
  Gap       open at 09:30 vs the previous RTH close (last 1-minute close before 16:00 NY);
            size = |gap| / prior-14-day mean RTH range. Buckets: small [0.10, 0.30),
            mid [0.30, 0.70), big >= 0.70. Below 0.10 is skipped.
  Entry     at the close of the minute before ENTRY (09:45 or 10:00) IF the gap is still
            unfilled (price has not touched the previous close since 09:30) and price is
            still on the gap side. Direction = toward the previous close (fade the gap).
  Target    the previous close.
  Stop      A = the same distance as the target (1:1);  B = beyond the 09:30-to-entry
            extreme on the far side (min 0.10 of the prior range).
  Exit      flat 12:00 if neither is hit. Stop checked first inside a bar. Costs = bar
            spread + slippage on entry and on stop/time exits (as phases 101-115).
  Split     explore 2023-04..2024, confirm 2025..2026-10. A cell PASSES when confirm
            mean R > 0 with the 95% bootstrap CI (Bonferroni over all cells) above 0
            AND both 2025 and 2026 positive.
Also reported: the fill probability from entry time vs the probability the stop/target
geometry needs to break even (explains the result).

    python -m phase117_gap_fill
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from typing import Dict, List

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1

OUT = os.path.join(p1.CACHE, "phase117")
EXPLORE_END = "2024-12-31"
BUCKETS = {"small": (0.10, 0.30), "mid": (0.30, 0.70), "big": (0.70, 99.0)}
ENTRIES = {"0945": (9, 45), "1000": (10, 0)}


def _day_rows(mkt: str, m1: pd.DataFrame, rng_by_day: pd.Series, prev_close: pd.Series) -> List[dict]:
    slip = p1.SLIPPAGE[mkt]
    rows = []
    for day, g in m1.groupby(m1.index.normalize()):
        if day.weekday() > 4 or day not in prev_close.index or np.isnan(prev_close[day]) or np.isnan(rng_by_day.get(day, np.nan)):
            continue
        rth = g.between_time("09:30", "11:59")
        if len(rth) < 150 or rth.index[0].time() != dt.time(9, 30):
            continue
        pc, atr = float(prev_close[day]), float(rng_by_day[day])
        o = float(rth["open"].iloc[0])
        gap = o - pc
        size = abs(gap) / atr
        bucket = next((b for b, (lo, hi) in BUCKETS.items() if lo <= size < hi), None)
        if bucket is None:
            continue
        gup = gap > 0
        for ename, (hh, mm) in ENTRIES.items():
            t0 = day + pd.Timedelta(hours=hh, minutes=mm)
            pre = rth[rth.index < t0]
            post = rth[rth.index >= t0]
            if len(pre) < 10 or len(post) < 10:
                continue
            touched = (pre["low"].min() <= pc) if gup else (pre["high"].max() >= pc)
            e = float(pre["close"].iloc[-1])
            if touched or (gup and e <= pc) or ((not gup) and e >= pc):
                continue
            side = -1 if gup else 1
            dist = abs(e - pc)
            spread = float(post["spread"].iloc[0])
            far = float(pre["high"].max()) if gup else float(pre["low"].min())
            for sname in ("A", "B"):
                risk = dist if sname == "A" else max(abs(far - e), 0.10 * atr)
                stop = e - side * risk
                h, l, c = post["high"].to_numpy(), post["low"].to_numpy(), post["close"].to_numpy()
                res, outcome, mkt_frac = None, "time", 1.0
                for k in range(len(post)):
                    hit_stop = (l[k] <= stop) if side > 0 else (h[k] >= stop)
                    hit_tp = (h[k] >= pc) if side > 0 else (l[k] <= pc)
                    if hit_stop:
                        res, outcome, mkt_frac = -1.0, "stop", 1.0
                        break
                    if hit_tp:
                        res, outcome, mkt_frac = dist / risk, "target", 0.0
                        break
                if res is None:
                    res = side * (c[-1] - e) / risk
                r = res - (spread + slip + slip * mkt_frac) / risk
                rows.append({"market": mkt, "day": str(day.date()), "bucket": bucket, "entry": ename, "stop": sname,
                             "side": side, "r": round(r, 4), "outcome": outcome, "risk_pts": round(risk, 2), "dist_pts": round(dist, 2),
                             "fill": outcome == "target"})
    return rows


def run() -> Dict:
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(117)
    res: Dict = {"phase": 117, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "cells": []}
    allrows: List[dict] = []
    for mkt in ("NQ", "ES"):
        m1 = p1.load(mkt, "M1")
        m1 = m1[m1.index >= pd.Timestamp("2023-03-01")]
        rth = m1[(m1.index.time >= dt.time(9, 30)) & (m1.index.time < dt.time(16, 0))]
        gb = rth.groupby(rth.index.normalize())
        dr = (gb["high"].max() - gb["low"].min())
        atr = dr.shift(1).rolling(14).mean()
        prev_close = gb["close"].last().shift(1)
        allrows += _day_rows(mkt, m1, atr, prev_close)
    df = pd.DataFrame(allrows)
    df.to_csv(os.path.join(OUT, "phase117_trades.csv"), index=False)
    groups = list(df.groupby(["market", "bucket", "entry", "stop"]))
    k = len(groups)
    for (mkt, bucket, entry, stop), g in groups:
        ex, co = g[g.day <= EXPLORE_END], g[g.day > EXPLORE_END]
        if len(co) < 20:
            continue
        lo, hi = p1._boot_ci(co.r.to_numpy(), 0.05 / k, rng)
        yr = {y: round(float(x.r.mean()), 3) for y, x in co.groupby(co.day.str[:4])}
        p_fill = float((g.outcome == "target").mean())
        be_p = float(g.risk_pts.mean() / (g.risk_pts.mean() + g.dist_pts.mean())) if len(g) else None  # win prob needed at avg geometry
        res["cells"].append({
            "market": mkt, "bucket": bucket, "entry": entry, "stop": stop, "n": int(len(g)),
            "explore": round(float(ex.r.mean()), 3) if len(ex) else None, "n_explore": int(len(ex)),
            "confirm": round(float(co.r.mean()), 3), "n_confirm": int(len(co)), "confirm_ci_bonf": [round(lo, 3), round(hi, 3)],
            "by_year_confirm": yr, "fill_rate": round(p_fill, 3), "breakeven_fill_rate": round(be_p, 3),
            "mean_r": round(float(g.r.mean()), 3),
            "pass": bool(lo > 0 and all(v > 0 for v in yr.values()) and len(yr) >= 2),
        })
    res["n_cells"] = k
    res["passes"] = [c for c in res["cells"] if c["pass"]]
    with open(os.path.join(OUT, "phase117_result.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    return res


def main(argv=None) -> int:  # pragma: no cover
    res = run()
    print(f"cells: {res['n_cells']}   passes: {len(res['passes'])}")
    print(f"{'mkt':<4}{'gap':<6}{'entry':<6}{'stop':<5}{'n':>5}  {'fill%':>6}{'needs%':>7}  {'explore':>8}{'confirm':>8}  confirm CI (Bonf)      by year (confirm)")
    for c in sorted(res["cells"], key=lambda c: (c["market"], c["bucket"], c["entry"], c["stop"])):
        print(f"{c['market']:<4}{c['bucket']:<6}{c['entry']:<6}{c['stop']:<5}{c['n']:>5}  {c['fill_rate']*100:>5.0f}%{c['breakeven_fill_rate']*100:>6.0f}%  {c['explore'] if c['explore'] is not None else float('nan'):>+8.3f}{c['confirm']:>+8.3f}  {str(c['confirm_ci_bonf']):<22} {c['by_year_confirm']}{'  <== PASS' if c['pass'] else ''}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
