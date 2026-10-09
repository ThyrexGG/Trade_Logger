"""Phase 127 - the user's management: NO time exit, half off at +1R, stop to breakeven, hold for the target.

Same gap-fade setups as Phases 123-126 (gap >= t x the 14-session RTH range, unfilled at 09:45, fade toward
yesterday's close, NQ + ES, Mar 2023 - 25 Sep 2026 so every trade has 10 sessions to resolve). Three ways to manage
the SAME entries, per stop placement:
  TIME12   half at +1R / stop to BE, but closed at 12:00 (Phase 125's best management)
  HOLD     plain: stop or yesterday's close, held up to 10 sessions (no time rule)
  HOLD_H1R half at +1R then stop to BE, rest to yesterday's close, held up to 10 sessions
  HOLD_HSTR same, but the half is taken at the 1m/5m swing nearest +1R (0.7R-1.5R away), else exactly +1R
Within one 1-minute bar the stop is taken before the target. After 10 sessions an unresolved trade closes at market.
Results in R (net of spread + slippage / stop distance). EXPLORATORY.

    python -m phase127_hold_no_time_exit
"""
from __future__ import annotations

import datetime as dt
import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1
import phase124_structure_stops as p24

LAST_DAY = pd.Timestamp("2026-09-25")
HOLD_DAYS = 10
BIG = 10 ** 9


def first(cond: np.ndarray, start: int = 0) -> int:
    c = cond[start:]
    return start + int(np.argmax(c)) if c.any() else BIG


def hold(side, e, stop, risk, pc, tp1, h, l, c, spread, slip):
    """Returns (pnl in points, bars held). tp1 None = no half."""
    n = len(c)
    hit_stop = (l <= stop) if side > 0 else (h >= stop)
    hit_tgt = (h >= pc) if side > 0 else (l <= pc)
    i_s, i_t = first(hit_stop), first(hit_tgt)
    tdist = abs(pc - e)
    if tp1 is None:
        if i_s == BIG and i_t == BIG:
            return side * (c[-1] - e) - spread - 2 * slip, n
        if i_s <= i_t:
            return -risk - spread - 2 * slip, i_s
        return tdist - spread - slip, i_t
    hit_1 = (h >= tp1) if side > 0 else (l <= tp1)
    i_1 = first(hit_1)
    if i_s <= min(i_1, i_t):
        return -risk - spread - 2 * slip, i_s
    if i_t < i_1:
        return tdist - spread - slip, i_t
    if i_1 == BIG:
        return side * (c[-1] - e) - spread - 2 * slip, n
    banked = 0.5 * abs(tp1 - e)
    hit_be = (l <= e) if side > 0 else (h >= e)
    i_be = first(hit_be, i_1 + 1)
    if i_t == BIG and i_be == BIG:
        return banked + 0.5 * side * (c[-1] - e) - spread - 1.5 * slip, n
    if i_be <= i_t:
        return banked - spread - 1.5 * slip, i_be
    return banked + 0.5 * tdist - spread - slip, i_t


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
            if day > LAST_DAY or day.weekday() > 4 or np.isnan(pcl.get(day, np.nan)) or np.isnan(atr.get(day, np.nan)) or g.index[0].time() != dt.time(9, 30):
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
            risks = {"Wide": abs(e - pc), "Tight": max(abs(far - e), 0.10 * a), "Medium": 0.25 * a, "Fixed": 0.0021 * e}
            for nm, ev in (("Struct1m", ev1), ("Struct5m", ev5)):
                sw = p24.pick(ev, kind, e, above=gup, floor=0.05 * a)
                risks[nm] = abs(sw - e) + spread if sw is not None else abs(e - pc)
            fut = df[(df.index >= t0) & (df.index < t0 + pd.Timedelta(days=HOLD_DAYS))]
            h, l, c = fut["high"].to_numpy(), fut["low"].to_numpy(), fut["close"].to_numpy()
            for nm, risk in risks.items():
                stop, tp1 = e - side * risk, e + side * risk
                if nm != "Wide":
                    pnl = p24.simulate(post, side, e, stop, risk, pc, tp1, "HALF", spread, slip)
                    out.append({"market": mkt, "day": str(day.date()), "stop": nm, "mode": "TIME12", "r": pnl / risk, "hours": 2.25})
                # half taken at the chart structure nearest +1R (last 3 swings of each timeframe, 0.7R-1.5R away), else exactly +1R
                pk = "L" if gup else "H"
                cand = [x for evx in (ev1, ev5) for x in [q[2] for q in evx if q[1] == pk][-3:]]
                cand = [x for x in cand if 0.7 * risk <= abs(x - e) <= 1.5 * risk and ((x < e) if gup else (x > e))]
                tstr = min(cand, key=lambda x: abs(x - tp1)) if cand else tp1
                for mode, t1 in (("HOLD", None), ("HOLD_H1R", tp1), ("HOLD_HSTR", tstr)):
                    if mode != "HOLD" and nm == "Wide" and mode == "HOLD_H1R":
                        continue
                    pnl, k = hold(side, e, stop, risk, pc, t1, h, l, c, spread, slip)
                    out.append({"market": mkt, "day": str(day.date()), "stop": nm, "mode": mode, "r": pnl / risk, "hours": k / 60})
    return pd.DataFrame(out)


def main(argv=None) -> int:  # pragma: no cover
    rng = np.random.default_rng(127)
    for thr in (0.2, 0.7):
        d = run(thr)
        d.to_csv(p1.CACHE + f"/phase127_rows_{thr}.csv", index=False)
        print(f"\n===== gap >= {thr} x range, Mar 2023 - 25 Sep 2026, NQ + ES pooled =====")
        print(f"{'stop':<9}{'mode':<10}{'n':>5}{'win%':>6}{'avgR':>8}{'95% interval':>18}{'PF':>6}{'totalR':>8}{'med hrs':>9}{'>1 day':>8}")
        for (s, m), g in d.groupby(["stop", "mode"], sort=False):
            r = g.r.to_numpy()
            boot = rng.choice(r, size=(2000, len(r)), replace=True).mean(axis=1)
            gl = -r[r < 0].sum()
            print(f"{s:<9}{m:<10}{len(r):>5}{(r > 0).mean() * 100:>5.0f}%{r.mean():>+8.3f}   [{np.quantile(boot, .025):+.2f}, {np.quantile(boot, .975):+.2f}]{(r[r > 0].sum() / gl if gl else float('nan')):>6.2f}{r.sum():>+8.1f}{g.hours.median():>9.1f}{(g.hours > 24).mean() * 100:>7.0f}%")
        d["year"] = d.day.str[:4]
        print("\n-- per year, avgR (pooled) for the HOLD_H1R / HOLD modes --")
        print(d[d["mode"].isin(["HOLD_HSTR", "HOLD_H1R", "HOLD"])].groupby(["stop", "mode", "year"]).r.mean().unstack("year").round(3).to_string())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
