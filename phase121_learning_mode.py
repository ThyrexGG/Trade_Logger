"""Phase 121 - LEARNING MODE: how many gap-fade setups per week at each gap size, and how entries behave.

Not a strategy test. The big-gap fade has no confirmed edge (Phases 116-120). The user wants to
learn from it by comparing winning and losing setups, which needs more setups: ~4-5 a week. This
measures, for NQ and ES, the setups per week and the result at each minimum gap size (a gap >= t x
the 14-session average range, still unfilled at the entry time, faded toward yesterday's close, wide
stop, exit 12:00), and the effect of entering at 09:45 / 10:00 / 10:15 / 10:30.

    python -m phase121_learning_mode
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1

OUT = os.path.join(p1.CACHE, "phase121")
THRESH = (0.1, 0.15, 0.2, 0.3, 0.5, 0.7)
ENTRIES = {"0945": (9, 45), "1000": (10, 0), "1015": (10, 15), "1030": (10, 30)}


def rows(mkt: str, df: pd.DataFrame) -> pd.DataFrame:
    rth = df[(df.index.time >= dt.time(9, 30)) & (df.index.time < dt.time(16, 0))]
    gb = rth.groupby(rth.index.normalize())
    atr = (gb["high"].max() - gb["low"].min()).shift(1).rolling(14).mean()
    pcl = gb["close"].last().shift(1)
    slip = p1.SLIPPAGE[mkt]
    out = []
    for day, g in gb:
        if day.weekday() > 4 or np.isnan(pcl.get(day, np.nan)) or np.isnan(atr.get(day, np.nan)) or g.index[0].time() != dt.time(9, 30):
            continue
        pc, a = float(pcl[day]), float(atr[day])
        o = float(g["open"].iloc[0])
        gap = o - pc
        size = abs(gap) / a
        if size < min(THRESH):
            continue
        gup = gap > 0
        noon = day + pd.Timedelta(hours=12)
        for en, (hh, mm) in ENTRIES.items():
            t0 = day + pd.Timedelta(hours=hh, minutes=mm)
            pre, post = g[g.index < t0], g[(g.index >= t0) & (g.index < noon)]
            if len(pre) < 10 or len(post) < 10:
                continue
            touched = (pre["low"].min() <= pc) if gup else (pre["high"].max() >= pc)
            e = float(pre["close"].iloc[-1])
            if touched or (gup and e <= pc) or ((not gup) and e >= pc):
                continue
            side = -1 if gup else 1
            dist = abs(e - pc)
            stop = e - side * dist
            h, l, c = post["high"].to_numpy(), post["low"].to_numpy(), post["close"].to_numpy()
            res, mf, how = None, 1.0, "time"
            for k in range(len(post)):
                if (side > 0 and l[k] <= stop) or (side < 0 and h[k] >= stop):
                    res, mf, how = -1.0, 1.0, "stop"
                    break
                if (side > 0 and h[k] >= pc) or (side < 0 and l[k] <= pc):
                    res, mf, how = 1.0, 0.0, "target"
                    break
            if res is None:
                res = side * (c[-1] - e) / dist
            r = res - (float(post["spread"].iloc[0]) + slip + slip * mf) / dist
            out.append({"market": mkt, "day": str(day.date()), "entry": en, "size": size, "r": r, "how": how, "gap_up": gup,
                        "progress": (o - e) / (o - pc) if o != pc else 0.0})  # signed: 0.3 = 30% of the gap already closed, negative = price moved AWAY from the target
    return pd.DataFrame(out)


def main(argv=None) -> int:  # pragma: no cover
    os.makedirs(OUT, exist_ok=True)
    allr = []
    for m in ("NQ", "ES"):
        df = p1.load(m, "M1")
        df = df[df.index >= pd.Timestamp("2023-03-01")]
        allr.append(rows(m, df))
    d = pd.concat(allr)
    d.to_csv(os.path.join(OUT, "phase121_rows.csv"), index=False)
    weeks = (pd.Timestamp(d.day.max()) - pd.Timestamp(d.day.min())).days / 7
    print(f"history: {weeks:.0f} weeks\n\n== setups per week (first entry 09:45 only) and result, by minimum gap size ==")
    print(f"{'min gap':<8}{'mkt':<4}{'setups/wk':>10}{'win%':>7}{'mean R':>8}  {'2023-24':>8}{'2025-26':>8}")
    res = {}
    for t in THRESH:
        for m in ("NQ", "ES"):
            x = d[(d.market == m) & (d.entry == "0945") & (d["size"] >= t)]
            ex, co = x[x.day <= "2024-12-31"], x[x.day > "2024-12-31"]
            res[f"{m}|{t}"] = {"per_week": round(len(x) / weeks, 2), "win": round(float((x.r > 0).mean()), 3), "mean_r": round(float(x.r.mean()), 3)}
            print(f"{t:<8}{m:<4}{len(x) / weeks:>10.1f}{(x.r > 0).mean() * 100:>6.0f}%{x.r.mean():>+8.3f}  {ex.r.mean():>+8.3f}{co.r.mean():>+8.3f}")
    print("\n== multiple entries: attempts per week and result by entry time (min gap 0.2) ==")
    for m in ("NQ", "ES"):
        for en in ENTRIES:
            x = d[(d.market == m) & (d.entry == en) & (d["size"] >= 0.2)]
            print(f"{m} {en}: {len(x) / weeks:.1f}/wk  win {(x.r > 0).mean():.0%}  mean {x.r.mean():+.3f}R")
        days = d[(d.market == m) & (d["size"] >= 0.2)].groupby("day").entry.nunique()
        tot = d[(d.market == m) & (d["size"] >= 0.2)].shape[0]
        print(f"{m}: all four entry times together = {tot / weeks:.1f} attempts/wk on {days.shape[0] / weeks:.1f} days/wk")
    json.dump(res, open(os.path.join(OUT, "phase121_result.json"), "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
