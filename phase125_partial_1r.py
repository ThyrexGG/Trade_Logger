"""Phase 125 - half off at +1R, stop to breakeven: does it help the gap fade?

The user (looking at a trade that ran to ~+1.9R and then closed at -0.27R at 12:00) manages trades by taking
half at 1R and moving the stop to breakeven. Same gap-fade setups as Phases 123/124 (gap >= t x the 14-session
range, unfilled at 09:45, fade toward yesterday's close, exit 12:00, NQ + ES). For each stop placement the SAME
days are run twice: PLAIN (stop, then yesterday's close or 12:00) and H1R (half off at +1R, stop to breakeven
for the rest, then yesterday's close or 12:00). The WIDE stop is skipped (its 1R IS yesterday's close).
Reported: win rate (net > 0), average P&L per trade as a % of the average daily range, and the PAIRED
difference H1R minus PLAIN day by day with a 95% bootstrap interval. EXPLORATORY.

    python -m phase125_partial_1r
"""
from __future__ import annotations

import datetime as dt
import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase124_structure_stops as p24


def run(thr: float) -> pd.DataFrame:
    out = []
    for mkt in ("NQ", "ES"):
        df = p1.load(mkt, "M1")
        df = df[df.index >= pd.Timestamp("2023-03-01")]
        rth = df[(df.index.time >= dt.time(9, 30)) & (df.index.time < dt.time(16, 0))]
        gb = rth.groupby(rth.index.normalize())
        atr = (gb["high"].max() - gb["low"].min()).shift(1).rolling(14).mean()
        pcl = gb["close"].last().shift(1)
        slip = p1.SLIPPAGE[mkt]
        for day, g in gb:
            if day.weekday() > 4 or np.isnan(pcl.get(day, np.nan)) or np.isnan(atr.get(day, np.nan)) or g.index[0].time() != dt.time(9, 30):
                continue
            pc, a = float(pcl[day]), float(atr[day])
            gap = float(g["open"].iloc[0]) - pc
            if abs(gap) / a < thr:
                continue
            gup = gap > 0
            t0, noon = day + pd.Timedelta(hours=9, minutes=45), day + pd.Timedelta(hours=12)
            pre, post = g[g.index < t0], g[(g.index >= t0) & (g.index < noon)]
            if len(pre) < 10 or len(post) < 10:
                continue
            e = float(pre["close"].iloc[-1])
            if ((pre["low"].min() <= pc) if gup else (pre["high"].max() >= pc)) or (gup and e <= pc) or ((not gup) and e >= pc):
                continue
            side = -1 if gup else 1
            spread = float(post["spread"].iloc[0])
            far = float(pre["high"].max()) if gup else float(pre["low"].min())
            m1 = df.loc[day + pd.Timedelta(hours=8, minutes=30): t0 - pd.Timedelta(minutes=1)]
            m5 = m1.resample("5min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
            m5 = m5[m5.index + pd.Timedelta(minutes=5) <= t0]
            ev1 = p24.events(*(m1[x].to_numpy() for x in ("open", "high", "low", "close")))
            ev5 = p24.events(*(m5[x].to_numpy() for x in ("open", "high", "low", "close")))
            kind = "H" if gup else "L"
            risks = {"TIGHT": max(abs(far - e), 0.10 * a), "A25": 0.25 * a, "FIX": 0.0021 * e}
            for nm, ev in (("S1", ev1), ("S5", ev5)):
                sw = p24.pick(ev, kind, e, above=gup, floor=0.05 * a)
                if sw is not None:
                    risks[nm] = abs(sw - e) + spread
            for nm, risk in risks.items():
                stop = e - side * risk
                tp1 = e + side * risk
                plain = p24.simulate(post, side, e, stop, risk, pc, None, "PC", spread, slip) / a
                half = p24.simulate(post, side, e, stop, risk, pc, tp1, "HALF", spread, slip) / a
                out.append({"market": mkt, "day": str(day.date()), "stop": nm, "risk": risk, "plain": plain, "h1r": half})
    return pd.DataFrame(out)


def main(argv=None) -> int:  # pragma: no cover
    rng = np.random.default_rng(125)
    for thr in (0.2, 0.7):
        d = run(thr)
        d.to_csv(p1.CACHE + f"/phase125_rows_{thr}.csv", index=False)
        print(f"\n===== gap >= {thr} x range =====")
        print(f"{'mkt':<4}{'stop':<6}{'n':>5}{'median stop':>12}{'win% plain':>11}{'win% H1R':>9}{'avg plain':>10}{'avg H1R':>9}{'H1R - plain':>12}   95% interval")
        for (m, s), g in d.groupby(["market", "stop"], sort=False):
            diff = (g.h1r - g.plain).to_numpy() * 100
            boot = rng.choice(diff, size=(3000, len(diff)), replace=True).mean(axis=1)
            print(f"{m:<4}{s:<6}{len(g):>5}{g.risk.median():>11.1f}p{(g.plain > 0).mean() * 100:>10.0f}%{(g.h1r > 0).mean() * 100:>8.0f}%{g.plain.mean() * 100:>+9.1f}%{g.h1r.mean() * 100:>+8.1f}%{diff.mean():>+11.1f}%   [{np.quantile(boot, .025):+.1f}, {np.quantile(boot, .975):+.1f}]")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
