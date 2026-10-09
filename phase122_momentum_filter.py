"""Phase 122 - does "the gap has not run away from the target by entry" separate winners from losers everywhere?

Hypothesis found in Phase 121b on NQ/ES (post hoc, so it needs an out-of-sample test): fade results are
better when, between the open and the entry (15 minutes), price has already moved TOWARD yesterday's
close ("progress" > 0) than when it kept running AWAY ("progress" <= 0). Pre-registered test on every
market except the NQ/ES sample it came from, plus NQ/ES by half:
  Rule     as Phase 120: gap >= 0.2 x the 14-session range, entry 15 min after the local cash open if the
           gap is unfilled, fade toward the previous close, wide 1:1 stop, exit 2.5 h after the open.
  Groups   progress > 0 (price already moving toward the target)  vs  progress <= 0.
  Regions  US other (Dow, Russell), EUROPE (6 indices), ASIA (3 indices); each day counts once per region
           (cluster bootstrap over days).
  PASS     in ALL THREE regions the difference (progress>0 minus progress<=0) in mean R is > 0 with a 95%
           day-cluster bootstrap interval above zero; plus NQ/ES positive in both halves.

    python -m phase122_momentum_filter
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase120_global_gaps as g20

OUT = os.path.join(p1.CACHE, "phase122")
THR = 0.2
SLIP = 0.00002
INFO = json.load(open(g20.INFO))
US = {"NQ": "NQ", "ES": "ES", "DJ": "US30", "RUT": "US2000"}
US_POINT = {"NQ": 0.01, "ES": 0.01, "DJ": 0.01, "RUT": 0.1}


def load_us(key: str) -> pd.DataFrame:
    if key in ("DJ", "RUT"):
        p1.SYMBOLS[key] = US[key]
    p1.POINT = US_POINT[key]
    try:
        df = p1.load(key, "M1")
    finally:
        p1.POINT = 0.01
    return df[df.index >= pd.Timestamp("2023-03-01")]


def rows(mkt: str, df: pd.DataFrame, open_hm, close_hm, region: str) -> list:
    (oh, om), (ch, cm) = open_hm, close_hm
    tmin = df.index.hour * 60 + df.index.minute
    ses = df[(tmin >= oh * 60 + om) & (tmin < ch * 60 + cm) & (df.index.weekday < 5)]
    gb = ses.groupby(ses.index.normalize())
    atr = (gb["high"].max() - gb["low"].min()).shift(1).rolling(14).mean()
    pcl = gb["close"].last().shift(1)
    out = []
    for day, g in gb:
        if np.isnan(pcl.get(day, np.nan)) or np.isnan(atr.get(day, np.nan)) or g.index[0] != day + pd.Timedelta(hours=oh, minutes=om):
            continue
        pc, a = float(pcl[day]), float(atr[day])
        o = float(g["open"].iloc[0])
        gap = o - pc
        if abs(gap) / a < THR:
            continue
        gup = gap > 0
        t0 = day + pd.Timedelta(hours=oh, minutes=om + 15)
        t1 = day + pd.Timedelta(hours=oh, minutes=om + 150)
        pre, post = g[g.index < t0], g[(g.index >= t0) & (g.index < t1)]
        if len(pre) < 5 or len(post) < 20:
            continue
        e = float(pre["close"].iloc[-1])
        if ((pre["low"].min() <= pc) if gup else (pre["high"].max() >= pc)) or (gup and e <= pc) or ((not gup) and e >= pc):
            continue
        side = -1 if gup else 1
        dist = abs(e - pc)
        stop = e - side * dist
        h, l, c = post["high"].to_numpy(), post["low"].to_numpy(), post["close"].to_numpy()
        res, mf = None, 1.0
        for k in range(len(post)):
            if (side > 0 and l[k] <= stop) or (side < 0 and h[k] >= stop):
                res, mf = -1.0, 1.0
                break
            if (side > 0 and h[k] >= pc) or (side < 0 and l[k] <= pc):
                res, mf = 1.0, 0.0
                break
        if res is None:
            res = side * (c[-1] - e) / dist
        slip = SLIP * e
        r = res - (float(post["spread"].iloc[0]) + slip + slip * mf) / dist
        out.append({"market": mkt, "region": region, "day": str(day.date()), "r": r, "progress": (o - e) / (o - pc)})
    return out


def cluster_diff(d: pd.DataFrame, rng) -> dict:
    days = d.day.unique()
    by = {k: g for k, g in d.groupby("day")}
    def diff(sel):
        x = pd.concat([by[k] for k in sel])
        up, dn = x[x.progress > 0].r, x[x.progress <= 0].r
        return up.mean() - dn.mean() if len(up) and len(dn) else np.nan
    base = diff(days)
    boots = np.array([diff(rng.choice(days, size=len(days), replace=True)) for _ in range(1500)])
    boots = boots[~np.isnan(boots)]
    up, dn = d[d.progress > 0], d[d.progress <= 0]
    return {"n_up": int(len(up)), "n_down": int(len(dn)), "mean_r_toward": round(float(up.r.mean()), 3), "mean_r_away": round(float(dn.r.mean()), 3),
            "diff": round(float(base), 3), "ci95": [round(float(np.quantile(boots, 0.025)), 3), round(float(np.quantile(boots, 0.975)), 3)]}


def main(argv=None) -> int:  # pragma: no cover
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(122)
    allr = []
    for k in ("NQ", "ES", "DJ", "RUT"):
        allr += rows(k, load_us(k), (9, 30), (16, 0), "US_SAMPLE" if k in ("NQ", "ES") else "US_OTHER")
    for mkt, cfg in g20.MARKETS.items():
        df = g20.load_local(mkt, cfg[0], INFO[mkt]["point"])
        allr += rows(mkt, df, cfg[1], cfg[2], cfg[3])
    d = pd.DataFrame(allr)
    d.to_csv(os.path.join(OUT, "phase122_rows.csv"), index=False)
    res = {}
    for reg, g in d.groupby("region"):
        res[reg] = cluster_diff(g, rng)
        if reg == "US_SAMPLE":
            for nm, sel in (("2023-24", g.day <= "2024-12-31"), ("2025-26", g.day > "2024-12-31")):
                res[f"US_SAMPLE {nm}"] = cluster_diff(g[sel], rng)
    for mkt, g in d.groupby("market"):
        up, dn = g[g.progress > 0], g[g.progress <= 0]
        res[f"market {mkt}"] = {"toward": round(float(up.r.mean()), 3), "away": round(float(dn.r.mean()), 3), "n": [int(len(up)), int(len(dn))]}
    passed = all(res[r]["ci95"][0] > 0 for r in ("US_OTHER", "EUROPE", "ASIA"))
    res["PASS"] = bool(passed)
    json.dump(res, open(os.path.join(OUT, "phase122_result.json"), "w"), indent=1)
    print(f"{'group':<20}{'n toward/away':>16}{'R toward':>10}{'R away':>9}{'diff':>8}  95% interval")
    for r in ("US_SAMPLE", "US_SAMPLE 2023-24", "US_SAMPLE 2025-26", "US_OTHER", "EUROPE", "ASIA"):
        v = res[r]
        print(f"{r:<20}{str(v['n_up']) + '/' + str(v['n_down']):>16}{v['mean_r_toward']:>+10.3f}{v['mean_r_away']:>+9.3f}{v['diff']:>+8.3f}  {v['ci95']}")
    print("\nper market (R when moving toward / away, n):")
    for k, v in res.items():
        if k.startswith("market "):
            print(f"  {k[7:]:<8} toward {v['toward']:+.3f}  away {v['away']:+.3f}  n={v['n']}")
    print("\nPASS (all three other regions, interval above 0):", res["PASS"])
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
