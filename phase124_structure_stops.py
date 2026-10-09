"""Phase 124 - stops and targets from internal market structure (the user's method).

The user places stops and targets using internal 1-minute and 5-minute swing highs and lows, not a
distance. This tests that on the gap-fade setups (gap >= t x the 14-session range, unfilled at 09:45,
fade toward yesterday's close, exit 12:00, NQ + ES, 2023-04..2026-10). Swings = TJR's definition: a
bullish candle followed by a bearish one makes a swing high at max(high of the pair); a bearish then
bullish pair makes a swing low at min(low of the pair); known once the second candle closes.
Everything is known at the 09:44 close (bars from 08:30).

  STOP   S1 = just beyond the NEAREST 1-minute swing on the far side (a swing high above the entry for a
              short, a swing low below for a long);  S5 = the same on 5-minute swings.
         A candidate closer than 0.05 x the average range is skipped for the next one; none -> no trade.
         Buffer = 1 spread.
  TARGET PC   yesterday's close;  STR = the nearest 5-minute swing in the trade's direction at least 1R away
              (else yesterday's close);  HALF = half off at the nearest 5-minute swing at least 0.5R away,
              stop to breakeven, rest at yesterday's close.
  Compared with the WIDE stop (as far as yesterday's close) on the same days. Judged by points per trade as
  a % of the average daily range, with a 95% bootstrap interval. EXPLORATORY: nothing is tuned.

    python -m phase124_structure_stops
"""
from __future__ import annotations

import datetime as dt
import sys

import numpy as np
import pandas as pd

import phase101_ny_open_sweep as p1

OUT = p1.CACHE + "/phase124_rows.csv"


def events(o, h, l, c):
    """TJR two-candle swings: list of (bar index when known, 'H'|'L', price)."""
    ev = []
    for k in range(1, len(c)):
        if c[k - 1] > o[k - 1] and c[k] < o[k]:
            ev.append((k, "H", max(h[k - 1], h[k])))
        if c[k - 1] < o[k - 1] and c[k] > o[k]:
            ev.append((k, "L", min(l[k - 1], l[k])))
    return ev


def pick(ev, kind, e, above, floor):
    """Nearest swing of `kind` above (or below) the entry, at least `floor` away; None if none."""
    prices = sorted(p for _, kd, p in ev if kd == kind and ((p > e) if above else (p < e)) and abs(p - e) >= floor)
    if not prices:
        return None
    return prices[0] if above else prices[-1]


def simulate(post, side, e, stop, risk, pc, tp1, mode, spread, slip):
    """mode PC | STR | HALF. Returns pnl in points after costs."""
    h, l, c = post["high"].to_numpy(), post["low"].to_numpy(), post["close"].to_numpy()
    target = tp1 if mode == "STR" else pc
    half_done, cur = False, stop
    banked = 0.0
    size = 1.0
    for k in range(len(post)):
        if (side > 0 and l[k] <= cur) or (side < 0 and h[k] >= cur):
            return banked + size * (side * (cur - e)) - spread - slip * (1 + size) - 0.0
        if mode == "HALF" and not half_done and tp1 is not None and ((side > 0 and h[k] >= tp1) or (side < 0 and l[k] <= tp1)):
            banked += 0.5 * abs(tp1 - e)
            size, half_done, cur = 0.5, True, e
        if (side > 0 and h[k] >= target) or (side < 0 and l[k] <= target):
            return banked + size * abs(target - e) - spread - slip
    return banked + size * side * (c[-1] - e) - spread - slip * (1 + size)


def rows(mkt: str, df: pd.DataFrame, thr: float) -> list:
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
        dist = abs(e - pc)
        m1 = df.loc[day + pd.Timedelta(hours=8, minutes=30): t0 - pd.Timedelta(minutes=1)]
        m5 = m1.resample("5min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
        m5 = m5[m5.index + pd.Timedelta(minutes=5) <= t0]
        ev1 = events(*(m1[x].to_numpy() for x in ("open", "high", "low", "close")))
        ev5 = events(*(m5[x].to_numpy() for x in ("open", "high", "low", "close")))
        spread = float(post["spread"].iloc[0])
        kind_stop = "H" if gup else "L"          # a short's stop sits above a swing high; a long's below a swing low
        kind_tp = "L" if gup else "H"
        floor = 0.05 * a
        base = {"market": mkt, "day": str(day.date()), "thresh": thr}
        # reference: wide stop, target = yesterday's close
        out.append({**base, "stop": "WIDE", "target": "PC", "risk": dist, "pnl": simulate(post, side, e, e - side * dist, dist, pc, None, "PC", spread, slip) / a})
        for sname, ev in (("S1", ev1), ("S5", ev5)):
            sw = pick(ev, kind_stop, e, above=gup, floor=floor)
            if sw is None:
                continue
            stop = sw + spread if gup else sw - spread
            risk = abs(e - stop)
            tp_s = pick(ev5, kind_tp, e, above=(not gup), floor=max(risk, 1e-9))     # nearest 5m swing >= 1R away
            tp_h = pick(ev5, kind_tp, e, above=(not gup), floor=0.5 * risk)          # nearest 5m swing >= 0.5R away
            for tname, tp in (("PC", None), ("STR", tp_s if tp_s is not None else pc), ("HALF", tp_h)):
                if tname == "HALF" and tp is None:
                    mode, tpx = "PC", None
                else:
                    mode, tpx = tname, tp
                out.append({**base, "stop": sname, "target": tname, "risk": risk, "pnl": simulate(post, side, e, stop, risk, pc, tpx, mode, spread, slip) / a})
    return out


def main(argv=None) -> int:  # pragma: no cover
    rng = np.random.default_rng(124)
    allr = []
    for m in ("NQ", "ES"):
        df = p1.load(m, "M1")
        df = df[df.index >= pd.Timestamp("2023-03-01")]
        for thr in (0.2, 0.7):
            allr += rows(m, df, thr)
    d = pd.DataFrame(allr)
    d.to_csv(OUT, index=False)
    for thr in (0.2, 0.7):
        print(f"\n===== gap >= {thr} x range =====")
        print(f"{'mkt':<4}{'stop':<6}{'target':<7}{'n':>5}{'median stop':>12}{'win%':>6}{'avg P&L (% of range)':>22}   95% interval")
        for (m, s, t), g in d[d.thresh == thr].groupby(["market", "stop", "target"], sort=False):
            x = g.pnl.to_numpy() * 100
            boot = rng.choice(x, size=(3000, len(x)), replace=True).mean(axis=1)
            print(f"{m:<4}{s:<6}{t:<7}{len(g):>5}{g.risk.median():>11.1f}p{(g.pnl > 0).mean() * 100:>5.0f}%{x.mean():>+21.1f}%   [{np.quantile(boot, .025):+.1f}, {np.quantile(boot, .975):+.1f}]")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
