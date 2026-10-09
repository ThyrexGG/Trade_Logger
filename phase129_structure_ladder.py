"""Phase 129 - scale out at the chart's marked highs / lows (a ladder), stop trailed behind each level.

The user's management: take partials at the structure (swing highs for a long, swing lows for a short) on the way to
yesterday's close, move the stop to breakeven after the first, and behind the first level after the second.
Same gap-fade entries as Phases 123-127 (NQ + ES, Mar 2023 - 25 Sep 2026, no time exit, up to 10 sessions).
LADDER   levels = the last 3 one-minute and last 3 five-minute swings (as known at entry) in the profit direction, between 0.5R
         and the target distance; L1 = the nearest, L2 = the next one at least 0.5R beyond L1. Missing levels fall back to
         +1R / +2R (only if they are closer than the target). A third of the position at L1, a third at L2, the rest at
         yesterday's close. Stop: initial -> breakeven after L1 -> L1 after L2.
LADDER_BE the same ladder but the stop only moves to breakeven (never to L1).
HSTR     the single half at the structure near +1R (Phase 127) as the benchmark; PLAIN = stop or target only.
Stop before target inside one 1-minute bar. R = net P&L (spread + slippage) / stop distance. EXPLORATORY.

    python -m phase129_structure_ladder
"""
from __future__ import annotations

import datetime as dt
import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase124_structure_stops as p24
import phase127_hold_no_time_exit as p27

HOLD_DAYS = 10


def ladder_sim(side, e, stop, risk, pc, levels, trail_to_l1, h, l, c, spread, slip):
    """levels: ascending profit distances (points) of the partials, may be empty. Thirds; returns pnl points."""
    tdist = abs(pc - e)
    fr = [1.0 / 3.0] * len(levels) if levels else []
    done = [False] * len(levels)
    cur = stop
    banked, size = 0.0, 1.0
    for k in range(len(c)):
        # stop first
        if (side > 0 and l[k] <= cur) or (side < 0 and h[k] >= cur):
            return banked + size * side * (cur - e) - spread - slip * (1 + size)
        for j, d in enumerate(levels):
            if not done[j] and ((side > 0 and h[k] >= e + d) or (side < 0 and l[k] <= e - d)):
                done[j] = True
                banked += fr[j] * d
                size -= fr[j]
                if j == 0:
                    cur = e
                elif j == 1 and trail_to_l1:
                    cur = e + side * levels[0]
        if (side > 0 and h[k] >= pc) or (side < 0 and l[k] <= pc):
            return banked + size * tdist - spread - slip
    return banked + size * side * (c[-1] - e) - spread - slip * (1 + size)


def make_levels(side, e, risk, tdist, cands):
    """cands: profit-side swing prices known at entry."""
    ds = sorted({abs(x - e) for x in cands if 0.5 * risk <= abs(x - e) < tdist * 0.999})
    lv = []
    if ds:
        lv.append(ds[0])
        nxt = [d for d in ds if d >= lv[0] + 0.5 * risk]
        lv.append(nxt[0] if nxt else None)
    else:
        lv = [None, None]
    if lv[0] is None:
        lv[0] = risk if risk < tdist * 0.999 else None
    if lv[0] is None:
        return []
    if lv[1] is None:
        lv[1] = max(2 * risk, lv[0] + 0.5 * risk)
        if lv[1] >= tdist * 0.999:
            lv[1] = 0.5 * (lv[0] + tdist)
    return [lv[0], lv[1]]


def run(thr: float, extra=None) -> pd.DataFrame:
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
            if day > p27.LAST_DAY or day.weekday() > 4 or np.isnan(pcl.get(day, np.nan)) or np.isnan(atr.get(day, np.nan)) or g.index[0].time() != dt.time(9, 30):
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
            pk = "L" if gup else "H"
            cands = [x for evx in (ev1, ev5) for x in [q[2] for q in evx if q[1] == pk][-3:] if ((x < e) if gup else (x > e))]
            risks = {"Wide": abs(e - pc), "Tight": max(abs(far - e), 0.10 * a), "Medium": 0.25 * a, "Fixed": 0.0021 * e}
            for nm, ev in (("Struct1m", ev1), ("Struct5m", ev5)):
                sw = p24.pick(ev, kind, e, above=gup, floor=0.05 * a)
                risks[nm] = abs(sw - e) + spread if sw is not None else abs(e - pc)
            fut = df[(df.index >= t0) & (df.index < t0 + pd.Timedelta(days=HOLD_DAYS))]
            h, l, c = fut["high"].to_numpy(), fut["low"].to_numpy(), fut["close"].to_numpy()
            tdist = abs(pc - e)
            for nm, risk in risks.items():
                stop = e - side * risk
                lv = make_levels(side, e, risk, tdist, cands)
                plain, _ = p27.hold(side, e, stop, risk, pc, None, h, l, c, spread, slip)
                ctl = {"PLAIN": plain / risk}
                if lv:
                    ctl["LADDER"] = ladder_sim(side, e, stop, risk, pc, lv, True, h, l, c, spread, slip) / risk
                    ctl["LADDER_BE"] = ladder_sim(side, e, stop, risk, pc, lv, False, h, l, c, spread, slip) / risk
                    ctl["HALF_L1"] = ladder_sim(side, e, stop, risk, pc, lv[:1], False, h, l, c, spread, slip) / risk
                else:
                    ctl["LADDER"] = ctl["LADDER_BE"] = ctl["HALF_L1"] = plain / risk
                if extra is not None:
                    ctl.update(extra({"side": side, "e": e, "stop": stop, "risk": risk, "pc": pc, "lv": lv, "h": h, "l": l, "c": c, "fut": fut, "spread": spread, "slip": slip}))
                for m, r in ctl.items():
                    out.append({"market": mkt, "day": str(day.date()), "stop": nm, "mode": m, "r": r, "has_ladder": bool(lv)})
    return pd.DataFrame(out)


def main(argv=None) -> int:  # pragma: no cover
    rng = np.random.default_rng(129)
    for thr in (0.2, 0.7):
        d = run(thr)
        d.to_csv(p1.CACHE + f"/phase129_rows_{thr}.csv", index=False)
        print(f"\n===== gap >= {thr} x range, NQ + ES pooled, no time exit =====")
        print(f"{'stop':<9}{'mode':<10}{'n':>5}{'win%':>6}{'avgR':>8}{'95% interval':>18}{'PF':>6}{'totalR':>8}")
        for (s, m), g in d.groupby(["stop", "mode"], sort=False):
            r = g.r.to_numpy()
            boot = rng.choice(r, size=(2000, len(r)), replace=True).mean(axis=1)
            gl = -r[r < 0].sum()
            print(f"{s:<9}{m:<10}{len(r):>5}{(r > 0).mean() * 100:>5.0f}%{r.mean():>+8.3f}   [{np.quantile(boot, .025):+.2f}, {np.quantile(boot, .975):+.2f}]{(r[r > 0].sum() / gl if gl else float('nan')):>6.2f}{r.sum():>+8.1f}")
        d["year"] = d.day.str[:4]
        print("\n-- per year avgR: LADDER vs PLAIN --")
        print(d[d["mode"].isin(["LADDER", "PLAIN"])].groupby(["stop", "mode", "year"]).r.mean().unstack("year").round(3).to_string())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
